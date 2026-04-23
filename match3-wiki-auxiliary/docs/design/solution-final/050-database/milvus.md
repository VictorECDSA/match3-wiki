# Milvus 向量存储

## 集合概览

| 集合 | 描述 |
|------|------|
| `match3_chunks` | 所有文本块的稠密向量 + 稀疏向量（text-embedding-3-small，dim=1536） |
| `image_chunks` | 图片的 CLIP 视觉向量（CLIP ViT-L/14，dim=768） |

每个集合均覆盖所有工作区。通过每次查询的 `expr` 过滤器中的 `workspace_id` 标量字段来强制实现工作区隔离。

---

## match3_chunks Schema

**文件**：`app/storage/milvus_store.py`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` (PK) | `VARCHAR(64)` | chunk UUID，与 `t_text_chunks.f_id` 对应 |
| `workspace_id` | `VARCHAR(64)` | 租户隔离键 |
| `raw_file_id` | `VARCHAR(64)` | 来源文件 |
| `chunk_type` | `VARCHAR(32)` | `text \| image \| pageindex_meta \| parent` |
| `topic_tags` | `VARCHAR(1024)` | 逗号拼接，如 `"entities/royal-match,market/puzzle"` |
| `dense_vector` | `FLOAT_VECTOR(1536)` | text-embedding-3-small；索引：HNSW，M=16，efConstruction=256，metric=COSINE |
| `sparse_vector` | `SPARSE_FLOAT_VECTOR` | BGE-M3 稀疏向量；索引：SPARSE_INVERTED_INDEX，drop_ratio_build=0.2，metric=IP |

维度常量来自 `constants.MILVUS_DENSE_DIM` / `constants.MILVUS_SPARSE_DIM`，禁止硬编码。

初始化：`ensure_collection(client)` — 集合不存在时创建并加载，存在则跳过（幂等）。

---

## MilvusStore API

**文件**：`app/storage/milvus_store.py`

### 写操作

| 方法 | 说明 |
|------|------|
| `upsert_chunks(rows)` | 批量 upsert 文本块向量；每行须含 `id, workspace_id, raw_file_id, chunk_type, topic_tags, dense_vector, sparse_vector` |
| `delete_by_raw_file_id(raw_file_id, workspace_id)` | 按文件删除全部向量（`filter` 表达式过滤） |

### 查询

所有查询方法均自动前置 `workspace_id == "{ws}"` 过滤，`expr` 参数追加额外标量过滤（如 `chunk_type == "text"` 或 `topic_tags like "%entities/%"`）：

| 方法 | 索引 | 说明 |
|------|------|------|
| `dense_search(query_vector, workspace_id, top_k, expr?)` | HNSW | COSINE，ef=128 |
| `sparse_search(query_sparse, workspace_id, top_k, expr?)` | SPARSE_INVERTED_INDEX | IP，drop_ratio_search=0.2 |
| `hybrid_search(query_vector, query_sparse, workspace_id, top_k, expr?, rrf_k=60)` | 两者并行 | Milvus 内置 `RRFRanker`，单次 `hybrid_search` 调用 |
| `get_by_ids(chunk_ids)` | PK 点查 | 用于 Speculative RAG 草稿验证 |

所有方法返回 `list[dict]`，含 `id, workspace_id, raw_file_id, chunk_type, topic_tags, distance`。

---

## Embedder

**文件**：`app/storage/embedder.py`

双模型策略：稠密向量用 OpenAI（多语言覆盖好），稀疏向量用 BGE-M3（本地，BM25 权重）：

```python
class Embedder:
    def __init__(self, openai_client, bge_model_path="BAAI/bge-m3"):
        self._openai = openai_client
        self._bge = BGEM3FlagModel(bge_model_path, use_fp16=True)

    def embed_dense(self, texts)  -> list[list[float]]:        # text-embedding-3-small, dim=1536
    def embed_sparse(self, texts) -> list[dict[int, float]]:   # BGE-M3 lexical_weights
    def embed_both(self, texts)   -> tuple[dense, sparse]      # single call for ingestion
