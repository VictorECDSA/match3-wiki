# hybrid-search：全部 16 种 RAG 方法

本文档涵盖适用于分块文本语料库的全部 16 种 RAG 检索方法。每种方法均以类的形式实现于 `app/rag/chunk/` 目录下。

---

## 共享基础设施

### 混合搜索（Milvus + Elasticsearch + RRF）

大多数方法将其作为基础检索步骤：

```python
# app/rag/chunk/hybrid_search.py
from app.common.constants import constants

def hybrid_search(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 150,
    alpha: float = 0.5,  # 权重：alpha=向量，(1-alpha)=BM25
) -> list[dict]:
    """混合搜索：Milvus ANN + Elasticsearch BM25，通过 RRF 合并。"""

    # 1. 向量搜索（Milvus）
    # Milvus 仅存储 id、workspace_id、raw_file_id、chunk_type、topic_tags、
    # dense_vector、sparse_vector。内容存于 PostgreSQL（t_text_chunks）。
    query_embedding = _embed_query(rt, query)
    try:
        milvus_results = rt.milvus.search(
            collection_name=constants.MILVUS_COLLECTION,
            data=[query_embedding],
            anns_field="dense_vector",
            search_params={"metric_type": "COSINE", "params": {"ef": 200}},
            limit=top_k,
            filter=f'workspace_id == "{workspace_id}"',
            output_fields=["id", "raw_file_id", "chunk_type"],
        )
    except Exception as e:
        raise Match3Exception.of("failed to milvus hybrid search").ctx(
            query=query, workspace_id=workspace_id,
        ).as_ex(e)

    # 2. BM25 搜索（Elasticsearch）
    try:
        es_response = rt.es.search(
            index=constants.ES_INDEX_CHUNKS,
            body={
                "query": {
                    "bool": {
                        "must": {"match": {"content": query}},
                        "filter": {"term": {"workspace_id": workspace_id}},
                    }
                },
                "size": top_k,
            },
        )
    except Exception as e:
        raise Match3Exception.of("failed to es hybrid search").ctx(
            query=query, workspace_id=workspace_id,
        ).as_ex(e)

    # 3. RRF 合并
    # Milvus 仅返回 id (PK) + raw_file_id；content 在合并后从 PostgreSQL 获取。
    milvus_hits = {hit["entity"]["id"]: hit for hit in milvus_results[0]}
    es_hits = {hit["_id"]: hit for hit in es_response["hits"]["hits"]}

    all_ids = set(milvus_hits.keys()) | set(es_hits.keys())

    def rrf_score(chunk_id: str, k: int = 60) -> float:
        score = 0.0
        milvus_rank = list(milvus_hits.keys()).index(chunk_id) + 1 if chunk_id in milvus_hits else top_k + 1
        es_rank = list(es_hits.keys()).index(chunk_id) + 1 if chunk_id in es_hits else top_k + 1
        score += alpha / (k + milvus_rank)
        score += (1 - alpha) / (k + es_rank)
        return score

    ranked = sorted(all_ids, key=rrf_score, reverse=True)

    # 从 PostgreSQL 按排序后的 ID 获取内容
    chunk_repo = TextChunkRepository(rt.db_engine)
    try:
        pg_records = chunk_repo.find_by_ids(list(ranked[:top_k]))
    except Exception as e:
        raise Match3Exception.of("failed to fetch chunk content from pg after hybrid search").ctx(
            workspace_id=workspace_id,
        ).as_ex(e)

    id_to_record = {r.id: r for r in pg_records}

    results = []
    for chunk_id in ranked[:top_k]:
        rec = id_to_record.get(chunk_id)
        if rec:
            results.append({
                "id": chunk_id,
                "content": rec.content,
                "raw_file_id": rec.raw_file_id,
                "score": rrf_score(chunk_id),
            })

    return results


def _embed_query(rt: Match3Runtime, query: str) -> list[float]:
    """对单条查询字符串进行嵌入，结果缓存于 Redis（TTL 1 小时）。"""
    import hashlib
    import json

    cache_key = f"embed:{hashlib.md5(query.encode()).hexdigest()}"
    cached = rt.redis.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        dense_vecs, _ = rt.embedder.embed_both([query])
    except Exception as e:
        raise Match3Exception.of("failed to embed query").ctx(
            query=query,
        ).as_ex(e)

    embedding = dense_vecs[0]
    rt.redis.setex(cache_key, 3600, json.dumps(embedding))
    return embedding
```

