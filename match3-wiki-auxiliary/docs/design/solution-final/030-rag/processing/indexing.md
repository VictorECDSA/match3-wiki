# 建索引：三路并行写入

文档经过格式转换、切块、Parent-Child 分层后（见 `chunking.md`），三路索引并发写入。每路存储各司其职，共同支撑查询侧的多通道检索。

```
[parent chunks + child chunks]
        │
        ├── embed_task ──► Dense + Sparse → Milvus         (vector retrieval)
        ├── embed_task ──► raw text + metadata → Elasticsearch (BM25 keyword retrieval)
        └── graph_task ──► LLM entity extraction → Neo4j   (graph retrieval, optional)
```

embed_task 和 graph_task 均为 Celery 异步任务，由导入流水线在 chunk 写入 PostgreSQL 后触发。

---

## 1. Milvus（向量检索）

### 集合与 Schema

文本块写入 `match3_chunks` 集合（`app/storage/milvus_store.py`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `VARCHAR(64)` | chunk UUID，与 `t_text_chunks.f_id` 对应 |
| `workspace_id` | `VARCHAR(64)` | 租户隔离键，所有查询强制过滤 |
| `raw_file_id` | `VARCHAR(64)` | 来源文件 |
| `chunk_type` | `VARCHAR(32)` | `text \| image \| pageindex_meta \| parent` |
| `topic_tags` | `VARCHAR(1024)` | 逗号拼接，如 `"entities/royal-match,market/puzzle"` |
| `dense_vector` | `FLOAT_VECTOR(1536)` | text-embedding-3-small；HNSW，M=16，efConstruction=256，metric=COSINE |
| `sparse_vector` | `SPARSE_FLOAT_VECTOR` | BGE-M3 SPLADE；SPARSE_INVERTED_INDEX，drop_ratio_build=0.2，metric=IP |

> 维度常量来自 `constants.MILVUS_DENSE_DIM` / `constants.MILVUS_SPARSE_DIM`，禁止硬编码。

### Embedder（双模型策略）

**文件**：`app/intelligence/embedder.py`

稠密向量用 OpenAI（多语言覆盖好），稀疏向量用 BGE-M3（本地推理，BM25 权重）：

```python
class Embedder:
    def __init__(self, openai_client, bge_model_path="BAAI/bge-m3"):
        self._openai = openai_client
        self._bge = BGEM3FlagModel(bge_model_path, use_fp16=True)

    def embed_dense(self, texts)  -> list[list[float]]:       # text-embedding-3-small, dim=1536
    def embed_sparse(self, texts) -> list[dict[int, float]]:  # BGE-M3 lexical_weights
    def embed_both(self, texts)   -> tuple[dense, sparse]     # single call for ingestion
```

BGE-M3 一次前向传播同时产出 dense / sparse / colbert，此处仅启用 `return_sparse=True`。

### 写入流程（embed_task.py）

```python
from app.intelligence.embedder import OpenAIEmbedder

chunks = chunk_repo.find_by_raw_file_id(raw_file_id)

# instantiate intelligence-layer embedder (not on Match3Runtime)
embedder = OpenAIEmbedder(api_key=rt.env.OPENAI_API_KEY, model=rt.config.embed.model)
dense_vecs, sparse_vecs = embedder.embed_both([c.content for c in chunks])

rows = [{
    "id": c.id, "workspace_id": c.workspace_id, "raw_file_id": c.raw_file_id,
    "chunk_type": c.chunk_type, "topic_tags": ",".join(c.topic_tags),
    "dense_vector": dense, "sparse_vector": sparse,
} for c, dense, sparse in zip(chunks, dense_vecs, sparse_vecs)]

rt.vector_db.insert(collection_name=constants.MILVUS_COLLECTION, data=rows)
```

> **只写 child chunks**（`chunk_type == "text"`）进向量索引。parent chunks 存在 PostgreSQL，通过 `parent_id` 取回上下文。

