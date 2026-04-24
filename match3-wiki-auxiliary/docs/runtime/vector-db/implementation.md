# VectorDatabase 实现 — Milvus 2.6.14

## 文件布局

```
backend/runtime_impl/implements/vector_db/
├── vector_db.py                            # create_vector_database(config, env, logger) -> VectorDatabase
└── impl_milvus/
    ├── milvus_vector_db.py                 # MilvusVectorDatabase
    └── milvus_vector_search_result.py      # MilvusVectorSearchResult
```

依赖：`pymilvus` 2.6.14+。

---

## 工厂函数

```python
# backend/runtime_impl/implements/vector_db/vector_db.py
from pymilvus import MilvusClient
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.config import Config, Env
from backend.runtime.protocols.logger.logger import Logger
from backend.runtime.protocols.vector_db.vector_db import VectorDatabase
from .impl_milvus.milvus_vector_db import MilvusVectorDatabase

def create_vector_database(config: Config, env: Env, logger: Logger) -> VectorDatabase:
    provider = config.runtime.vector_db.provider

    if provider != "milvus":
        raise Match3Exception.of_code(
            codes.CONFIG_MISSING_REQUIRED,
            "unsupported vector_db provider",
        ).ctx(provider=provider)

    impl = config.runtime.vector_db.implementations.milvus
    try:
        client = MilvusClient(
            uri=env.MILVUS_URI,
            token=env.MILVUS_TOKEN or None,
            timeout=impl.timeout,
        )
    except Exception as e:
        raise Match3Exception.of_code(codes.MILVUS_ERROR, "failed to init milvus") \
            .ctx(uri=env.MILVUS_URI).as_ex(e)

    logger.info("milvus client initialized", uri=env.MILVUS_URI)
    return MilvusVectorDatabase(client, consistency_level=impl.consistency_level)
```

---

## 适配器

```python
# backend/runtime_impl/implements/vector_db/impl_milvus/milvus_vector_db.py
from typing import Any
from pymilvus import MilvusClient, AnnSearchRequest, RRFRanker
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from .milvus_vector_search_result import MilvusVectorSearchResult

class MilvusVectorDatabase:
    """Milvus implementation of VectorDatabase protocol."""

    def __init__(self, client: MilvusClient, consistency_level: str):
        self._client = client
        self._consistency_level = consistency_level

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        filter_expr: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[MilvusVectorSearchResult]:
        try:
            raw = self._client.search(
                collection_name=collection_name,
                data=[query_vector],
                anns_field="dense_vector",
                limit=limit,
                filter=filter_expr or "",
                output_fields=output_fields,
                consistency_level=self._consistency_level,
            )
        except Exception as e:
            raise Match3Exception.of_code(codes.MILVUS_ERROR, "milvus search failed") \
                .ctx(collection=collection_name, limit=limit).as_ex(e)
        return [MilvusVectorSearchResult(hit) for hit in raw[0]]

    def hybrid_search(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: dict[int, float],
        limit: int = 10,
        rrf_k: int = 60,
        filter_expr: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[MilvusVectorSearchResult]:
        dense_req = AnnSearchRequest(
            data=[dense_vector],
            anns_field="dense_vector",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=limit * 2,
            expr=filter_expr,
        )
        sparse_req = AnnSearchRequest(
            data=[sparse_vector],
            anns_field="sparse_vector",
            param={"metric_type": "IP"},
            limit=limit * 2,
            expr=filter_expr,
        )
        try:
            raw = self._client.hybrid_search(
                collection_name=collection_name,
                reqs=[dense_req, sparse_req],
                ranker=RRFRanker(k=rrf_k),
                limit=limit,
                output_fields=output_fields,
                consistency_level=self._consistency_level,
            )
        except Exception as e:
            raise Match3Exception.of_code(codes.MILVUS_ERROR, "milvus hybrid search failed") \
                .ctx(collection=collection_name, limit=limit, rrf_k=rrf_k).as_ex(e)
        return [MilvusVectorSearchResult(hit) for hit in raw[0]]

    def insert(
        self,
        collection_name: str,
        data: list[dict[str, Any]],
    ) -> list[int | str]:
        try:
            result = self._client.insert(collection_name=collection_name, data=data)
        except Exception as e:
            raise Match3Exception.of_code(codes.MILVUS_ERROR, "milvus insert failed") \
                .ctx(collection=collection_name, count=len(data)).as_ex(e)
        return list(result.get("ids", []))

    def delete(
        self,
        collection_name: str,
        ids: list[int | str],
    ) -> int:
        try:
            result = self._client.delete(collection_name=collection_name, ids=ids)
        except Exception as e:
            raise Match3Exception.of_code(codes.MILVUS_ERROR, "milvus delete failed") \
                .ctx(collection=collection_name, count=len(ids)).as_ex(e)
        return int(result.get("delete_count", 0))

    def close(self) -> None:
        self._client.close()
```

---

## 搜索结果

```python
# backend/runtime_impl/implements/vector_db/impl_milvus/milvus_vector_search_result.py
from typing import Any

class MilvusVectorSearchResult:
    """Wraps one pymilvus Hit as VectorSearchResult protocol."""

    def __init__(self, hit: Any):
        self._hit = hit

    @property
    def id(self) -> int | str:
        return self._hit["id"]

    @property
    def distance(self) -> float:
        return float(self._hit["distance"])

    @property
    def entity(self) -> dict[str, Any]:
        return dict(self._hit.get("entity", {}))
```

---

## 配置与环境

- `config.yaml`：`runtime.vector_db.*`
- `.env`：`MILVUS_URI`、`MILVUS_TOKEN`

详见 [`../config.md`](../config.md)。

---

## 关联文档

- [protocol.md](./protocol.md) — VectorDatabase / VectorSearchResult Protocol
- [versions/milvus-v2.6.14.md](./versions/milvus-v2.6.14.md) — pymilvus 2.6 接口速查
- [`../../design/solution-final/020-ingestion/`](../../design/solution-final/020-ingestion/) — 向量嵌入与集合 schema 定义