### 重排序器

```python
# app/rag/chunk/reranker.py
# 注意：无全局状态——重排序模型通过 rt.reranker（Protocol 接口）访问。
# 在 build_runtime() 中构建具体的 CrossEncoder，并赋值给 rt.reranker。

def rerank(
    rt: Match3Runtime,
    query: str,
    candidates: list[dict],
    top_k: int = 8,
) -> list[dict]:
    """使用 rt.reranker（cross-encoder Protocol）对候选块重排序，返回 top_k 个。"""
    pairs = [(query, c["content"]) for c in candidates]
    scores = rt.reranker.predict(pairs)
    for c, score in zip(candidates, scores):
        c["rerank_score"] = float(score)
    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    return candidates[:top_k]
```

---

## 方法 1：Naive RAG

```python
# app/rag/chunk/naive_rag.py
from app.common.constants import constants

def naive_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 8,
) -> list[dict]:
    """基础向量搜索 → top-k 块 → 生成答案。

    伪代码：
        query_embedding = embed(query)
        chunks = milvus.search(query_embedding, top_k)
        context = join(chunks)
        answer = llm(query, context)
    """
    query_embedding = _embed_query(rt, query)

    try:
        results = rt.milvus.search(
            collection_name=constants.MILVUS_COLLECTION,
            data=[query_embedding],
            anns_field="dense_vector",
            search_params={"metric_type": "COSINE", "params": {"ef": 200}},
            limit=top_k,
            filter=f'workspace_id == "{workspace_id}"',
            output_fields=["id", "raw_file_id"],
        )
    except Exception as e:
        raise Match3Exception.of("failed to naive_rag milvus search").ctx(
            query=query, workspace_id=workspace_id,
        ).as_ex(e)

    # 从 PostgreSQL 获取内容
    chunk_ids = [hit["entity"]["id"] for hit in results[0]]
    chunk_repo = TextChunkRepository(rt.db_engine)
    try:
        pg_records = chunk_repo.find_by_ids(chunk_ids)
    except Exception as e:
        raise Match3Exception.of("failed to naive_rag fetch pg content").ctx(
            query=query, workspace_id=workspace_id,
        ).as_ex(e)

    id_to_record = {r.id: r for r in pg_records}
    return [
        {"id": hit["entity"]["id"], "content": id_to_record[hit["entity"]["id"]].content,
         "score": hit["distance"]}
        for hit in results[0]
        if hit["entity"]["id"] in id_to_record
    ]
```

---

## 方法 2：Multi-Query RAG

```python
# app/rag/chunk/multi_query_rag.py

MULTI_QUERY_PROMPT = """Generate {n} different versions of the following question.
Each version should approach the question from a different angle or use different terminology.
Return as JSON array of strings.

Original question: {query}"""

def multi_query_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    n_variants: int = 4,
    top_k_per_query: int = 20,
    final_top_k: int = 8,
) -> list[dict]:
    """LLM 将查询改写为 N 个变体，分别检索，通过 RRF 合并。

    伪代码：
        variants = llm.rewrite(query, n=N)
        all_results = []
        for v in [query] + variants:
            results = embed_search(v, top_k)
            all_results.append(results)
        merged = rrf_merge(all_results)
        reranked = rerank(rt, query, merged[:150])
        return reranked[:8]
    """
    # 生成查询变体
    import json

    try:
        raw = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": MULTI_QUERY_PROMPT.format(query=query, n=n_variants),
            }],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("failed to generate multi-query variants").ctx(
            query=query, n_variants=n_variants,
        ).as_ex(e)

    try:
        variants_data = json.loads(raw)
        variants = variants_data if isinstance(variants_data, list) else list(variants_data.values())[0]
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        raise Match3Exception.of("failed to parse multi-query variants response").ctx(
            query=query,
        ).as_ex(e)

    all_queries = [query] + variants[:n_variants]

    # 对每个变体执行搜索
    all_hits: dict[str, dict] = {}
    rank_lists: list[list[str]] = []

    for q in all_queries:
        results = naive_rag(rt, q, workspace_id, top_k=top_k_per_query)
        rank_list = [r["id"] for r in results]
        rank_lists.append(rank_list)
        for r in results:
            all_hits[r["id"]] = r

    # RRF 合并
    def rrf_score(chunk_id: str, k: int = 60) -> float:
        score = 0.0
        for rl in rank_lists:
            if chunk_id in rl:
                rank = rl.index(chunk_id) + 1
                score += 1 / (k + rank)
        return score

    all_ids = list(all_hits.keys())
    all_ids.sort(key=rrf_score, reverse=True)

    top_candidates = [all_hits[cid] for cid in all_ids[:150]]
    return rerank(rt, query, top_candidates, top_k=final_top_k)
```

