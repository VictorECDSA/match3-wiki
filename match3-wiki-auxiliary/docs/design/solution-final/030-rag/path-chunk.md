# hybrid-search：全部 16 种 RAG 方法

本文档涵盖适用于分块文本语料库的全部 16 种 RAG 检索方法。每种方法均实现于 `app/rag/chunk/` 目录下。

---

## 共享基础设施

### 混合搜索（Milvus + Elasticsearch + RRF）

大多数方法将其作为基础检索步骤：

```python
# app/rag/chunk/hybrid_search.py
def hybrid_search(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 150,
    alpha: float = 0.5,   # alpha=dense weight, (1-alpha)=BM25 weight
) -> list[dict]:

    query_embedding = _embed_query(rt, query)

    # 1. Milvus ANN — returns id + metadata only (no content stored in Milvus)
    milvus_hits = rt.milvus.search(
        collection_name=constants.MILVUS_COLLECTION,
        data=[query_embedding],
        anns_field="dense_vector",
        search_params={"metric_type": "COSINE", "params": {"ef": 200}},
        limit=top_k,
        filter=f'workspace_id == "{workspace_id}"',
        output_fields=["id", "raw_file_id", "chunk_type"],
    )[0]

    # 2. Elasticsearch BM25
    es_hits = rt.es.search(
        index=constants.ES_INDEX_CHUNKS,
        body={"query": {"bool": {
            "must": {"match": {"content": query}},
            "filter": {"term": {"workspace_id": workspace_id}},
        }}, "size": top_k},
    )["hits"]["hits"]

    # 3. RRF merge — rank positions from both systems combined
    milvus_rank = {h["entity"]["id"]: i for i, h in enumerate(milvus_hits)}
    es_rank     = {h["_id"]: i         for i, h in enumerate(es_hits)}
    all_ids     = set(milvus_rank) | set(es_rank)

    def rrf(cid, k=60):
        return alpha       / (k + milvus_rank.get(cid, top_k + 1)) \
             + (1 - alpha) / (k + es_rank.get(cid,    top_k + 1))

    ranked = sorted(all_ids, key=rrf, reverse=True)[:top_k]

    # 4. Fetch content from PostgreSQL (Milvus holds vectors only)
    chunk_repo = TextChunkRepository(rt.db_engine)
    records = {r.id: r for r in chunk_repo.find_by_ids(list(ranked))}

    return [
        {"id": cid, "content": records[cid].content,
         "raw_file_id": records[cid].raw_file_id, "score": rrf(cid)}
        for cid in ranked if cid in records
    ]


def _embed_query(rt: Match3Runtime, query: str) -> list[float]:
    """Embed a query string; result cached in Redis (TTL 1h)."""
    cache_key = f"embed:{hashlib.md5(query.encode()).hexdigest()}"
    if cached := rt.redis.get(cache_key):
        return json.loads(cached)
    embedding = rt.embedder.embed_both([query])[0][0]
    rt.redis.setex(cache_key, 3600, json.dumps(embedding))
    return embedding
```

### 重排序器

```python
# app/rag/chunk/reranker.py
def rerank(rt: Match3Runtime, query: str, candidates: list[dict], top_k: int = 8) -> list[dict]:
    """Re-rank candidates using rt.reranker (cross-encoder Protocol). Returns top_k."""
    scores = rt.reranker.predict([(query, c["content"]) for c in candidates])
    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)
    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    return candidates[:top_k]
```

---

## 方法 1：Naive RAG

**文件**：`app/rag/chunk/naive_rag.py`
**签名**：`naive_rag(rt, query, workspace_id, top_k=8) → list[dict]`

```
query_embedding = embed(query)
hits = milvus.search(query_embedding, top_k)
records = pg.find_by_ids([h.id for h in hits])
return [{id, content, score}]
```

