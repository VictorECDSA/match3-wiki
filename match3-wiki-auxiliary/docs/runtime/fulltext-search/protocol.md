# FullTextSearch Protocol

- **功能**：BM25 全文检索、批量索引、按条件删除
- **推荐实现**：Elasticsearch 9.3.3（客户端 elasticsearch-py 9.3）
- **Runtime 字段**：`rt.search: FullTextSearch`
- **错误码**：失败时抛 `Match3Exception.of_code(codes.ES_ERROR, ...)` (500004)

---

## 类清单

| 类 | 文件 | 类型 |
|----|------|------|
| `FullTextSearch` | `backend/runtime/protocols/fulltext_search/fulltext_search.py` | Protocol |
| `SearchResult` | `backend/runtime/protocols/fulltext_search/search_result.py` | Protocol |

---

## FullTextSearch

```python
# backend/runtime/protocols/fulltext_search/fulltext_search.py
from typing import Protocol, Any
from .search_result import SearchResult

class FullTextSearch(Protocol):
    """Full-text search engine protocol."""

    def index(
        self,
        index_name: str,
        document: dict[str, Any],
        document_id: str | None = None,
    ) -> str: ...

    def bulk_index(
        self,
        index_name: str,
        documents: list[dict[str, Any]],
    ) -> tuple[int, int]: ...

    def search(
        self,
        index_name: str,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        fields: list[str] | None = None,
    ) -> list[SearchResult]: ...

    def delete(
        self,
        index_name: str,
        document_id: str,
    ) -> bool: ...

    def delete_by_query(
        self,
        index_name: str,
        filters: dict[str, Any],
    ) -> int: ...

    def close(self) -> None: ...
```

### 方法签名

| 方法 | 参数 | 返回 |
|------|------|------|
| `index` | `index_name`, `document: dict`, `document_id: str \| None` | `str`（写入后的文档 ID；`None` 时由引擎自动生成） |
| `bulk_index` | `index_name`, `documents: list[dict]`（每条**必须**含 `_id` 字段） | `(success_count, failed_count)` |
| `search` | `index_name`, `query: str`（用户查询文本）, `limit`, `filters: dict \| None`（字段精确值过滤）, `fields: list[str] \| None`（返回字段白名单） | `list[SearchResult]` |
| `delete` | `index_name`, `document_id: str` | `bool` |
| `delete_by_query` | `index_name`, `filters: dict[str, Any]` | `int`（删除条数） |
| `close` | — | `None` |

### 使用约束

- **`query` 统一为字符串**；ES Query DSL 不得穿过 Protocol 边界。
- **`filters` 为标量字段过滤字典**（如 `{"workspace_id": 1, "chunk_type": "text"}`），由适配器翻译为引擎语法（ES 的 `term` / `terms`）。
- **索引管理**（mapping、analyzer、shard 设置）不在 Protocol，由一次性脚本 `scripts/init_es.py` 完成。

---

## SearchResult

```python
# backend/runtime/protocols/fulltext_search/search_result.py
from typing import Protocol, Any

class SearchResult(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def score(self) -> float: ...

    @property
    def source(self) -> dict[str, Any]: ...
```

- `score`：BM25 相关性分数，越大越相关。
- `source`：原始文档字段（受 `fields` 白名单裁剪）。

---

## 使用示例

```python
# 索引
doc_id = rt.search.index(
    index_name="text_chunks",
    document={"chunk_id": 42, "content": "...", "workspace_id": 1},
    document_id="42",
)

# 搜索
hits = rt.search.search(
    index_name="text_chunks",
    query="match-3 mechanics",
    limit=20,
    filters={"workspace_id": 1},
    fields=["chunk_id", "content"],
)
for h in hits:
    print(h.id, h.score, h.source["content"])

# 按 workspace 清理
rt.search.delete_by_query("text_chunks", filters={"workspace_id": 1})
```

---

## 关联文档

- [implementation.md](./implementation.md) — Elasticsearch 适配器
- [versions/elasticsearch-v9.3.3.md](./versions/elasticsearch-v9.3.3.md) — elasticsearch-py 9.3 接口速查
- [../config.md](../config.md) — `runtime.fulltext_search.*` 配置
- [`../../design/solution-final/030-rag/`](../../design/solution-final/030-rag/) — Hybrid Search 中 BM25 的角色
