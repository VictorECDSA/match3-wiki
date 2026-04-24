# DatabaseEngine 实现 — PostgreSQL 18 + SQLAlchemy 2.0.48

## 文件布局

```
backend/runtime_impl/implements/database/
├── database.py                     # create_database_engine(config, env, logger) -> DatabaseEngine
└── impl_postgresql/
    ├── postgresql_engine.py        # PostgreSQLEngine
    └── postgresql_session.py       # PostgreSQLSession
```

依赖：`SQLAlchemy` 2.0.48，驱动 `psycopg2-binary`。

---

## 工厂函数

```python
# backend/runtime_impl/implements/database/database.py
from sqlalchemy import create_engine
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.config import Config, Env
from backend.runtime.protocols.logger.logger import Logger
from backend.runtime.protocols.database.database_engine import DatabaseEngine
from backend.runtime_impl.implements.database.impl_postgresql.postgresql_engine import PostgreSQLEngine

def create_database_engine(config: Config, env: Env, logger: Logger) -> DatabaseEngine:
    provider = config.runtime.database.provider

    if provider != "postgresql":
        raise Match3Exception.of_code(
            codes.CONFIG_MISSING_REQUIRED,
            "unsupported database provider",
        ).ctx(provider=provider)

    impl = config.runtime.database.implementations.postgresql
    url = (
        f"postgresql+psycopg2://{env.POSTGRESQL_USER}:{env.POSTGRESQL_PASSWORD}"
        f"@{env.POSTGRESQL_HOST}:{env.POSTGRESQL_PORT}/{env.POSTGRESQL_DB}"
    )
    try:
        engine = create_engine(
            url,
            pool_size=impl.pool_size,
            max_overflow=impl.max_overflow,
            pool_timeout=impl.pool_timeout,
            pool_recycle=impl.pool_recycle,
            pool_pre_ping=impl.pool_pre_ping,
            echo=impl.echo,
        )
    except Exception as e:
        raise Match3Exception.of_code(codes.DB_ERROR, "failed to init postgres engine") \
            .ctx(host=env.POSTGRESQL_HOST, db=env.POSTGRESQL_DB).as_ex(e)

    logger.info(
        "postgresql engine initialized",
        pool_size=impl.pool_size, host=env.POSTGRESQL_HOST, db=env.POSTGRESQL_DB,
    )
    return PostgreSQLEngine(engine)
```

---

## 引擎适配器

```python
# backend/runtime_impl/implements/database/impl_postgresql/postgresql_engine.py
from contextlib import contextmanager
from typing import ContextManager
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.runtime.protocols.database.database_session import DatabaseSession
from backend.runtime_impl.implements.database.impl_postgresql.postgresql_session import PostgreSQLSession

class PostgreSQLEngine:
    """PostgreSQL + SQLAlchemy implementation of DatabaseEngine protocol."""

    def __init__(self, engine: Engine):
        self._engine = engine

    @contextmanager
    def session(self) -> ContextManager[DatabaseSession]:
        sa_session = Session(self._engine)
        try:
            yield PostgreSQLSession(sa_session)
            sa_session.commit()
        except Match3Exception:
            sa_session.rollback()
            raise
        except Exception as e:
            sa_session.rollback()
            raise Match3Exception.of_code(codes.DB_ERROR, "db session failed").as_ex(e)
        finally:
            sa_session.close()

    def dispose(self) -> None:
        self._engine.dispose()
```

---

## 会话适配器

```python
# backend/runtime_impl/implements/database/impl_postgresql/postgresql_session.py
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session as SASession
from app.common.exceptions import Match3Exception
from app.common.constants import codes

class PostgreSQLSession:
    """SQLAlchemy Session wrapper implementing DatabaseSession protocol."""

    def __init__(self, session: SASession):
        self._session = session

    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        try:
            stmt = text(query) if isinstance(query, str) else query
            return self._session.execute(stmt, params or {})
        except Exception as e:
            raise Match3Exception.of_code(codes.DB_ERROR, "sql execute failed") \
                .ctx(param_keys=list((params or {}).keys())).as_ex(e)

    def add(self, entity: Any) -> None:
        self._session.add(entity)

    def delete(self, entity: Any) -> None:
        self._session.delete(entity)

    def flush(self) -> None:
        try:
            self._session.flush()
        except Exception as e:
            raise Match3Exception.of_code(codes.DB_ERROR, "flush failed").as_ex(e)

    def commit(self) -> None:
        try:
            self._session.commit()
        except Exception as e:
            raise Match3Exception.of_code(codes.DB_ERROR, "commit failed").as_ex(e)

    def rollback(self) -> None:
        self._session.rollback()

    def close(self) -> None:
        self._session.close()
```

> 说明：`PostgreSQLEngine.session()` 已经提供事务边界；业务层一般用 `with rt.db.session() as s: s.add(...)` 的方式即可，无需手动 `commit()`。显式事务 API 依然保留，供需要手工控制提交点的场景使用。

---

## 配置与环境

- `config.yaml`：`runtime.database.*`
- `.env`：`POSTGRESQL_HOST`、`POSTGRESQL_PORT`、`POSTGRESQL_DB`、`POSTGRESQL_USER`、`POSTGRESQL_PASSWORD`

详见 [`../config.md`](../config.md)。

---

## 关联文档

- [protocol.md](./protocol.md) — DatabaseEngine / DatabaseSession Protocol
- [versions/sqlalchemy-v2.0.48.md](./versions/sqlalchemy-v2.0.48.md) — SQLAlchemy 2.0 接口速查
- [`../../design/solution-final/050-data-model/`](../../design/solution-final/050-data-model/) — ORM 模型与 Alembic 迁移
