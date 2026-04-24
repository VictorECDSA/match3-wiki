# FullTextSearch 实现 — Elasticsearch 9.3.3

## 文件布局

```
backend/runtime_impl/implements/fulltext_search/
├── fulltext_search.py                          # create_fulltext_search(config, env, logger) -> FullTextSearch
└── impl_elasticsearch/
    ├── elasticsearch_search.py                 # ElasticsearchSearch
    └── elasticsearch_search_result.py          # ElasticsearchSearchResult
```

依赖：`elasticsearch` 9.3.x（含 `elasticsearch.helpers.bulk`）。

---

## 工厂函数

```python
# backend/runtime_impl/implements/fulltext_search/fulltext_search.py
from elasticsearch import Elasticsearch
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.config import Config, Env
from backend.runtime.protocols.logger.logger import Logger
from backend.runtime.protocols.fulltext_search.fulltext_search import FullTextSearch
from .impl_elasticsearch.elasticsearch_search import ElasticsearchSearch

def create_fulltext_search(config: Config, env: Env, logger: Logger) -> FullTextSearch:
    provider = config.runtime.fulltext_search.provider

    if provider != "elasticsearch":
        raise Match3Exception.of_code(
            codes.CONFIG_MISSING_REQUIRED,
            "unsupported fulltext_search provider",
        ).ctx(provider=provider)

    impl = config.runtime.fulltext_search.implementations.elasticsearch
    hosts = [h.strip() for h in env.ELASTICSEARCH_URL.split(",") if h.strip()]
    basic_auth = (
        (env.ELASTICSEARCH_USER, env.ELASTICSEARCH_PASSWORD)
        if env.ELASTICSEARCH_USER else None
    )
    try:
        client = Elasticsearch(
            hosts=hosts,
            basic_auth=basic_auth,
            request_timeout=impl.request_timeout,
            max_retries=impl.max_retries,
            retry_on_timeout=impl.retry_on_timeout,
            verify_certs=impl.verify_certs,
        )
        if not client.ping():
            raise RuntimeError("elasticsearch ping returned False")
    except Exception as e:
        raise Match3Exception.of_code(codes.ES_ERROR, "failed to init elasticsearch") \
            .ctx(hosts=",".join(hosts)).as_ex(e)

    logger.info("elasticsearch client initialized", hosts=",".join(hosts))
    return ElasticsearchSearch(client)
```

---

## 适配器

```python
# backend/runtime_impl/implements/fulltext_search/impl_elasticsearch/elasticsearch_search.py
from typing import Any
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from .elasticsearch_search_result import ElasticsearchSearchResult

class ElasticsearchSearch:
    """Elasticsearch implementation of FullTextSearch protocol."""

    def __init__(self, client: Elasticsearch):
        self._client = client

    def index(
        self,
        index_name: str,
        document: dict[str, Any],
        document_id: str | None = None,
    ) -> str:
        try:
            resp = self._client.index(index=index_name, document=document, id=document_id)
            return str(resp["_id"])
        except Exception as e:
            raise Match3Exception.of_code(codes.ES_ERROR, "es index failed") \
                .ctx(index=index_name, document_id=document_id).as_ex(e)

    def bulk_index(
        self,
        index_name: str,
        documents: list[dict[str, Any]],
    ) -> tuple[int, int]:
        actions = [
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": doc["_id"],
                "_source": {k: v for k, v in doc.items() if k != "_id"},
            }
            for doc in documents
        ]
        try:
            success, errors = bulk(self._client, actions, raise_on_error=False)
        except Exception as e:
            raise Match3Exception.of_code(codes.ES_ERROR, "es bulk index failed") \
                .ctx(index=index_name, doc_count=len(documents)).as_ex(e)
        failed = len(errors) if isinstance(errors, list) else 0
        return success, failed

    def search(
        self,
        index_name: str,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        fields: list[str] | None = None,
    ) -> list[ElasticsearchSearchResult]:
        must = [{"multi_match": {"query": query, "fields": ["content^2", "title"]}}]
        filter_clauses = [{"term": {k: v}} for k, v in (filters or {}).items()]
        body = {
            "query": {"bool": {"must": must, "filter": filter_clauses}},
            "size": limit,
        }
        if fields is not None:
            body["_source"] = fields

        try:
            resp = self._client.search(index=index_name, body=body)
        except Exception as e:
            raise Match3Exception.of_code(codes.ES_ERROR, "es search failed") \
                .ctx(index=index_name, limit=limit).as_ex(e)

        return [ElasticsearchSearchResult(hit) for hit in resp["hits"]["hits"]]

    def delete(
        self,
        index_name: str,
        document_id: str,
    ) -> bool:
        try:
            resp = self._client.delete(index=index_name, id=document_id, ignore=[404])
        except Exception as e:
            raise Match3Exception.of_code(codes.ES_ERROR, "es delete failed") \
                .ctx(index=index_name, document_id=document_id).as_ex(e)
        return resp.get("result") == "deleted"

    def delete_by_query(
        self,
        index_name: str,
        filters: dict[str, Any],
    ) -> int:
        body = {"query": {"bool": {"filter": [{"term": {k: v}} for k, v in filters.items()]}}}
        try:
            resp = self._client.delete_by_query(index=index_name, body=body, refresh=True)
        except Exception as e:
            raise Match3Exception.of_code(codes.ES_ERROR, "es delete_by_query failed") \
                .ctx(index=index_name, filter_keys=list(filters.keys())).as_ex(e)
        return int(resp.get("deleted", 0))

    def close(self) -> None:
        self._client.close()
```

---

## 搜索结果

```python
# backend/runtime_impl/implements/fulltext_search/impl_elasticsearch/elasticsearch_search_result.py
from typing import Any

class ElasticsearchSearchResult:
    """Wraps one ES hit as SearchResult protocol."""

    def __init__(self, hit: dict[str, Any]):
        self._hit = hit

    @property
    def id(self) -> str:
        return str(self._hit["_id"])

    @property
    def score(self) -> float:
        return float(self._hit.get("_score") or 0.0)

    @property
    def source(self) -> dict[str, Any]:
        return dict(self._hit.get("_source", {}))
```

---

## 配置与环境

- `config.yaml`：`runtime.fulltext_search.*`
- `.env`：`ELASTICSEARCH_URL`、`ELASTICSEARCH_USER`、`ELASTICSEARCH_PASSWORD`

详见 [`../config.md`](../config.md)。

---

## 关联文档

- [protocol.md](./protocol.md) — FullTextSearch / SearchResult Protocol
- [versions/elasticsearch-v9.3.3.md](./versions/elasticsearch-v9.3.3.md) — elasticsearch-py 9.3 接口速查
- [`../../design/solution-final/030-rag/`](../../design/solution-final/030-rag/) — Hybrid Search 中 BM25 的角色