> 与 `hybrid_search` 的区别：仅用密集向量，无 BM25，无 RRF 合并。内容同样需从 PostgreSQL 二次取回（Milvus 不存正文）。

---

## 方法 2：Multi-Query RAG

**文件**：`app/rag/chunk/multi_query_rag.py`
**签名**：`multi_query_rag(rt, query, workspace_id, n_variants=4, top_k_per_query=20, final_top_k=8) → list[dict]`

**改写提示词**：

```
Generate {n} different versions of the following question.
Each version should approach the question from a different angle or use different terminology.
Return as JSON array of strings.

Original question: {query}
```

```
variants = llm.complete(prompt, n=n_variants)   # → JSON list[str]
all_queries = [query] + variants

for q in all_queries:
    rank_lists[q] = naive_rag(rt, q, workspace_id, top_k=top_k_per_query)

merged = rrf_merge(rank_lists)                  # across all query rank lists
return rerank(rt, query, merged[:150], top_k=final_top_k)
```

---

## 方法 3：HyDE（假设文档嵌入）

**文件**：`app/rag/chunk/hyde_rag.py`
**签名**：`hyde_rag(rt, query, workspace_id, top_k=8) → list[dict]`

**假设文档提示词**：

```
Write a hypothetical answer to the following question, as if you already had the information.
This will be used to find relevant documents, not as a final answer.
Be specific and detailed. Write 100-200 words.

Question: {query}
```

```
hyp_doc       = llm.complete(HYDE_PROMPT)
hyp_embedding = embed(hyp_doc)              # embed hypothetical doc, NOT the original query
hits          = milvus.search(hyp_embedding, limit=150)
return rerank(rt, query, hits, top_k)       # rerank against original query
```

---

## 方法 4–6：混合搜索（已在共享基础设施中介绍）

标准 `hybrid_search()` 函数涵盖方法 4（语义分块）、5（父子块）和 6（混合搜索）：
- **方法 4**（语义分块）：分块在导入阶段由语义分块器预先构建
- **方法 5**（父子块）：存储子块及父块 ID；检索子块，返回父块内容
- **方法 6**（混合）：`hybrid_search()` 配合 RRF

### 父子块检索实现

```python
# app/rag/chunk/hybrid_search.py  (parent-child variant)
def hybrid_search_parent_child(rt, query, workspace_id, top_k=8) -> list[dict]:
    child_results = hybrid_search(rt, query, workspace_id, top_k=30)

    chunk_repo = ChunkRepository(rt.db_engine)
    children   = chunk_repo.find_by_ids([r["id"] for r in child_results])
    parent_ids = list({c.parent_chunk_id for c in children if c.parent_chunk_id})

    if not parent_ids:
        return rerank(rt, query, child_results, top_k=top_k)   # fallback: no parent structure

    parents = chunk_repo.find_by_ids(parent_ids)
    return rerank(rt, query, [
        {"id": c.id, "content": c.content, "raw_file_id": c.raw_file_id, "score": 0.0}
        for c in parents
    ], top_k=top_k)
```

---

## 方法 7：重排序（已在共享基础设施中介绍）

以上 `rerank()` 函数涵盖方法 7。标准流程：`hybrid_search(top_k=150) → rerank(top_k=8)`。

---

## 方法 8：Corrective RAG（CRAG）

**文件**：`app/rag/chunk/crag.py`
**签名**：`corrective_rag(rt, query, workspace_id, relevance_threshold=0.5, top_k=8) → list[dict]`

**相关性检查提示词**：

```
Is this document chunk relevant to the query?
Reply with JSON: {"relevant": true/false, "confidence": 0.0-1.0, "reason": "brief reason"}

Query: {query}
Chunk: {chunk}
```

**三分支决策**（仅对前 10 个候选块执行 LLM 打分，控制 LLM 调用成本）：

