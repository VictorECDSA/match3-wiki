# Milvus 向量存储

## 集合概览

| 集合 | 描述 |
|------|------|
| `match3_chunks` | 所有文本块的稠密向量 + 稀疏向量（text-embedding-3-small，dim=1536） |
| `image_chunks` | 图片的 CLIP 视觉向量（CLIP ViT-L/14，dim=768） |

每个集合均覆盖所有工作区。通过每次查询的 `expr` 过滤器中的 `workspace_id` 标量字段来强制实现工作区隔离。

---

## 集合 Schema

```python
# app/storage/milvus_store.py
from pymilvus import (
    MilvusClient,
    CollectionSchema,
    FieldSchema,
    DataType,
)
from app.common.constants import constants

# 集合名称和维度来自常量定义，禁止在此硬编码
DENSE_DIM = constants.MILVUS_DENSE_DIM    # 1536，text-embedding-3-small
SPARSE_DIM = constants.MILVUS_SPARSE_DIM  # 250002，BGE-M3 稀疏词表大小


def get_chunk_schema() -> CollectionSchema:
    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.VARCHAR,
            max_length=64,
            is_primary=True,
            auto_id=False,
            description="chunk UUID matching t_text_chunks.f_id",
        ),
        FieldSchema(
            name="workspace_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="workspace isolation key",
        ),
        FieldSchema(
            name="raw_file_id",
            dtype=DataType.VARCHAR,
            max_length=64,
        ),
        FieldSchema(
            name="chunk_type",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="text | image | pageindex_meta | parent",
        ),
        # topic_tags 以逗号拼接字符串存储，用于标量过滤
        # 如 "entities/royal-match,market/puzzle"
        FieldSchema(
            name="topic_tags",
            dtype=DataType.VARCHAR,
            max_length=1024,
        ),
        FieldSchema(
            name="dense_vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=DENSE_DIM,
        ),
        FieldSchema(
            name="sparse_vector",
            dtype=DataType.SPARSE_FLOAT_VECTOR,
        ),
    ]
    return CollectionSchema(
        fields=fields,
        description="match3 text chunk vectors",
        enable_dynamic_field=False,
    )
```

---

## 索引配置

```python
# app/storage/milvus_store.py  (continued)

DENSE_INDEX_PARAMS = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {
        "M": 16,
        "efConstruction": 256,
    },
}

SPARSE_INDEX_PARAMS = {
    "metric_type": "IP",
    "index_type": "SPARSE_INVERTED_INDEX",
    "params": {
        "drop_ratio_build": 0.2,  # 索引构建时裁剪低权重词元
    },
}


def ensure_collection(client: MilvusClient) -> None:
    """若集合不存在则创建集合和索引。"""
    if client.has_collection(constants.MILVUS_COLLECTION):
        return

    schema = get_chunk_schema()
    client.create_collection(
        collection_name=constants.MILVUS_COLLECTION,
        schema=schema,
    )

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="dense_vector",
        **DENSE_INDEX_PARAMS,
    )
    index_params.add_index(
        field_name="sparse_vector",
        **SPARSE_INDEX_PARAMS,
    )
    client.create_index(
        collection_name=constants.MILVUS_COLLECTION,
        index_params=index_params,
    )
    client.load_collection(constants.MILVUS_COLLECTION)
```

---

## MilvusStore 类