---

## 方法 3：HyDE（假设文档嵌入）

```python
# app/rag/chunk/hyde_rag.py
from app.common.constants import constants

HYDE_PROMPT = """Write a hypothetical answer to the following question, as if you already had the information.
This will be used to find relevant documents, not as a final answer.
Be specific and detailed. Write 100-200 words.

Question: {query}"""

def hyde_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 8,
) -> list[dict]:
    """生成假设性答案，对其嵌入，用该嵌入进行搜索。

    伪代码：
        hyp_doc = llm("Write an answer to: " + query)
        hyp_embedding = embed(hyp_doc)
        chunks = milvus.search(hyp_embedding, top_k)
        reranked = rerank(rt, query, chunks)
    """
    try:
        hypothetical_doc = rt.llm.complete(
            messages=[{"role": "user", "content": HYDE_PROMPT.format(query=query)}],
        )
    except Exception as e:
        raise Match3Exception.of("failed to generate hyde hypothetical doc").ctx(
            query=query,
        ).as_ex(e)

    # 对假设性文档进行嵌入（而非原始查询）
    hyp_embedding = _embed_query(rt, hypothetical_doc)

    try:
        results = rt.milvus.search(
            collection_name=constants.MILVUS_COLLECTION,
            data=[hyp_embedding],
            anns_field="dense_vector",
            search_params={"metric_type": "COSINE", "params": {"ef": 200}},
            limit=150,
            filter=f'workspace_id == "{workspace_id}"',
            output_fields=["id", "raw_file_id"],
        )
    except Exception as e:
        raise Match3Exception.of("failed to hyde milvus search").ctx(
            query=query, workspace_id=workspace_id,
        ).as_ex(e)

    chunk_ids = [hit["entity"]["id"] for hit in results[0]]
    chunk_repo = TextChunkRepository(rt.db_engine)
    try:
        pg_records = chunk_repo.find_by_ids(chunk_ids)
    except Exception as e:
        raise Match3Exception.of("failed to hyde fetch pg content").ctx(
            query=query, workspace_id=workspace_id,
        ).as_ex(e)

    id_to_record = {r.id: r for r in pg_records}
    candidates = [
        {"id": hit["entity"]["id"], "content": id_to_record[hit["entity"]["id"]].content,
         "score": hit["distance"]}
        for hit in results[0]
        if hit["entity"]["id"] in id_to_record
    ]

    return rerank(rt, query, candidates, top_k=top_k)
```

---

## 方法 4–6：混合搜索（已在共享基础设施中介绍）

标准 `hybrid_search()` 函数涵盖方法 4（语义分块）、5（父子块）和 6（混合搜索）：
- **方法 4**（语义分块）：分块在导入阶段由语义分块器预先构建
- **方法 5**（父子块）：存储子块及父块 ID；检索子块，返回父块内容
- **方法 6**（混合）：`hybrid_search()` 配合 RRF

### 父子块检索实现

```python
# app/rag/chunk/hybrid_search.py  (父子块变体)

def hybrid_search_parent_child(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 8,
) -> list[dict]:
    """用小块进行匹配，返回父块作为上下文。

    伪代码：
        child_chunks = hybrid_search(query, top_k=30)
        parent_ids = {c.parent_chunk_id for c in child_chunks}
        parents = db.get_chunks(parent_ids)
        reranked = rerank(rt, query, parents)
    """
    child_results = hybrid_search(rt, query, workspace_id, top_k=30)
    child_ids = [r["id"] for r in child_results]

    # 从 PostgreSQL 查找父块
    chunk_repo = ChunkRepository(rt.db_engine)
    child_chunks = chunk_repo.find_by_ids(child_ids)

    parent_ids = list({c.parent_chunk_id for c in child_chunks if c.parent_chunk_id})

    if not parent_ids:
        # 无父子结构，回退到子块
        return rerank(rt, query, child_results, top_k=top_k)

    parent_chunks = chunk_repo.find_by_ids(parent_ids)
    parent_candidates = [
        {"id": c.id, "content": c.content, "raw_file_id": c.raw_file_id, "score": 0.0}
        for c in parent_chunks
    ]

    return rerank(rt, query, parent_candidates, top_k=top_k)
```