```

BGE-M3 在一次前向传播中同时产出 dense / sparse / colbert；此处仅用 `return_sparse=True`。

---

## 导入：写入向量（embed_task.py）

```python
chunks = chunk_repo.find_by_raw_file_id(raw_file_id)
dense_vecs, sparse_vecs = rt.embedder.embed_both([c.content for c in chunks])

rows = [{
    "id": c.id, "workspace_id": c.workspace_id, "raw_file_id": c.raw_file_id,
    "chunk_type": c.chunk_type, "topic_tags": ",".join(c.topic_tags),
    "dense_vector": dense, "sparse_vector": sparse,
} for c, dense, sparse in zip(chunks, dense_vecs, sparse_vecs)]

MilvusStore(rt.milvus).upsert_chunks(rows)
```

---

## 查询示例

**Naive RAG**（仅密集向量）：

```python
hits = milvus.dense_search(query_vec, workspace_id, top_k=10, expr='chunk_type == "text"')
```

**多智能体 RAG**（带领域过滤的混合搜索）：

```python
hits = milvus.hybrid_search(
    query_vector, query_sparse, workspace_id, top_k=10,
    expr='topic_tags like "%entities/%"',
)
```

---

## image_chunks 集合（CLIP 图片向量）

与 `match3_chunks` 分离，维度不同（768 vs 1536）。

### Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` (PK) | `VARCHAR(64)` | image chunk UUID |
| `workspace_id` | `VARCHAR(64)` | 租户隔离键 |
| `raw_file_id` | `VARCHAR(64)` | 来源文件 |
| `topic_tags` | `VARCHAR(1024)` | 逗号拼接标签 |
| `image_path` | `VARCHAR(512)` | MinIO object key，多模态 RAG 检索原图用 |
| `embedding` | `FLOAT_VECTOR(768)` | CLIP ViT-L/14；索引：HNSW，M=16，efConstruction=256，metric=COSINE |

初始化：`ensure_image_collection(client)` — 幂等。

### 写入（embed_task.py 图片分支）

```python
image_chunks = chunk_repo.find_by_raw_file_id_and_type(raw_file_id, CHUNK_TYPE_IMAGE)
embeddings   = rt.image_embedder.embed_images([c.image_path for c in image_chunks])

rows = [{"id": c.id, "workspace_id": c.workspace_id, "raw_file_id": c.raw_file_id,
         "topic_tags": ",".join(c.topic_tags), "image_path": c.image_path, "embedding": emb}
        for c, emb in zip(image_chunks, embeddings)]

rt.milvus.upsert(collection_name=MILVUS_COLLECTION_IMAGES, data=rows)
```

### 查询（multimodal_rag.py）

```python
# image_search(rt, query, workspace_id, top_k=5)
query_vec = rt.image_embedder.embed_text(query)   # CLIP text encoder
hits = rt.milvus.search(
    collection_name=MILVUS_COLLECTION_IMAGES,
    data=[query_vec], anns_field="embedding",
    search_params={"metric_type": "COSINE", "params": {"ef": 128}},
    limit=top_k, filter=f'workspace_id == "{workspace_id}"',
    output_fields=["id", "workspace_id", "raw_file_id", "topic_tags", "image_path"],
)
```

---

## 环境变量

| 变量 | 示例 | 描述 |
|------|------|------|
| `MILVUS_URI` | `http://localhost:19530` | Milvus gRPC 端点 |
| `MILVUS_TOKEN` | *(OSS 版本留空)* | Zilliz Cloud API 令牌 |
| `MILVUS_DB` | `match3` | 数据库名称（Milvus 2.4+） |

```python
client = MilvusClient(uri=env.MILVUS_URI, token=env.MILVUS_TOKEN or "", db_name=env.MILVUS_DB)
```

### constants.py 相关常量

```python
MILVUS_COLLECTION        = "match3_chunks"   # text collection
MILVUS_COLLECTION_IMAGES = "image_chunks"    # CLIP image collection
MILVUS_DENSE_DIM         = 1536              # text-embedding-3-small
MILVUS_SPARSE_DIM        = 250002            # BGE-M3 vocabulary size
MILVUS_IMAGE_DIM         = 768               # CLIP ViT-L/14
```
