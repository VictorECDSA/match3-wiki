# VectorDatabase Protocol

- **功能**：稠密 / 稀疏向量检索、混合检索（RRF）、向量 CRUD
- **推荐实现**：Milvus 2.6.14（客户端 pymilvus 2.6.14）
- **Runtime 字段**：`rt.vector_db: VectorDatabase`
- **错误码**：失败时抛 `Match3Exception.of_code(codes.MILVUS_ERROR, ...)` (500003)

---

## 类清单

| 类 | 文件 | 类型 |
|----|------|------|
| `VectorDatabase` | `backend/runtime/protocols/vector_db/vector_db.py` | Protocol |
| `VectorSearchResult` | `backend/runtime/protocols/vector_db/vector_search_result.py` | Protocol |

---

## VectorDatabase

```python
# backend/runtime/protocols/vector_db/vector_db.py
from typing import Protocol, Any
from backend.runtime.protocols.vector_db.vector_search_result import VectorSearchResult

class VectorDatabase(Protocol):
    """Vector database protocol (sync; hybrid dense + sparse)."""

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        filter_expr: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[VectorSearchResult]: ...

    def hybrid_search(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: dict[int, float],
        limit: int = 10,
        rrf_k: int = 60,
        filter_expr: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[VectorSearchResult]: ...

    def insert(
        self,
        collection_name: str,
        data: list[dict[str, Any]],
    ) -> list[int | str]: ...

    def delete(
        self,
        collection_name: str,
        ids: list[int | str],
    ) -> int: ...

    def close(self) -> None: ...
```

### 方法签名

| 方法 | 参数 | 返回 |
|------|------|------|
| `search` | `collection_name`, `query_vector: list[float]`, `limit: int = 10`, `filter_expr: str \| None`, `output_fields: list[str] \| None` | `list[VectorSearchResult]` |
| `hybrid_search` | 同上 + `dense_vector`, `sparse_vector: dict[int, float]`, `rrf_k: int = 60`（RRF 融合参数） | `list[VectorSearchResult]` |
| `insert` | `collection_name`, `data: list[dict]`（每条含 `id`、向量字段、其他标量） | `list[int \| str]`（主键列表） |
| `delete` | `collection_name`, `ids: list[int \| str]` | `int`，删除条数 |
| `close` | — | `None` |

### 使用约束

- **过滤表达式**使用 Milvus 的表达式字符串（如 `"workspace_id == 1 and chunk_type == 'text'"`）。业务层不得传入 pymilvus 专有对象。
- **集合管理**（创建 collection、建索引）不在 Protocol 中，由一次性脚本 `scripts/init_milvus.py` 完成。

---

## VectorSearchResult

```python
# backend/runtime/protocols/vector_db/vector_search_result.py
from typing import Protocol, Any

class VectorSearchResult(Protocol):
    @property
    def id(self) -> int | str: ...

    @property
    def distance(self) -> float: ...

    @property
    def entity(self) -> dict[str, Any]: ...
```

- `distance`：相似度分数（COSINE 越大越相似；IP 越大越相似；L2 越小越相似；实现层统一输出）。
- `entity`：`output_fields` 指定的字段映射。

---

## 使用示例

```python
# 稠密向量检索
hits = rt.vector_db.search(
    collection_name="text_chunks",
    query_vector=embedding,
    limit=20,
    filter_expr=f"workspace_id == {workspace_id}",
    output_fields=["chunk_id", "content", "raw_file_id"],
)
for h in hits:
    print(h.id, h.distance, h.entity["content"])

# 混合检索（Dense + Sparse + RRF）
hits = rt.vector_db.hybrid_search(
    collection_name="text_chunks",
    dense_vector=dense_emb,
    sparse_vector=sparse_emb,
    limit=20,
    rrf_k=60,
    filter_expr=f"workspace_id == {workspace_id}",
    output_fields=["chunk_id", "content"],
)
```

---

## 关联文档

- [implementation.md](./implementation.md) — Milvus 适配器
- [versions/milvus-v2.6.14.md](./versions/milvus-v2.6.14.md) — pymilvus 2.6 接口速查
- [../config.md](../config.md) — `runtime.vector_db.*` 配置