---

## 方法 7：重排序（已在共享基础设施中介绍）

以上 `rerank()` 函数涵盖方法 7。标准流程：hybrid_search(top_k=150) → rerank(top_k=8)。

---

## 方法 8：Corrective RAG（CRAG）

```python
# app/rag/chunk/crag.py

RELEVANCE_CHECK_PROMPT = """Is this document chunk relevant to the query?
Reply with JSON: {{"relevant": true/false, "confidence": 0.0-1.0, "reason": "brief reason"}}

Query: {query}
Chunk: {chunk}"""

def corrective_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    relevance_threshold: float = 0.5,
    top_k: int = 8,
) -> list[dict]:
    """检索 → 相关性检查 → 若相关性低则回退到 Web 搜索。

    伪代码：
        chunks = hybrid_search(query)
        for each chunk: score = llm.relevance_check(query, chunk)
        if max(scores) < threshold:
            web_results = web_search(query)
            chunks = chunks + web_results
        else:
            chunks = filter(chunks, score >= threshold)
        return rerank(rt, query, chunks)
    """
    candidates = hybrid_search(rt, query, workspace_id, top_k=30)

    # 检查头部候选项的相关性
    relevant = []
    ambiguous = []
    irrelevant = []
    import json

    for candidate in candidates[:10]:  # 仅检查前 10 个
        try:
            raw = rt.llm.complete(
                messages=[{
                    "role": "user",
                    "content": RELEVANCE_CHECK_PROMPT.format(
                        query=query,
                        chunk=candidate["content"][:500],
                    ),
                }],
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise Match3Exception.of("failed to crag relevance check").ctx(
                query=query, chunk_id=candidate["id"],
            ).as_ex(e)

        check = json.loads(raw)
        confidence = check.get("confidence", 0.0)

        if confidence >= relevance_threshold:
            relevant.append(candidate)
        elif confidence >= 0.3:
            ambiguous.append(candidate)
        else:
            irrelevant.append(candidate)

    if not relevant and not ambiguous:
        # 所有块均不相关：回退到 Web 搜索
        web_chunks = _web_search_fallback(rt, query, workspace_id)
        candidates = web_chunks + candidates[:5]
    elif not relevant:
        # 存在模糊块：通过查询改写进行精化
        refined_query = _refine_query(rt, query)
        extra = hybrid_search(rt, refined_query, workspace_id, top_k=20)
        candidates = relevant + ambiguous + extra
    else:
        candidates = relevant

    return rerank(rt, query, candidates[:150], top_k=top_k)


def _web_search_fallback(rt: Match3Runtime, query: str, workspace_id: str) -> list[dict]:
    """当语料库无相关结果时回退到 Web 搜索。
    使用 Tavily API 或类似服务。"""
    # 实现：调用 Tavily 搜索 API，将结果转换为类 chunk 的字典
    # 当前返回空列表（Tavily 集成单独实现）
    rt.logger.warning(f"CRAG: web search fallback triggered for query: {query}")
    return []


def _refine_query(rt: Match3Runtime, query: str) -> str:
    try:
        return rt.llm.complete(
            messages=[{
                "role": "user",
                "content": f"Rewrite this query to be more specific and searchable: {query}",
            }],
        ).strip()
    except Exception as e:
        raise Match3Exception.of("failed to crag refine query").ctx(query=query).as_ex(e)
```

---

## 方法 9：Self-RAG