```python
# app/storage/milvus_store.py  (continued)
from __future__ import annotations
from typing import Any, Optional
from pymilvus import MilvusClient, AnnSearchRequest, RRFRanker


class MilvusStore:
    """
    MilvusClient 的封装，用于文本块向量操作。

    所有公开方法均接受 workspace_id 参数，通过标量过滤表达式强制实现租户隔离。
    """

    def __init__(self, client: MilvusClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def upsert_chunks(self, rows: list[dict[str, Any]]) -> None:
        """
        插入或更新文本块向量。

        每行必须包含：
          id, workspace_id, raw_file_id, chunk_type, topic_tags（逗号分隔），
          dense_vector (list[float])，sparse_vector (dict[int, float])

        使用 upsert，因此重新导入文件是幂等的。
        """
        self._client.upsert(
            collection_name=constants.MILVUS_COLLECTION,
            data=rows,
        )

    def delete_by_raw_file_id(self, raw_file_id: str, workspace_id: str) -> None:
        """删除某个文件的所有文本块向量。"""
        self._client.delete(
            collection_name=constants.MILVUS_COLLECTION,
            filter=f'raw_file_id == "{raw_file_id}" and workspace_id == "{workspace_id}"',
        )

    # ------------------------------------------------------------------
    # 稠密向量搜索
    # ------------------------------------------------------------------

    def dense_search(
        self,
        query_vector: list[float],
        workspace_id: str,
        top_k: int = 20,
        expr: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        使用稠密 HNSW 索引进行近似近邻搜索。

        Args:
            query_vector: 查询的嵌入向量。
            workspace_id: 租户过滤器（始终应用）。
            top_k: 返回的候选数量。
            expr: 额外的标量过滤表达式，例如
                  'chunk_type == "text"' 或
                  'topic_tags like "%entities/royal-match%"'。
                  工作区过滤器会自动前置。

        Returns:
            包含以下键的结果字典列表：id, workspace_id, raw_file_id,
            chunk_type, topic_tags, distance。
        """
        base_expr = f'workspace_id == "{workspace_id}"'
        full_expr = f"{base_expr} and ({expr})" if expr else base_expr

        results = self._client.search(
            collection_name=constants.MILVUS_COLLECTION,
            data=[query_vector],
            anns_field="dense_vector",
            search_params={"metric_type": "COSINE", "params": {"ef": 128}},
            limit=top_k,
            filter=full_expr,
            output_fields=["id", "workspace_id", "raw_file_id", "chunk_type", "topic_tags"],
        )
        return _flatten_hits(results)

    # ------------------------------------------------------------------
    # 稀疏向量搜索
    # ------------------------------------------------------------------

    def sparse_search(
        self,
        query_sparse: dict[int, float],
        workspace_id: str,
        top_k: int = 20,
        expr: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        使用稀疏 SPARSE_INVERTED_INDEX 进行关键词搜索。

        Args:
            query_sparse: BGE-M3 稀疏向量 {token_id: weight}。
            workspace_id: 租户过滤器。
            top_k: 返回的候选数量。
            expr: 额外的标量过滤器。
        """
        base_expr = f'workspace_id == "{workspace_id}"'
        full_expr = f"{base_expr} and ({expr})" if expr else base_expr

        results = self._client.search(
            collection_name=constants.MILVUS_COLLECTION,
            data=[query_sparse],
            anns_field="sparse_vector",
            search_params={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
            limit=top_k,
            filter=full_expr,
            output_fields=["id", "workspace_id", "raw_file_id", "chunk_type", "topic_tags"],
        )
        return _flatten_hits(results)

    # ------------------------------------------------------------------
    # 混合搜索（RRF）
    # ------------------------------------------------------------------

    def hybrid_search(
        self,
        query_vector: list[float],
        query_sparse: dict[int, float],
        workspace_id: str,
        top_k: int = 10,
        expr: Optional[str] = None,
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        """
        对稠密向量 + 稀疏向量结果进行倒序排名融合（RRF）。

        在 Milvus 内部并行运行两个近似近邻搜索，然后使用 RRF 重新排序。
        这是混合检索 RAG 方法的默认检索路径。

        Args:
            query_vector: 稠密嵌入向量。
            query_sparse: BGE-M3 的稀疏词元权重。
            workspace_id: 租户过滤器。
            top_k: 重新排序后的最终结果数量。
            expr: 额外的过滤器（例如领域标签限制）。
            rrf_k: RRF 平滑常数（默认 60，标准值）。
        """
        base_expr = f'workspace_id == "{workspace_id}"'
        full_expr = f"{base_expr} and ({expr})" if expr else base_expr

        dense_req = AnnSearchRequest(
            data=[query_vector],
            anns_field="dense_vector",
            param={"metric_type": "COSINE", "params": {"ef": 128}},
            limit=top_k * 2,
            expr=full_expr,
        )
        sparse_req = AnnSearchRequest(
            data=[query_sparse],
            anns_field="sparse_vector",
            param={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
            limit=top_k * 2,
            expr=full_expr,
        )

        results = self._client.hybrid_search(
            collection_name=constants.MILVUS_COLLECTION,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(k=rrf_k),
            limit=top_k,
            output_fields=["id", "workspace_id", "raw_file_id", "chunk_type", "topic_tags"],
        )
        return _flatten_hits(results)

    # ------------------------------------------------------------------
    # 按 ID 批量获取
    # ------------------------------------------------------------------

    def get_by_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        """按主键获取向量记录（用于推测式 RAG 草稿验证）。"""
        if not chunk_ids:
            return []
        results = self._client.get(
            collection_name=constants.MILVUS_COLLECTION,
            ids=chunk_ids,
            output_fields=["id", "workspace_id", "raw_file_id", "chunk_type", "topic_tags"],
        )
        return results


# ------------------------------------------------------------------
# 内部辅助函数
# ------------------------------------------------------------------

def _flatten_hits(search_results: list) -> list[dict[str, Any]]:
    """将 MilvusClient 搜索结果规范化为扁平字典列表。"""
    hits = []
    for batch in search_results:
        for hit in batch:
            entry = hit.get("entity", {}).copy()
            entry["distance"] = hit.get("distance", 0.0)
            hits.append(entry)
    return hits
```

