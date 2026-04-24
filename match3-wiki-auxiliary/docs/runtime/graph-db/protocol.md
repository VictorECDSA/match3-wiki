# GraphDatabase Protocol

- **功能**：知识图谱存储与 Cypher 查询（GraphRAG）
- **推荐实现**：Neo4j 2026.03.1（驱动 neo4j-python-driver 5.28+）
- **Runtime 字段**：`rt.graph_db: GraphDatabase`
- **错误码**：失败时抛 `Match3Exception.of_code(codes.NEO4J_ERROR, ...)` (500005)

---

## 类清单

| 类 | 文件 | 类型 |
|----|------|------|
| `GraphDatabase` | `backend/runtime/protocols/graph_db/graph_db.py` | Protocol |
| `GraphSession` | `backend/runtime/protocols/graph_db/graph_session.py` | Protocol |
| `GraphTransaction` | `backend/runtime/protocols/graph_db/graph_transaction.py` | Protocol |
| `GraphQueryResult` | `backend/runtime/protocols/graph_db/graph_query_result.py` | Protocol |

---

## GraphDatabase

```python
# backend/runtime/protocols/graph_db/graph_db.py
from typing import Protocol, ContextManager
from backend.runtime.protocols.graph_db.graph_session import GraphSession

class GraphDatabase(Protocol):
    """Graph database driver protocol."""

    def session(self, database: str | None = None) -> ContextManager[GraphSession]: ...

    def close(self) -> None: ...
```

| 方法 | 参数 | 返回 |
|------|------|------|
| `session` | `database: str \| None`（为 `None` 时使用默认数据库） | `ContextManager[GraphSession]`，退出时自动关闭 |
| `close` | — | `None`，关闭驱动连接池 |

---

## GraphSession

```python
# backend/runtime/protocols/graph_db/graph_session.py
from typing import Protocol, Any
from backend.runtime.protocols.graph_db.graph_transaction import GraphTransaction
from backend.runtime.protocols.graph_db.graph_query_result import GraphQueryResult

class GraphSession(Protocol):
    """Graph session protocol."""

    def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[GraphQueryResult]: ...

    def begin_transaction(self) -> GraphTransaction: ...

    def close(self) -> None: ...
```

- `run()`：自动提交模式，单语句执行。
- `begin_transaction()`：开启显式事务，由调用方 `commit()` / `rollback()`。

---

## GraphTransaction

```python
# backend/runtime/protocols/graph_db/graph_transaction.py
from typing import Protocol, Any
from backend.runtime.protocols.graph_db.graph_query_result import GraphQueryResult

class GraphTransaction(Protocol):
    """Explicit Cypher transaction."""

    def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[GraphQueryResult]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
```

---

## GraphQueryResult

```python
# backend/runtime/protocols/graph_db/graph_query_result.py
from typing import Protocol, Any

class GraphQueryResult(Protocol):
    """Single record from a Cypher query."""

    def get(self, key: str, default: Any = None) -> Any: ...

    def data(self) -> dict[str, Any]: ...
```

- `get(key)`：按字段名取值，缺失返回 `default`。
- `data()`：整条记录转 `dict`。

---

## 使用示例

```python
# 自动提交
with rt.graph_db.session() as s:
    rows = s.run(
        "MATCH (e:Entity {name: $name})-[:RELATES_TO]->(r) RETURN r.name AS name",
        parameters={"name": "Match3"},
    )
    names = [r.get("name") for r in rows]

# 显式事务（批量写入）
with rt.graph_db.session() as s:
    tx = s.begin_transaction()
    try:
        for e in entities:
            tx.run("MERGE (:Entity {name: $name})", parameters={"name": e})
        tx.commit()
    except Exception as err:
        tx.rollback()
        raise Match3Exception.of_code(codes.NEO4J_ERROR, "graph batch write failed") \
            .ctx(entity_count=len(entities)).as_ex(err)
```

---

## 关联文档

- [implementation.md](./implementation.md) — Neo4j 适配器
- [versions/neo4j-v2026.03.1.md](./versions/neo4j-v2026.03.1.md) — neo4j-python-driver 5.28 接口速查
- [../config.md](../config.md) — `runtime.graph_db.*` 配置