```python
# app/rag/chunk/self_rag.py

def self_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 8,
) -> list[dict]:
    """4 个检查点的自我反思循环。

    伪代码：
        checkpoint_1: is_retrieval_needed = llm("Need retrieval? " + query)
        if not is_retrieval_needed: return direct_answer()

        chunks = hybrid_search(query)

        checkpoint_2: relevant_chunks = [c for c in chunks if llm.is_relevant(query, c)]
        if not relevant_chunks: return "insufficient context"

        answer = llm(query, relevant_chunks)

        checkpoint_3: is_supported = llm.is_grounded(answer, relevant_chunks)
        if not is_supported: regenerate answer

        checkpoint_4: is_useful = llm.is_useful(query, answer)
        if not is_useful: try different chunks
    """

    # 检查点 1：是否需要检索？
    need_retrieval = _check_need_retrieval(rt, query)
    if not need_retrieval:
        return []  # 向 QAService 发出信号：无需检索块，直接回答

    # 检查点 2：检索并过滤相关块
    candidates = hybrid_search(rt, query, workspace_id, top_k=20)
    relevant_chunks = _filter_relevant(rt, query, candidates)

    if not relevant_chunks:
        return []  # 上下文不足

    return relevant_chunks[:top_k]


def _check_need_retrieval(rt: Match3Runtime, query: str) -> bool:
    import json

    try:
        raw = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": f'Does answering this question require looking up specific information? Reply with JSON: {{"need_retrieval": true/false}}\nQuestion: {query}',
            }],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("failed to self_rag check need retrieval").ctx(query=query).as_ex(e)

    result = json.loads(raw)
    return result.get("need_retrieval", True)


def _filter_relevant(rt: Match3Runtime, query: str, candidates: list[dict]) -> list[dict]:
    """仅保留被 LLM 评为相关（ISREL=1）的块。"""
    import json

    relevant = []

    for c in candidates:
        try:
            raw = rt.llm.complete(
                messages=[{
                    "role": "user",
                    "content": f'Is this chunk relevant to the query?\nQuery: {query}\nChunk: {c["content"][:300]}\nReply: {{"relevant": true/false}}',
                }],
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise Match3Exception.of("failed to self_rag filter relevant").ctx(
                query=query, chunk_id=c["id"],
            ).as_ex(e)

        result = json.loads(raw)
        if result.get("relevant", False):
            relevant.append(c)

    return relevant
```

---

## 方法 10：Parent Document RAG

检索时使用小粒度子块（更精准命中），但返回给 LLM 的是对应的父块（更完整上下文）。

**核心思路**：导入时将原始文本同时切成两套粒度——小子块（~100 token）用于嵌入检索，大父块（~400 token，即 `chunk_type = "parent"`）用于最终提供上下文。子块在 `t_text_chunks` 表中通过 `f_parent_id` 外键关联父块。

```python
# app/rag/chunk/parent_doc_rag.py

def parent_doc_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 6,
) -> list[dict]:
    """检索小粒度子块，再获取其父块内容供 LLM 上下文窗口使用。

    步骤：
      1. 对查询进行嵌入，混合搜索子块（chunk_type != 'parent'）。
      2. 对每个命中的子块，查找其 parent_id。
      3. 去重父块 ID，从 PostgreSQL 获取父块内容。
      4. 返回父块（更大的上下文）给调用方。
    """
    # 1. 搜索子块（从 ANN 候选中排除父级块）
    child_hits = hybrid_search(
        rt=rt,
        query=query,
        workspace_id=workspace_id,
        top_k=top_k * 3,
    )
    child_hits = [h for h in child_hits if h.get("chunk_type") != "parent"]

    if not child_hits:
        return []

    # 2. 收集父块 ID（去重，保留命中顺序）
    chunk_repo = TextChunkRepository(rt.db_engine)
    child_ids = [h["id"] for h in child_hits]

    try:
        child_records = chunk_repo.find_by_ids(child_ids)
    except Exception as e:
        raise Match3Exception.of("failed to fetch child chunk records").ctx(
            count=len(child_ids), workspace_id=workspace_id
        ).as_ex(e)

    seen: set[str] = set()
    parent_ids: list[str] = []
    for rec in child_records:
        pid = rec.parent_id or rec.id   # 无父块时回退到自身
        if pid not in seen:
            seen.add(pid)
            parent_ids.append(pid)
        if len(parent_ids) >= top_k:
            break

    # 3. 获取父块内容
    try:
        parent_records = chunk_repo.find_by_ids(parent_ids)
    except Exception as e:
        raise Match3Exception.of("failed to fetch parent chunk records").ctx(
            count=len(parent_ids), workspace_id=workspace_id
        ).as_ex(e)

    id_to_parent = {r.id: r for r in parent_records}
    return [
        {
            "id": pid,
            "content": id_to_parent[pid].content,
            "raw_file_id": id_to_parent[pid].raw_file_id,
            "chunk_type": id_to_parent[pid].chunk_type,
        }
        for pid in parent_ids
        if pid in id_to_parent
    ]
```