```python
candidates = hybrid_search(rt, query, workspace_id, top_k=30)

relevant, ambiguous = [], []
for c in candidates[:10]:                   # LLM relevance check — top 10 only
    conf = llm.check_relevance(query, c["content"][:500])
    if conf >= 0.5:   relevant.append(c)
    elif conf >= 0.3: ambiguous.append(c)

if not relevant and not ambiguous:
    # All chunks irrelevant → fallback to web search (Tavily)
    web_chunks = _web_search_fallback(rt, query)
    candidates = web_chunks + candidates[:5]
elif not relevant:
    # Only ambiguous → refine query and re-search
    refined   = llm.rewrite(query)
    extra     = hybrid_search(rt, refined, workspace_id, top_k=20)
    candidates = ambiguous + extra
else:
    candidates = relevant

return rerank(rt, query, candidates[:150], top_k=top_k)
```

> `_web_search_fallback`：调用 Tavily API；当前返回空列表，集成单独实现。

---

## 方法 9：Self-RAG

**文件**：`app/rag/chunk/self_rag.py`
**签名**：`self_rag(rt, query, workspace_id, top_k=8) → list[dict]`

四个检查点，Checkpoint 1–2 在检索层，Checkpoint 3–4 在生成层：

```
# Checkpoint 1 — need retrieval?
need = llm({"need_retrieval": bool}, query)
if not need: return []     # signal QAService to answer directly without RAG

# Checkpoint 2 — retrieve and filter relevant chunks (ISREL)
candidates     = hybrid_search(query, top_k=20)
relevant_chunks = [c for c in candidates if llm({"relevant": bool}, query, c[:300])]
if not relevant_chunks: return []   # insufficient context

return relevant_chunks[:top_k]

# Checkpoint 3 — is answer grounded in chunks? (ISSUP)   → QAService responsibility
# Checkpoint 4 — is answer useful to the query? (ISUSE)  → QAService responsibility
```

---

## 方法 10：Parent Document RAG

**文件**：`app/rag/chunk/parent_doc_rag.py`
**签名**：`parent_doc_rag(rt, query, workspace_id, top_k=6) → list[dict]`

```
# 1. Search child chunks (exclude chunk_type == "parent" from ANN candidates)
child_hits = hybrid_search(query, top_k=top_k*3)
child_hits = [h for h in child_hits if h.chunk_type != "parent"]

# 2. Deduplicate parent IDs (preserve hit-rank order)
child_records = pg.find_by_ids([h.id for h in child_hits])
parent_ids    = deduplicate([r.parent_id or r.id for r in child_records])[:top_k]

# 3. Return parent chunks (larger context)
return pg.find_by_ids(parent_ids)
```

> 与方法 5 的区别：方法 5 由 `hybrid_search_parent_child` 处理；方法 10 是其独立封装，加入 `chunk_type` 过滤与命中顺序去重。

---

## 方法 11：GraphRAG

**文件**：`app/rag/chunk/graph_rag.py`
**签名**：`graph_rag(rt, query, workspace_id, top_k=8, max_hops=2) → list[dict]`

**实体提取提示词**：

```
Extract the main named entities from this query.
Return JSON: {"entities": ["entity1", "entity2"]}
Query: {query}
```

```
entities      = llm.extract_entities(query)           # → list[str]
subgraph_text = neo4j.expand(entities, max_hops=2)    # APOC path expansion (see below)
graph_chunk   = {"id": "graph_subgraph", "content": subgraph_text, "score": 1.0}

vector_chunks = hybrid_search(query, top_k=30)
return rerank(rt, query, [graph_chunk] + vector_chunks, top_k)
```

**子图查询（Cypher）**：

```cypher
MATCH (start)
WHERE start.name IN $entity_list
CALL apoc.path.subgraphAll(start, {maxLevel: $max_hops})
YIELD nodes, relationships
RETURN nodes, relationships
LIMIT 100
```

> 子图序列化为文本后注入 LLM 上下文：`"[Label] name"` 节点列表 + `"A -[REL]-> B"` 关系列表。

