# DatabaseEngine Protocol

- **功能**：关系型数据库访问（连接池 + 事务 + SQL 执行）
- **推荐实现**：PostgreSQL 18 + SQLAlchemy 2.0.48（驱动 psycopg2）
- **Runtime 字段**：`rt.db: DatabaseEngine`
- **错误码**：失败时抛 `Match3Exception.of_code(codes.DB_ERROR, ...)` (500001)

---

## 类清单

| 类 | 文件 | 类型 |
|----|------|------|
| `DatabaseEngine` | `backend/runtime/protocols/database/database_engine.py` | Protocol |
| `DatabaseSession` | `backend/runtime/protocols/database/database_session.py` | Protocol |

---

## DatabaseEngine

```python
# backend/runtime/protocols/database/database_engine.py
from typing import Protocol, ContextManager
from .database_session import DatabaseSession

class DatabaseEngine(Protocol):
    """Relational database engine protocol."""

    def session(self) -> ContextManager[DatabaseSession]: ...

    def dispose(self) -> None: ...
```

| 方法 | 参数 | 返回 |
|------|------|------|
| `session` | — | `ContextManager[DatabaseSession]`，正常退出 `commit`，异常退出 `rollback`，最后自动 `close` |
| `dispose` | — | `None`，释放底层连接池 |

---

## DatabaseSession

```python
# backend/runtime/protocols/database/database_session.py
from typing import Protocol, Any

class DatabaseSession(Protocol):
    """Unit-of-work session protocol."""

    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> Any: ...

    def add(self, entity: Any) -> None: ...

    def delete(self, entity: Any) -> None: ...

    def flush(self) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...
```

### 方法签名

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `execute` | `query: str`（SQL 文本或表达式）, `params: dict \| None` | 驱动原生 `Result` | 参数用 `:name` 占位符绑定 |
| `add` | `entity: Any` | `None` | 将 ORM 对象加入 UoW |
| `delete` | `entity: Any` | `None` | 标记删除 |
| `flush` | — | `None` | 写入但不提交事务 |
| `commit` / `rollback` | — | `None` | 事务控制 |
| `close` | — | `None` | 释放会话 |

### 使用约束

- **禁止返回驱动专用类型穿越业务边界**：业务层不得依赖 `sqlalchemy.Result` 的类型，需要结果时通过 ORM 实体或显式字典返回。
- **ORM 模型**定义在 `backend/app/storage/models/` 下（详见 `design/solution-final/010-architecture/directory-structure.md`）。
- **`session()` 上下文管理器** 必须是业务代码访问数据库的唯一入口。

---

## 使用示例

```python
from sqlalchemy import text

# 原生 SQL
with rt.db.session() as s:
    result = s.execute(
        text("SELECT id, name FROM workspaces WHERE id = :wid"),
        {"wid": workspace_id},
    )
    row = result.first()

# ORM 插入（单一 UoW 内自动提交）
with rt.db.session() as s:
    workspace = Workspace(name=name, owner_id=owner_id)
    s.add(workspace)
    # 退出 with：commit 成功；异常自动 rollback

# 错误包装
try:
    with rt.db.session() as s:
        s.execute(text("UPDATE ..."), params)
except Exception as e:
    raise Match3Exception.of_code(codes.DB_ERROR, "update failed") \
        .ctx(workspace_id=workspace_id).as_ex(e)
```

---

## 关联文档

- [implementation.md](./implementation.md) — PostgreSQL + SQLAlchemy 适配器
- [versions/sqlalchemy-v2.0.48.md](./versions/sqlalchemy-v2.0.48.md) — SQLAlchemy 2.0 接口速查
- [../config.md](../config.md) — `runtime.database.*` 配置
- [`../../design/solution-final/050-data-model/`](../../design/solution-final/050-data-model/) — ORM 模型与 Alembic 迁移