---

## 方法 11：GraphRAG

```python
# app/rag/chunk/graph_rag.py

ENTITY_EXTRACTION_FOR_QUERY_PROMPT = """Extract the main named entities from this query.
Return JSON: {{"entities": ["entity1", "entity2"]}}
Query: {query}"""

def graph_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 8,
    max_hops: int = 2,
) -> list[dict]:
    """实体提取 → Neo4j 子图 → 与向量块合并。

    伪代码：
        entities = llm.extract_entities(query)
        subgraph = neo4j.get_subgraph(entities, max_hops=2)
        subgraph_text = serialize(subgraph)
        vector_chunks = hybrid_search(query)
        combined = vector_chunks + [subgraph_text_chunk]
        return rerank(rt, query, combined)
    """
    # 从查询中提取实体
    entities = _extract_query_entities(rt, query)

    graph_chunks = []
    if entities:
        # 从 Neo4j 获取子图
        subgraph_text = _get_entity_subgraph(rt, entities, max_hops)
        if subgraph_text:
            graph_chunks.append({
                "id": "graph_subgraph",
                "content": subgraph_text,
                "raw_file_id": "neo4j",
                "score": 1.0,
            })

    # 同时执行标准向量搜索
    vector_chunks = hybrid_search(rt, query, workspace_id, top_k=30)

    combined = graph_chunks + vector_chunks
    return rerank(rt, query, combined[:150], top_k=top_k)


def _extract_query_entities(rt: Match3Runtime, query: str) -> list[str]:
    import json

    try:
        raw = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": ENTITY_EXTRACTION_FOR_QUERY_PROMPT.format(query=query),
            }],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("failed to graph_rag extract entities").ctx(query=query).as_ex(e)

    result = json.loads(raw)
    return result.get("entities", [])


def _get_entity_subgraph(rt: Match3Runtime, entities: list[str], max_hops: int) -> str:
    """查询 Neo4j，获取给定实体周围的子图。"""
    entity_list = ", ".join(f'"{e}"' for e in entities)
    cypher = f"""
    MATCH (start)
    WHERE start.name IN [{entity_list}]
    CALL apoc.path.subgraphAll(start, {{maxLevel: {max_hops}}})
    YIELD nodes, relationships
    RETURN nodes, relationships
    LIMIT 100
    """

    with rt.neo4j.session() as session:
        try:
            result = session.run(cypher)
        except Exception as e:
            raise Match3Exception.of("failed to neo4j subgraph query").ctx(
                entities=len(entities), max_hops=max_hops,
            ).as_ex(e)

        nodes = []
        rels = []
        for record in result:
            for node in record["nodes"]:
                nodes.append(f"[{':'.join(node.labels)}] {node['name']}")
            for rel in record["relationships"]:
                rels.append(f"{rel.start_node['name']} -[{rel.type}]-> {rel.end_node['name']}")

    if not nodes and not rels:
        return ""

        return (
            f"知识图谱子图，实体：{', '.join(entities)}\n\n"
            f"实体节点：\n" + "\n".join(nodes) + "\n\n"
            f"关系边：\n" + "\n".join(rels)
        )
```

---

## 方法 12：Text-to-SQL RAG