---

## 2. Elasticsearch（BM25 关键词检索）

### 写入内容

| 字段 | 说明 |
|------|------|
| `_id` | chunk UUID |
| `content` | 原文文本 |
| `workspace_id` | 租户隔离，所有查询 `filter` 强制匹配 |
| `raw_file_id` | 来源文件 |
| `chunk_type` | `text \| image \| parent` |
| `topic_tags` | 列表，用于域过滤（`prefix` 查询） |

BM25 检索走标准的 `match` 或 `multi_match` 查询，不需要 embedding 模型，写入只是原文 + metadata 的 upsert。

### 写入流程（embed_task.py，与 Milvus 并发）

```python
es_ops = []
for c in chunks:
    es_ops.append({"index": {"_index": constants.ES_INDEX_CHUNKS, "_id": c.id}})
    es_ops.append({
        "content": c.content,
        "workspace_id": c.workspace_id,
        "raw_file_id": c.raw_file_id,
        "chunk_type": c.chunk_type,
        "topic_tags": c.topic_tags,
    })

rt.search.bulk(operations=es_ops)
```

---

## 3. Neo4j（图谱检索，可选）

**默认关闭**。只在工作区明确开启 `graph=True` 时触发 `graph_task`。每个 chunk 调用一次 LLM，成本较高。

### LLM 实体抽取提示词

```
Extract named entities and relationships from the text below.
Return JSON with two keys:
- "entities": list of {"id": "<slug>", "name": "<name>", "type": "<type>"}
- "relations": list of {"from": "<slug>", "to": "<slug>", "relation": "<label>", "weight": 1.0}

Entity types: GAME, COMPANY, FEATURE, MECHANIC, MARKET, METRIC, PERSON
Relationship labels: MADE_BY, HAS_FEATURE, COMPETES_WITH, BELONGS_TO, RELATED_TO

Text: {text[:3000]}
```

### 写入流程（graph_task.py）

```python
from app.intelligence.llm import OpenAILLMCaller

# instantiate intelligence-layer LLM (not on Match3Runtime)
llm = OpenAILLMCaller(api_key=rt.env.OPENAI_API_KEY, model=rt.config.llm.default_model)
data = json.loads(llm.complete(prompt, response_format="json_object"))

# prefix entity IDs with workspace_id for tenant isolation
for e in data["entities"]:
    e["id"] = f"{workspace_id}:{e['id']}"

with rt.graph_db.session() as session:
    # upsert entity nodes
    for entity in data["entities"]:
        session.run(
            f"MERGE (n:{entity['type']} {{name: $name}}) SET n += $props",
            name=entity["name"],
            props=entity.get("properties", {}),
        )
    # upsert entity → entity relationships
    for rel in data["relations"]:
        session.run(
            f"""
            MATCH (a {{name: $from_name}})
            MATCH (b {{name: $to_name}})
            MERGE (a)-[r:{rel['relation']}]->(b)
            SET r.raw_file_id = $raw_file_id
            """,
            from_name=rel["from"],
            to_name=rel["to"],
            raw_file_id=raw_file_id,
        )
```

节点与关系类型的完整定义见 `050-database/neo4j.md`。

---

## 索引侧与查询侧的对应关系

| 索引侧决策 | 查询侧影响 |
|-----------|-----------|
| Milvus dense 必须写入 | 查询侧可开 `dense=True`（默认启用） |
| Milvus sparse 必须写入 | 查询侧才能开 `sparse=True` |
| ES 必须写入 | 查询侧才能开 `bm25=True` |
| Neo4j 写入（`graph=True` 工作区） | 查询侧才能开 `graph=True` |
| 只写 child 进向量索引 | 命中 child → 取 `parent_id` → 返回 parent 上下文 |

查询侧五阶段流水线详见 `030-rag/retrieval/hybrid-search.md`。
