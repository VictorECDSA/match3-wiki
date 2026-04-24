# Vector Database Implementation — Milvus

## 概述

使用 **Milvus v2.6.14** 实现 `VectorDatabase` Protocol，支持稠密向量、稀疏向量、混合检索和元数据过滤。

---

## 工厂函数

```python
# backend/runtime_impl/implements/vector_db/vector_db.py
from pymilvus import MilvusClient
from backend.config import Config, Env
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.vector_db import VectorDatabase
from .impl_milvus.milvus_adapter import MilvusAdapter

def create_vector_database(config: Config, env: Env, logger: Logger) -> VectorDatabase:
    """创建 VectorDatabase 实例
    
    Args:
        config: 配置对象
        env: 环境变量
        logger: 日志记录器
    
    Returns:
        实现了 VectorDatabase Protocol 的 MilvusAdapter 实例
    
    Raises:
        ValueError: provider 不支持时抛出
    """
    provider = config.runtime.vector_db.provider
    
    if provider == "milvus":
        milvus_client = MilvusClient(
            uri=env.MILVUS_URI,
            timeout=config.runtime.vector_db.implementations.milvus.timeout,
        )
        
        logger.info("Milvus client initialized")
        return MilvusAdapter(milvus_client, config, logger)
    else:
        raise ValueError(f"Unsupported vector_db provider: {provider}")
```

---

## 适配器实现

```python
# backend/runtime_impl/implements/vector_db/impl_milvus/milvus_adapter.py
from pymilvus import MilvusClient, DataType, FieldSchema, CollectionSchema
from backend.config import Config
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.vector_db import VectorDatabase

class MilvusAdapter:
    """Milvus 适配器，实现 VectorDatabase Protocol"""
    
    def __init__(self, client: MilvusClient, config: Config, logger: Logger):
        self.client = client
        self.config = config.runtime.vector_db
        self.logger = logger
    
    def create_collection(
        self,
        collection_name: str,
        dense_dim: int = 1536,
        enable_sparse: bool = False,
    ):
        """创建集合"""
        schema = self._build_schema(dense_dim, enable_sparse)
        
        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=self._build_index_params(dense_dim, enable_sparse),
        )
        self.logger.info(f"Created collection: {collection_name}")
    
    def _build_schema(self, dense_dim: int, enable_sparse: bool):
        """构建集合 Schema"""
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
        """构建索引参数"""
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
        """插入向量数据"""
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
        """稠密向量检索"""
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
        """混合检索（Dense + Sparse + RRF）"""
        from pymilvus import AnnSearchRequest, RRFRanker
        
        dense_req = AnnSearchRequest(
            data=[dense_vector],
            anns_field="dense_vector",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=limit * 2,
        )
        
        sparse_req = AnnSearchRequest(
            data=[sparse_vector],
            anns_field="sparse_vector",
            param={"metric_type": "IP"},
            limit=limit * 2,
        )
        
        results = self.client.hybrid_search(
            collection_name=collection_name,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(k=60),
            limit=limit,
            filter=filter_expr,
            output_fields=["id", "text", "workspace_id", "raw_file_id"],
        )
        
        return self._parse_results(results[0])
    
    def _parse_results(self, raw_results) -> list[dict]:
        """解析检索结果"""
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

---

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  vector_db:
    provider: milvus
    implementations:
      milvus:
        timeout: 30                      # 请求超时（秒）
        consistency_level: Eventually    # 一致性级别: Strong | Bounded | Eventually
```

### Env (.env)

```bash
MILVUS_URI=http://localhost:19530
```

---

## 相关文档

- **[protocol.md](./protocol.md)** — VectorDatabase Protocol 定义
- **[versions/milvus-v2.6.14.md](./versions/milvus-v2.6.14.md)** — Milvus 版本技术文档
- **[../../design/solution-final/020-ingestion/](../../design/solution-final/020-ingestion/)** — 向量嵌入流程