```python
# app/rag/chunk/text2sql_rag.py
from app.common.constants import codes

TEXT2SQL_SCHEMA = """
Available tables:
- raw_files(id, filename, file_type, tags, created_at, workspace_id)
- wiki_pages(id, title, topic, content, tags, created_at, workspace_id)
- qa_sessions(id, query, answer, rag_path, created_at, workspace_id)

Only SELECT queries allowed. Filter by workspace_id = '{workspace_id}'.
"""

def text2sql_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
) -> list[dict]:
    """将自然语言查询转换为 SQL → 执行 → 将结果作为上下文块返回。

    伪代码：
        sql = llm.text2sql(query, schema)
        result = db.execute(sql)
        return [format_as_chunk(result)]
    """
    sql = _generate_sql(rt, query, workspace_id)
    rows = _execute_safe_sql(rt, sql, workspace_id)

    if not rows:
        return []

    # 将 SQL 结果格式化为块，供 LLM 回答
    result_text = f"SQL query result for: {query}\n\n"
    if rows:
        headers = list(rows[0].keys())
        result_text += "| " + " | ".join(headers) + " |\n"
        result_text += "|" + "|".join(["---"] * len(headers)) + "|\n"
        for row in rows[:50]:
            result_text += "| " + " | ".join(str(row[h]) for h in headers) + " |\n"

    return [{"id": "sql_result", "content": result_text, "raw_file_id": "postgresql", "score": 1.0}]


def _generate_sql(rt: Match3Runtime, query: str, workspace_id: str) -> str:
    prompt = f"""Convert this natural language query to SQL.
{TEXT2SQL_SCHEMA.format(workspace_id=workspace_id)}
Query: {query}
Return only the SQL statement, no explanation."""

    try:
        return rt.llm.complete(
            messages=[{"role": "user", "content": prompt}],
        ).strip()
    except Exception as e:
        raise Match3Exception.of("failed to text2sql generate SQL").ctx(query=query).as_ex(e)


def _execute_safe_sql(rt: Match3Runtime, sql: str, workspace_id: str) -> list[dict]:
    """执行 SQL，含安全检查（仅允许 SELECT，必须含 workspace_id 过滤）。"""
    sql_lower = sql.lower().strip()

    if not sql_lower.startswith("select"):
        raise Match3Exception.of_code(
            codes.INVALID_PARAM,
            "invalid text2sql: only SELECT queries allowed"
        ).ctx(sql=sql[:100])

    if workspace_id not in sql:
        raise Match3Exception.of_code(
            codes.INVALID_PARAM,
            "invalid text2sql: missing workspace_id filter"
        ).ctx(sql=sql[:100])

    from sqlalchemy import text

    try:
        with rt.db_engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row) for row in result.fetchall()]
    except Exception as e:
        raise Match3Exception.of("failed to execute text2sql query").ctx(sql=sql[:100]).as_ex(e)
```

---

## 方法 13：Agentic RAG

```python
# app/rag/chunk/agentic_rag.py
# ReAct 循环：推理 → 行动 → 观察，循环直至得出答案或达到最大步数

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the match3-wiki knowledge base for information.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_wiki_page",
            "description": "Retrieve a specific wiki page by topic slug.",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "graph_query",
            "description": "Query the knowledge graph for entity relationships.",
            "parameters": {
                "type": "object",
                "properties": {"entities": {"type": "array", "items": {"type": "string"}}},
                "required": ["entities"],
            },
        },
    },
]

def agentic_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    max_steps: int = 6,
) -> list[dict]:
    """带工具调用的 ReAct 循环，返回所有检索到的块。

    伪代码：
        messages = [system, user_query]
        for step in range(max_steps):
            response = llm(messages, tools)
            if response.finish_reason == "stop": break
            tool_calls = response.tool_calls
            for tc in tool_calls:
                result = execute_tool(tc)
                messages.append(tool_result(result))
        return all_gathered_chunks
    """
    import json

    all_chunks: list[dict] = []

    messages = [
        {
            "role": "system",
            "content": (
                "You are a research agent for a match-3 game knowledge base. "
                "Use the available tools to gather information, then synthesize an answer. "
                f"All searches are scoped to workspace: {workspace_id}"
            ),
        },
        {"role": "user", "content": query},
    ]

    for step in range(max_steps):
        try:
            tool_results = rt.llm.complete_with_tools(
                messages,
                AGENT_TOOLS,
                model=rt.config.llm.default_model,
            )
        except Exception as e:
            raise Match3Exception.of("failed to agentic_rag llm step").ctx(
                query=query, step=step,
            ).as_ex(e)

        if not tool_results:
            break

        # 追加 assistant 轮次（本步骤所有工具调用共享此消息）
        messages.append(tool_results[0]["assistant_message"])

        if tool_results[0]["finish_reason"] == "stop":
            break

        for tc in tool_results:
            if not tc["tool_name"]:
                continue
            tool_name = tc["tool_name"]
            args = tc["arguments"]

            if tool_name == "search":
                chunks = hybrid_search(rt, args["query"], workspace_id, top_k=10)
                all_chunks.extend(chunks)
                tool_result = "\n".join(c["content"][:300] for c in chunks[:5])
            elif tool_name == "get_wiki_page":
                wiki_page_repo = WikiPageRepository(rt.db_engine)
                page = wiki_page_repo.find_by_topic(args["topic"], workspace_id)
                tool_result = page.content if page else "Wiki page not found."
                if page:
                    all_chunks.append({
                        "id": page.id,
                        "content": page.content,
                        "raw_file_id": "wiki",
                        "score": 1.0,
                    })
            elif tool_name == "graph_query":
                subgraph_text = _get_entity_subgraph(rt, args["entities"], max_hops=2)
                tool_result = subgraph_text or "No graph data found."
                if subgraph_text:
                    all_chunks.append({
                        "id": "graph",
                        "content": subgraph_text,
                        "raw_file_id": "neo4j",
                        "score": 1.0,
                    })
            else:
                tool_result = "Unknown tool."

            messages.append({
                "role": "tool",
                "tool_call_id": tc["tool_call_id"],
                "content": tool_result,
            })

    return all_chunks[:20]
```

