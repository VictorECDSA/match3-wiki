# Vector Database Implementation — Milvus

## 概述

Match3 使用 **Milvus v2.6.14** 作为向量数据库，支持：
- **稠密向量检索**（Dense Embedding，1536-dim）
- **稀疏向量检索**（Sparse Embedding，BGE-M3）
- **混合检索**（Dense + Sparse，使用 RRF 融合）
- **标量过滤**（Metadata Filtering）

## 适配器实现

### MilvusAdapter

```python
# app/intelligence/vector_db/milvus_adapter.py
from pymilvus import MilvusClient, DataType
from app.config.config import Config
from app.runtime.dependencies.logger.logger import Logger


class MilvusAdapter:
    """Milvus 适配器，实现 VectorDB Protocol。"""

    def __init__(self, client: MilvusClient, config: Config, logger: Logger):
        self.client = client
        self.config = config.milvus
        self.logger = logger

    def create_collection(
        self,
        collection_name: str,
        dense_dim: int = 1536,
        enable_sparse: bool = False,
    ):
        """创建集合，支持稠密 + 可选稀疏向量。"""
        schema = self._build_schema(dense_dim, enable_sparse)
        
        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=self._build_index_params(dense_dim, enable_sparse),
        )
        self.logger.info(f"Created collection: {collection_name}")

    def _build_schema(self, dense_dim: int, enable_sparse: bool):
        """构建集合 Schema。"""
        from pymilvus import FieldSchema, CollectionSchema
        
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
            FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=dense_dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="workspace_id", dtype=DataType.INT64),
            FieldSchema(name="raw_file_id", dtype=DataType.INT64),
        ]
        
        if enable_sparse:
            fields.append(
                FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR)
            )
        
        return CollectionSchema(fields=fields, description="Match3 vector collection")

    def _build_index_params(self, dense_dim: int, enable_sparse: bool):
        """构建索引参数。"""
        index_params = [
            {
                "field_name": "dense_vector",
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 16, "efConstruction": 256},
            }
        ]
        
        if enable_sparse:
            index_params.append({
                "field_name": "sparse_vector",
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "IP",
            })
        
        return index_params

    def insert(self, collection_name: str, data: list[dict]):
        """插入向量数据。"""
        self.client.insert(
            collection_name=collection_name,
            data=data,
        )
        self.logger.debug(f"Inserted {len(data)} vectors into {collection_name}")

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 20,
        filter_expr: str | None = None,
    ) -> list[dict]:
        """稠密向量检索。"""
        results = self.client.search(
            collection_name=collection_name,
            data=[query_vector],
            anns_field="dense_vector",
            limit=limit,
            filter=filter_expr,
            output_fields=["id", "text", "workspace_id", "raw_file_id"],
        )
        
        return self._parse_results(results[0])

    def hybrid_search(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: dict,
        limit: int = 20,
        filter_expr: str | None = None,
    ) -> list[dict]:
        """混合检索（Dense + Sparse）。"""
        from pymilvus import AnnSearchRequest, RRFRanker
        
        # 稠密检索请求
        dense_req = AnnSearchRequest(
            data=[dense_vector],
            anns_field="dense_vector",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=top_k * 2,
        )
        
        # 稀疏检索请求
        sparse_req = AnnSearchRequest(
            data=[sparse_vector],
            anns_field="sparse_vector",
            param={"metric_type": "IP"},
            limit=top_k * 2,
        )
        
        # 使用 RRF 融合
        results = self.client.hybrid_search(
            collection_name=collection_name,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(k=60),
            limit=top_k,
            filter=filter_expr,
            output_fields=["id", "text", "workspace_id", "raw_file_id"],
        )
        
        return self._parse_results(results[0])

    def _parse_results(self, raw_results) -> list[dict]:
        """解析检索结果。"""
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "text": hit.entity.get("text"),
                "workspace_id": hit.entity.get("workspace_id"),
                "raw_file_id": hit.entity.get("raw_file_id"),
            }
            for hit in raw_results
        ]
```

## Runtime 集成

```python
# app/runtime.py (build_runtime 部分)
from pymilvus import MilvusClient

milvus_client = MilvusClient(uri=env.MILVUS_URI)

return Match3Runtime(
    # ...
    milvus=milvus_client,
    # ...
)
```

## 集合设计

### 文本集合（text_chunks）

```python
{
    "id": 12345,                          # Chunk ID
    "dense_vector": [0.1, 0.2, ...],      # 1536-dim (text-embedding-3-small)
    "sparse_vector": {102: 0.5, 205: 0.3},# BGE-M3 稀疏向量
    "text": "实际文本内容...",
    "workspace_id": 1,
    "raw_file_id": 42,
}
```

### 图片集合（image_chunks）

```python
{
    "id": 67890,
    "dense_vector": [0.3, 0.1, ...],      # 768-dim (CLIP ViT-L/14)
    "text": "GPT-4V 生成的图片描述",
    "workspace_id": 1,
    "raw_file_id": 42,
}
```

## 使用示例

### 创建集合

```python
from app.intelligence.vector_db.milvus_adapter import MilvusAdapter

adapter = MilvusAdapter(rt)
adapter.create_collection(
    collection_name="text_chunks",
    dense_dim=1536,
    enable_sparse=True,
)
```

### 插入向量

```python
data = [
    {
        "id": 1,
        "dense_vector": [0.1, 0.2, ...],
        "sparse_vector": {102: 0.5, 205: 0.3},
        "text": "这是一段文本",
        "workspace_id": 1,
        "raw_file_id": 42,
    },
    # ... 更多数据
]

adapter.insert("text_chunks", data)
```

### 稠密检索

```python
results = adapter.search(
    collection_name="text_chunks",
    query_vector=[0.15, 0.22, ...],
    limit=20,
    filter_expr="workspace_id == 1",
)
```

### 混合检索

```python
results = adapter.hybrid_search(
    collection_name="text_chunks",
    dense_vector=[0.15, 0.22, ...],
    sparse_vector={102: 0.5, 205: 0.3},
    limit=20,
    filter_expr="workspace_id == 1",
)
```

## 配置参数

### Config (config.yaml)

```yaml
milvus:
  consistency_level: Eventually  # Strong | Bounded | Eventually
```

### Env (.env)

```bash
MILVUS_URI=http://localhost:19530
```

## 性能优化

### 1. 批量插入

每次插入 **100-500 条**向量，避免单条插入：

```python
batch_size = 500
for i in range(0, len(all_data), batch_size):
    batch = all_data[i:i + batch_size]
    adapter.insert("text_chunks", batch)
```

### 2. 索引参数调优

- **HNSW M**：16-64（越大精度越高，内存越大）
- **efConstruction**：128-512（越大构建越慢，精度越高）
- **搜索 ef**：32-128（越大精度越高，速度越慢）

### 3. 一致性级别

- **Strong**：强一致性，适合实时插入后立即搜索
- **Eventually**：最终一致性，适合批量导入后搜索

## 相关文档

- **[protocol.md](./protocol.md)** — VectorDB Protocol 定义
- **[versions/milvus-v2.6.14.md](./versions/milvus-v2.6.14.md)** — Milvus 版本技术文档
- **[../../design/solution-final/020-ingestion/](../../design/solution-final/020-ingestion/)** — 向量嵌入流程