---

## 方法 12：Text-to-SQL RAG

**文件**：`app/rag/chunk/text2sql_rag.py`
**签名**：`text2sql_rag(rt, query, workspace_id) → list[dict]`

**可查询 Schema**：

```
raw_files(id, filename, file_type, tags, created_at, workspace_id)
wiki_pages(id, title, topic, content, tags, created_at, workspace_id)
qa_sessions(id, query, answer, rag_path, created_at, workspace_id)
Only SELECT. Must filter by workspace_id.
```

```
sql = llm.text2sql(query, schema)

# Safety checks before execution:
assert sql.strip().lower().startswith("select")   # no DML/DDL
assert workspace_id in sql                         # prevents cross-tenant leakage

rows = db.execute(text(sql))                       # via SQLAlchemy text()
return [format_as_markdown_table(rows[:50])]
```

---

## 方法 13：Agentic RAG

**文件**：`app/rag/chunk/agentic_rag.py`
**签名**：`agentic_rag(rt, query, workspace_id, max_steps=6) → list[dict]`

**可用工具**：

| 工具 | 参数 | 底层实现 |
|------|------|---------|
| `search(query)` | `query: str` | `hybrid_search()` |
| `get_wiki_page(topic)` | `topic: str` | `WikiPageRepository.find_by_topic()` |
| `graph_query(entities)` | `entities: list[str]` | Neo4j APOC subgraph |

**ReAct 循环**：

```python
messages   = [system_prompt, user_query]
all_chunks = []

for step in range(max_steps):
    response = llm.complete_with_tools(messages, AGENT_TOOLS)
    if response.finish_reason == "stop":
        break

    messages.append(response.assistant_message)

    for tc in response.tool_calls:
        result, chunks = execute_tool(tc.name, tc.args, workspace_id)
        all_chunks.extend(chunks)
        messages.append(tool_result(tc.tool_call_id, result))

return all_chunks[:20]
```

---

## 方法 14：Multi-Agent RAG

详见 `030-rag/multi-agent.md`，内含完整实现。

---

## 方法 15：多模态 RAG

**文件**：`app/rag/chunk/multimodal_rag.py`
**签名**：`multimodal_rag(rt, query, workspace_id, top_k=8) → list[dict]`

```
text_results  = hybrid_search(query, text_collection,  top_k=30)
image_results = clip_search(query,   image_collection, top_k=10)  # query → CLIP embedding

# Normalize image results: {"id", "content": "[Image] {description}", "image_path", ...}
combined = text_results + image_as_text
return rerank(rt, query, combined[:150], top_k)
```

---

## 方法 16：Speculative RAG

**文件**：`app/rag/chunk/speculative_rag.py`
**签名**：`speculative_rag(rt, query, workspace_id, n_drafts=3, top_k=8) → list[dict]`

```python
candidates = hybrid_search(query, top_k=n_drafts * 5)
groups     = split_evenly(candidates, n_drafts)       # list[list[dict]]

# Small model generates one draft answer per group
drafts = []
for group in groups:
    context    = "\n\n".join(c["content"][:400] for c in group)
    draft_text = llm.complete(f"Answer briefly:\n{context}\n\nQuestion: {query}",
                              model=rt.config.llm.draft_model)   # ← small/fast model
    drafts.append({"text": draft_text, "group": group})

# Large model selects the best draft
all_drafts_text = "\n\n".join(f"Draft {i+1}: {d['text']}" for i, d in enumerate(drafts))
best_idx = int(llm.complete(
    f"Which draft (1-{len(drafts)}) best answers: {query}?\n\n{all_drafts_text}",
    model=rt.config.llm.default_model,                           # ← large/accurate model
)) - 1

return rerank(rt, query, drafts[best_idx]["group"], top_k)
```

> 使用两个模型：`draft_model`（小模型并行生成草稿）和 `default_model`（大模型验证选优）。