---

## 方法 14：Multi-Agent RAG

详见 `030-rag/multi-agent.md`，内含完整实现。

---

## 方法 15：多模态 RAG

通过合并 `text_chunks` 和 `image_chunks` 两个 Milvus 集合的结果来实现。

```python
def multimodal_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 8,
) -> list[dict]:
    """同时搜索文本嵌入和图片嵌入，合并结果。

    伪代码：
        text_results = hybrid_search(query, text_collection)
        image_results = clip_search(query, image_collection)   # text → CLIP embedding
        merged = rrf_merge(text_results, image_results)
        return rerank(rt, query, merged)
    """
    text_results = hybrid_search(rt, query, workspace_id, top_k=30)
    image_results = search_images_by_text(rt, query, workspace_id, top_k=10)

    # 将图片结果转换为相同格式
    image_as_text = [
        {
            "id": r["id"],
            "content": f"[Image] {r['description']}",
            "raw_file_id": r.get("raw_file_id", ""),
            "score": r["score"],
            "image_path": r["image_path"],
        }
        for r in image_results
    ]

    combined = text_results + image_as_text
    return rerank(rt, query, combined[:150], top_k=top_k)
```

---

## 方法 16：Speculative RAG

```python
# app/rag/chunk/speculative_rag.py

def speculative_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    n_drafts: int = 3,
    top_k: int = 8,
) -> list[dict]:
    """多个小模型草稿 + 大模型验证。

    伪代码：
        chunks = hybrid_search(query)
        # 将块分成 N 组
        for each group:
            draft = small_llm(query, group)
        best_draft = large_llm.select(query, drafts)
        relevant_chunks = group_of_best_draft
    """
    candidates = hybrid_search(rt, query, workspace_id, top_k=n_drafts * 5)

    # 分组
    group_size = max(1, len(candidates) // n_drafts)
    groups = [candidates[i:i + group_size] for i in range(0, len(candidates), group_size)][:n_drafts]

    if not groups:
        return []

    # 用小模型生成草稿答案
    drafts = []
    for i, group in enumerate(groups):
        context = "\n\n".join(c["content"][:400] for c in group)
        try:
            draft_text = rt.llm.complete(
                [{"role": "user", "content": f"Based only on this context, answer briefly:\n{context}\n\nQuestion: {query}"}],
                model=rt.config.llm.draft_model,
            )
        except Exception as e:
            raise Match3Exception.of("failed to speculative_rag generate draft").ctx(
                query=query, group_index=i,
            ).as_ex(e)

        drafts.append({
            "draft": draft_text,
            "group": group,
            "group_index": i,
        })

    # 大模型选择最佳草稿
    drafts_text = "\n\n".join(
        f"Draft {i+1}: {d['draft']}" for i, d in enumerate(drafts)
    )
    try:
        verify_text = rt.llm.complete(
            [{"role": "user", "content": f"Which draft best answers the question? Reply with just the number (1-{len(drafts)}).\nQuestion: {query}\n\n{drafts_text}"}],
            model=rt.config.llm.default_model,
        )
    except Exception as e:
        raise Match3Exception.of("failed to speculative_rag verify drafts").ctx(
            query=query, n_drafts=len(drafts),
        ).as_ex(e)

    try:
        best_idx = int(verify_text.strip()) - 1
        best_idx = max(0, min(best_idx, len(drafts) - 1))
    except ValueError:
        best_idx = 0

    return rerank(rt, query, drafts[best_idx]["group"], top_k=top_k)
```