---

## 嵌入辅助工具

```python
# app/storage/embedder.py
from __future__ import annotations
from FlagEmbedding import BGEM3FlagModel


class Embedder:
    """
    封装 BGE-M3，同时支持稠密和稀疏嵌入。

    BGE-M3 在一次前向传播中生成三种嵌入：
    - dense：1024 维浮点向量（如需可投影至 1536 维，或直接使用）
    - sparse：BM25 风格的 {token_id: weight} 字典
    - colbert：多向量（此处未使用）

    稠密向量使用 text-embedding-3-small（OpenAI）以获得更好的多语言覆盖；
    稀疏向量使用 BGE-M3 获取 BM25 权重。
    """

    def __init__(self, openai_client, bge_model_path: str = "BAAI/bge-m3") -> None:
        self._openai = openai_client
        self._bge = BGEM3FlagModel(bge_model_path, use_fp16=True)

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        """使用 text-embedding-3-small（dim=1536）对文本列表进行嵌入。"""
        resp = self._openai.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in resp.data]

    def embed_sparse(self, texts: list[str]) -> list[dict[int, float]]:
        """返回 BGE-M3 稀疏向量，格式为 {token_id: weight} 字典。"""
        output = self._bge.encode(
            texts,
            return_dense=False,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        # output["lexical_weights"] 是 {token_id_str: float} 字典列表
        return [
            {int(k): float(v) for k, v in row.items()}
            for row in output["lexical_weights"]
        ]

    def embed_both(self, texts: list[str]) -> tuple[list[list[float]], list[dict[int, float]]]:
        """对相同的输入列表返回 (dense_vectors, sparse_vectors)。"""
        dense = self.embed_dense(texts)
        sparse = self.embed_sparse(texts)
        return dense, sparse
```

---

## 导入：写入向量

在 `embed` Celery 任务中，PostgreSQL 块创建完成后：

```python
# app/workers/tasks/embed_task.py  (relevant excerpt)
from app.storage.milvus_store import MilvusStore

def _embed_and_store(rt: Match3Runtime, raw_file_id: str) -> None:
    chunk_repo = TextChunkRepository(rt.db_engine)
    milvus_store = MilvusStore(rt.milvus)

    chunks = chunk_repo.find_by_raw_file_id(raw_file_id)
    texts = [c.content for c in chunks]

    dense_vecs, sparse_vecs = rt.embedder.embed_both(texts)

    rows = []
    for chunk, dense, sparse in zip(chunks, dense_vecs, sparse_vecs):
        rows.append({
            "id": chunk.id,
            "workspace_id": chunk.workspace_id,
            "raw_file_id": chunk.raw_file_id,
            "chunk_type": chunk.chunk_type,
            "topic_tags": ",".join(chunk.topic_tags),
            "dense_vector": dense,
            "sparse_vector": sparse,
        })

    milvus_store.upsert_chunks(rows)
```

---

## 查询：在 RAG 中读取向量

示例：仅使用稠密搜索的朴素 RAG 路径。

```python
from app.storage.milvus_store import MilvusStore

def retrieve_chunks(
    milvus: MilvusStore,
    query_vec: list[float],
    workspace_id: str,
    top_k: int = 10,
) -> list[str]:
    hits = milvus.dense_search(
        query_vector=query_vec,
        workspace_id=workspace_id,
        top_k=top_k,
        expr='chunk_type == "text"',
    )
    return [h["id"] for h in hits]
```

示例：带领域过滤器的混合搜索（多智能体 RAG）：

```python
hits = milvus.hybrid_search(
    query_vector=query_vec,
    query_sparse=query_sparse,
    workspace_id=workspace_id,
    top_k=10,
    expr='topic_tags like "%entities/%"',   # domain = "entities"
)
```

---

## 环境变量

| 变量 | 示例 | 描述 |
|------|------|------|
| `MILVUS_URI` | `http://localhost:19530` | Milvus gRPC 端点 |
| `MILVUS_TOKEN` | *(OSS 版本留空)* | Zilliz Cloud API 令牌 |
| `MILVUS_DB` | `match3` | 数据库名称（Milvus 2.4+） |

在 `Match3Runtime` 中的客户端构建：

```python
from pymilvus import MilvusClient

client = MilvusClient(
    uri=env.MILVUS_URI,
    token=env.MILVUS_TOKEN or "",
    db_name=env.MILVUS_DB,
)
```

---

## image_chunks 集合（CLIP 图片向量）

图片经 CLIP ViT-L/14 编码后存入 `image_chunks` 集合，与文本块的 `match3_chunks` 集合分离，维度不同（768 vs 1536）。

### Schema

