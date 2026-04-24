# GraphDatabase 实现 — Neo4j 2026.03.1

## 文件布局

```
backend/runtime_impl/implements/graph_db/
├── graph_db.py                             # create_graph_database(config, env, logger) -> GraphDatabase
└── impl_neo4j/
    ├── neo4j_graph_db.py                   # Neo4jGraphDatabase
    ├── neo4j_graph_session.py              # Neo4jGraphSession
    ├── neo4j_graph_transaction.py          # Neo4jGraphTransaction
    └── neo4j_graph_query_result.py         # Neo4jGraphQueryResult
```

依赖：`neo4j` 5.28+ (Python driver)。可选安装 `neo4j-rust-ext` 提升 3–10 倍性能。

---

## 工厂函数

```python
# backend/runtime_impl/implements/graph_db/graph_db.py
from neo4j import GraphDatabase as Neo4jDriver
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.config import Config, Env
from backend.runtime.protocols.logger.logger import Logger
from backend.runtime.protocols.graph_db.graph_db import GraphDatabase
from .impl_neo4j.neo4j_graph_db import Neo4jGraphDatabase

def create_graph_database(config: Config, env: Env, logger: Logger) -> GraphDatabase:
    provider = config.runtime.graph_db.provider

    if provider != "neo4j":
        raise Match3Exception.of_code(
            codes.CONFIG_MISSING_REQUIRED,
            "unsupported graph_db provider",
        ).ctx(provider=provider)

    impl = config.runtime.graph_db.implementations.neo4j
    try:
        driver = Neo4jDriver.driver(
            env.NEO4J_URI,
            auth=(env.NEO4J_USER, env.NEO4J_PASSWORD),
            max_connection_lifetime=impl.max_connection_lifetime,
            max_connection_pool_size=impl.max_connection_pool_size,
            connection_acquisition_timeout=impl.connection_acquisition_timeout,
        )
        driver.verify_connectivity()
    except Exception as e:
        raise Match3Exception.of_code(codes.NEO4J_ERROR, "failed to init neo4j") \
            .ctx(uri=env.NEO4J_URI, user=env.NEO4J_USER).as_ex(e)

    logger.info("neo4j driver initialized", uri=env.NEO4J_URI)
    return Neo4jGraphDatabase(driver, default_database=impl.default_database)
```

---

## 驱动适配器

```python
# backend/runtime_impl/implements/graph_db/impl_neo4j/neo4j_graph_db.py
from contextlib import contextmanager
from typing import ContextManager
from neo4j import Driver
from backend.runtime.protocols.graph_db.graph_session import GraphSession
from .neo4j_graph_session import Neo4jGraphSession

class Neo4jGraphDatabase:
    """Neo4j implementation of GraphDatabase protocol."""

    def __init__(self, driver: Driver, default_database: str):
        self._driver = driver
        self._default_database = default_database

    @contextmanager
    def session(self, database: str | None = None) -> ContextManager[GraphSession]:
        raw = self._driver.session(database=database or self._default_database)
        try:
            yield Neo4jGraphSession(raw)
        finally:
            raw.close()

    def close(self) -> None:
        self._driver.close()
```

---

## 会话适配器

```python
# backend/runtime_impl/implements/graph_db/impl_neo4j/neo4j_graph_session.py
from typing import Any
from neo4j import Session as Neo4jSession
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.runtime.protocols.graph_db.graph_transaction import GraphTransaction
from backend.runtime.protocols.graph_db.graph_query_result import GraphQueryResult
from .neo4j_graph_transaction import Neo4jGraphTransaction
from .neo4j_graph_query_result import Neo4jGraphQueryResult

class Neo4jGraphSession:
    """Wraps neo4j.Session as GraphSession protocol."""

    def __init__(self, session: Neo4jSession):
        self._session = session

    def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[GraphQueryResult]:
        try:
            result = self._session.run(query, parameters or {})
            return [Neo4jGraphQueryResult(r) for r in result]
        except Exception as e:
            raise Match3Exception.of_code(codes.NEO4J_ERROR, "cypher run failed") \
                .ctx(param_keys=list((parameters or {}).keys())).as_ex(e)

    def begin_transaction(self) -> GraphTransaction:
        try:
            tx = self._session.begin_transaction()
        except Exception as e:
            raise Match3Exception.of_code(codes.NEO4J_ERROR, "begin tx failed").as_ex(e)
        return Neo4jGraphTransaction(tx)

    def close(self) -> None:
        self._session.close()
```

---

## 事务适配器

```python
# backend/runtime_impl/implements/graph_db/impl_neo4j/neo4j_graph_transaction.py
from typing import Any
from neo4j import Transaction as Neo4jTx
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.runtime.protocols.graph_db.graph_query_result import GraphQueryResult
from .neo4j_graph_query_result import Neo4jGraphQueryResult

class Neo4jGraphTransaction:
    """Wraps neo4j.Transaction as GraphTransaction protocol."""

    def __init__(self, tx: Neo4jTx):
        self._tx = tx

    def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[GraphQueryResult]:
        try:
            result = self._tx.run(query, parameters or {})
            return [Neo4jGraphQueryResult(r) for r in result]
        except Exception as e:
            raise Match3Exception.of_code(codes.NEO4J_ERROR, "cypher run failed in tx") \
                .ctx(param_keys=list((parameters or {}).keys())).as_ex(e)

    def commit(self) -> None:
        try:
            self._tx.commit()
        except Exception as e:
            raise Match3Exception.of_code(codes.NEO4J_ERROR, "commit tx failed").as_ex(e)

    def rollback(self) -> None:
        try:
            self._tx.rollback()
        except Exception as e:
            raise Match3Exception.of_code(codes.NEO4J_ERROR, "rollback tx failed").as_ex(e)
```

---

## 查询结果

```python
# backend/runtime_impl/implements/graph_db/impl_neo4j/neo4j_graph_query_result.py
from typing import Any
from neo4j import Record

class Neo4jGraphQueryResult:
    """Wraps neo4j.Record as GraphQueryResult protocol."""

    def __init__(self, record: Record):
        self._record = record

    def get(self, key: str, default: Any = None) -> Any:
        return self._record.get(key, default)

    def data(self) -> dict[str, Any]:
        return dict(self._record)
```

---

## 配置与环境

- `config.yaml`：`runtime.graph_db.*`
- `.env`：`NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD`

详见 [`../config.md`](../config.md)。

---

## 关联文档

- [protocol.md](./protocol.md) — GraphDatabase 系列 Protocol
- [versions/neo4j-v2026.03.1.md](./versions/neo4j-v2026.03.1.md) — Neo4j 5.28 Python driver 接口速查
- [`../../design/solution-final/030-rag/`](../../design/solution-final/030-rag/) — GraphRAG 使用方式