```python
# app/storage/milvus_store.py  (image_chunks section)
from app.common.constants import constants

IMAGE_DIM = constants.MILVUS_IMAGE_DIM    # 768，CLIP ViT-L/14


def get_image_schema() -> CollectionSchema:
    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.VARCHAR,
            max_length=64,
            is_primary=True,
            auto_id=False,
            description="image chunk UUID matching t_text_chunks.f_id (chunk_type=image)",
        ),
        FieldSchema(
            name="workspace_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="workspace isolation key",
        ),
        FieldSchema(
            name="raw_file_id",
            dtype=DataType.VARCHAR,
            max_length=64,
        ),
        # topic_tags 以逗号拼接字符串存储，用于标量过滤
        FieldSchema(
            name="topic_tags",
            dtype=DataType.VARCHAR,
            max_length=1024,
        ),
        # 图片文件的 MinIO object key，用于多模态 RAG 中检索原始图片
        FieldSchema(
            name="image_path",
            dtype=DataType.VARCHAR,
            max_length=512,
        ),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=IMAGE_DIM,
        ),
    ]
    return CollectionSchema(
        fields=fields,
        description="match3 image chunk CLIP vectors",
        enable_dynamic_field=False,
    )


def ensure_image_collection(client: MilvusClient) -> None:
    """若 image_chunks 集合不存在则创建集合和 HNSW 索引。"""
    if client.has_collection(constants.MILVUS_COLLECTION_IMAGES):
        return

    schema = get_image_schema()
    client.create_collection(
        collection_name=constants.MILVUS_COLLECTION_IMAGES,
        schema=schema,
    )

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        metric_type="COSINE",
        index_type="HNSW",
        params={"M": 16, "efConstruction": 256},
    )
    client.create_index(
        collection_name=constants.MILVUS_COLLECTION_IMAGES,
        index_params=index_params,
    )
    client.load_collection(constants.MILVUS_COLLECTION_IMAGES)
```

### 写入（导入阶段）

在 `ingest_task` 中，图片经 CLIP 编码后写入 `image_chunks`：

```python
# app/workers/tasks/embed_task.py  (image section)

def _embed_and_store_images(rt: Match3Runtime, raw_file_id: str) -> None:
    chunk_repo = TextChunkRepository(rt.db_engine)
    image_chunks = chunk_repo.find_by_raw_file_id_and_type(
        raw_file_id, constants.CHUNK_TYPE_IMAGE
    )
    if not image_chunks:
        return

    image_paths = [c.image_path for c in image_chunks]

    try:
        embeddings = rt.image_embedder.embed_images(image_paths)
    except Exception as e:
        raise Match3Exception.of("failed to embed images").ctx(
            raw_file_id=raw_file_id, count=len(image_paths)
        ).as_ex(e)

    rows = []
    for chunk, emb in zip(image_chunks, embeddings):
        rows.append({
            "id": chunk.id,
            "workspace_id": chunk.workspace_id,
            "raw_file_id": chunk.raw_file_id,
            "topic_tags": ",".join(chunk.topic_tags),
            "image_path": chunk.image_path,
            "embedding": emb,
        })

    try:
        rt.milvus.upsert(
            collection_name=constants.MILVUS_COLLECTION_IMAGES,
            data=rows,
        )
    except Exception as e:
        raise Match3Exception.of("failed to upsert image chunks to milvus").ctx(
            raw_file_id=raw_file_id, count=len(rows)
        ).as_ex(e)
```

### 查询（多模态 RAG）

```python
# app/rag/chunk/multimodal_rag.py  (image search section)

def image_search(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 5,
) -> list[dict]:
    """使用 CLIP 对文本查询进行编码，在 image_chunks 集合中执行搜索。"""
    try:
        query_vec = rt.image_embedder.embed_text(query)
    except Exception as e:
        raise Match3Exception.of("failed to embed query for image search").ctx(
            query_len=len(query), workspace_id=workspace_id
        ).as_ex(e)

    try:
        results = rt.milvus.search(
            collection_name=constants.MILVUS_COLLECTION_IMAGES,
            data=[query_vec],
            anns_field="embedding",
            search_params={"metric_type": "COSINE", "params": {"ef": 128}},
            limit=top_k,
            filter=f'workspace_id == "{workspace_id}"',
            output_fields=["id", "workspace_id", "raw_file_id", "topic_tags", "image_path"],
        )
    except Exception as e:
        raise Match3Exception.of("failed to search image chunks").ctx(
            workspace_id=workspace_id, top_k=top_k
        ).as_ex(e)

    return _flatten_hits(results)
```

### constants.py 补充项

`image_chunks` 集合相关常量已定义于 `app/common/constants/constants.py`：

```python
MILVUS_COLLECTION_IMAGES = "image_chunks"    # CLIP 图片块集合
MILVUS_IMAGE_DIM         = 768               # CLIP ViT-L/14 输出维度
```
