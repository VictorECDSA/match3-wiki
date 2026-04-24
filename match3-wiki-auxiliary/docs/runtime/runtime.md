# Runtime 运行时依赖系统

Runtime 是 Match3 Wiki 的基础设施抽象层，采用 **Protocol-based Architecture**：业务层只依赖 `typing.Protocol` 抽象接口，实现层在启动时通过 `build_runtime()` 注入。

> 相关文档：
> - [config.md](./config.md) — `config.yaml` 与 `.env` 的完整字段列表
> - [directory.md](./directory.md) — `backend/runtime/` 与 `backend/runtime_impl/` 的代码目录结构
> - 各组件的 `protocol.md` 与 `implementation.md`（见下表）
> - 报错规范：[`../design/solution-final/090-error/error-design.md`](../design/solution-final/090-error/error-design.md)

---

## 设计原则

基于 SOLID（Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, Dependency Inversion）：

- **DIP**：业务层与实现层都依赖 `Protocol` 抽象；高层不依赖低层。
- **ISP**：每个 Protocol 只暴露一个能力域的最小方法集；一个类一个文件。
- **OCP**：新增实现只需新增 `impl_xxx/` 目录，不改 Protocol，不改业务代码。
- **SRP**：`CacheStore` 与 `MessageQueue` 底层都是 Redis，但能力语义不同，接口也必须分离。

依赖方向：

```
业务层 (api / services / rag / workers)
    │ 依赖
    ▼
Protocol 层 (backend/runtime/protocols/)
    ▲ 实现
    │
实现层 (backend/runtime_impl/implements/)
```

约束：
- **Protocol 层**零外部依赖，只用标准库 + `typing.Protocol`。
- **实现层**可自由依赖第三方库（`sqlalchemy`、`redis`、`pymilvus` 等），但不得被业务层直接 import。
- `build_runtime()` 在应用启动时一次性完成装配，运行时 Runtime 不可变。

---

## Match3Runtime 容器

`Match3Runtime` 是 `frozen dataclass`，字段全部为 Protocol 类型：

```python
# backend/runtime/runtime.py
from dataclasses import dataclass
from backend.config import Config
from backend.env import Env
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.cache_store import CacheStore
from backend.runtime.protocols.message_queue import MessageQueue
from backend.runtime.protocols.vector_db import VectorDatabase
from backend.runtime.protocols.graph_db import GraphDatabase
from backend.runtime.protocols.database import DatabaseEngine
from backend.runtime.protocols.fulltext_search import FullTextSearch
from backend.runtime.protocols.object_storage import ObjectStorage

@dataclass(frozen=True)
class Match3Runtime:
    config: Config
    env: Env
    logger: Logger
    cache: CacheStore
    queue: MessageQueue
    vector_db: VectorDatabase
    graph_db: GraphDatabase
    db: DatabaseEngine
    search: FullTextSearch
    storage: ObjectStorage
```

### 组件清单

| 字段 | Protocol | 推荐实现 | 用途 |
|------|----------|---------|------|
| `logger` | `Logger` | Loguru 0.7.3 | 结构化日志（⚠️ 在 `build_runtime()` 之前由业务层创建） |
| `cache` | `CacheStore` | Redis 8.6.2 | 会话缓存、计数器、限流 |
| `queue` | `MessageQueue` | Redis 8.6.2 | Celery Broker/Backend、任务队列 |
| `vector_db` | `VectorDatabase` | Milvus 2.6.14 | 稠密+稀疏混合向量检索 |
| `graph_db` | `GraphDatabase` | Neo4j 2026.03.1 | GraphRAG 知识图谱 |
| `db` | `DatabaseEngine` | PostgreSQL 18 + SQLAlchemy 2.0.48 | 关系数据访问 |
| `search` | `FullTextSearch` | Elasticsearch 9.3.3 | BM25 关键词检索 |
| `storage` | `ObjectStorage` | MinIO RELEASE.2025-10-15 | S3 兼容对象存储 |

每个组件的详细接口与实现：

| 组件 | Protocol 文档 | 实现文档 |
|------|---------------|----------|
| Logger | [logger/protocol.md](./logger/protocol.md) | [logger/implementation.md](./logger/implementation.md) |
| CacheStore | [cache-store/protocol.md](./cache-store/protocol.md) | [cache-store/implementation.md](./cache-store/implementation.md) |
| MessageQueue | [message-queue/protocol.md](./message-queue/protocol.md) | [message-queue/implementation.md](./message-queue/implementation.md) |
| VectorDatabase | [vector-db/protocol.md](./vector-db/protocol.md) | [vector-db/implementation.md](./vector-db/implementation.md) |
| GraphDatabase | [graph-db/protocol.md](./graph-db/protocol.md) | [graph-db/implementation.md](./graph-db/implementation.md) |
| DatabaseEngine | [database/protocol.md](./database/protocol.md) | [database/implementation.md](./database/implementation.md) |
| FullTextSearch | [fulltext-search/protocol.md](./fulltext-search/protocol.md) | [fulltext-search/implementation.md](./fulltext-search/implementation.md) |
| ObjectStorage | [object-storage/protocol.md](./object-storage/protocol.md) | [object-storage/implementation.md](./object-storage/implementation.md) |

---

## 构建 Runtime

### 工厂函数规范

每个组件对应一个 `create_xxx(config, env, logger) -> XxxProtocol` 工厂函数：

- **命名**：`create_` 前缀，函数名与组件字段名一致（`create_cache_store`、`create_database_engine` 等）。
- **签名**：`(config: Config, env: Env, logger: Logger) -> <Protocol>`。Logger 例外，签名为 `create_logger(config: Config) -> Logger`。
- **职责**：读取 `config.runtime.<组件>.provider`，创建对应 `impl_xxx` 适配器，注入 `config` 中该 provider 的参数与 `env` 中的连接凭证。
- **失败**：provider 不支持或初始化异常时用 `Match3Exception` 包装（见下方「报错」节）。

### build_runtime()

```python
# backend/runtime_impl/runtime.py
from backend.runtime.runtime import Match3Runtime
from backend.config import Config
from backend.env import Env
from backend.runtime.protocols.logger import Logger

from .implements.cache_store.cache_store import create_cache_store
from .implements.message_queue.message_queue import create_message_queue
from .implements.vector_db.vector_db import create_vector_database
from .implements.graph_db.graph_db import create_graph_database
from .implements.database.database import create_database_engine
from .implements.fulltext_search.fulltext_search import create_fulltext_search
from .implements.object_storage.object_storage import create_object_storage

def build_runtime(config: Config, env: Env, logger: Logger) -> Match3Runtime:
    logger.info("Building runtime")
    return Match3Runtime(
        config=config,
        env=env,
        logger=logger,
        cache=create_cache_store(config, env, logger),
        queue=create_message_queue(config, env, logger),
        vector_db=create_vector_database(config, env, logger),
        graph_db=create_graph_database(config, env, logger),
        db=create_database_engine(config, env, logger),
        search=create_fulltext_search(config, env, logger),
        storage=create_object_storage(config, env, logger),
    )
```

### 应用启动流程

```python
# backend/app/main.py
from backend.config import load_config
from backend.env import load_env
from backend.runtime_impl.implements.logger.logger import create_logger
from backend.runtime_impl.runtime import build_runtime

config = load_config("config.yaml")      # 严格校验，缺字段直接抛 Match3Exception
env = load_env()                          # 加载 .env，缺必填项直接抛 Match3Exception
logger = create_logger(config)           # Logger 在 Runtime 之外创建
runtime = build_runtime(config, env, logger)
```

---

## Protocol 层与实现层

### Protocol 层

`typing.Protocol` 声明抽象接口，零外部依赖；一个类一个文件（详见 [directory.md](./directory.md)）。示例：

```python
# backend/runtime/protocols/cache_store/cache_store.py
from typing import Protocol

class CacheStore(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ex: int | None = None) -> bool: ...
    async def delete(self, *keys: str) -> int: ...
```

### 实现层

实现 Protocol 接口；一个适配器一个文件；类名格式 `<Provider><Capability>`（如 `RedisCacheStore`、`PostgreSQLEngine`）。

```python
# backend/runtime_impl/implements/cache_store/impl_redis/redis_cache_store.py
from redis.asyncio import Redis
from backend.runtime.protocols.cache_store.cache_store import CacheStore

class RedisCacheStore:
    """Redis implementation of CacheStore protocol"""

    def __init__(self, client: Redis):
        self._client = client

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        return bool(await self._client.set(key, value, ex=ex))

    async def delete(self, *keys: str) -> int:
        return await self._client.delete(*keys)
```

### 业务层使用

业务代码只通过 `rt: Match3Runtime` 访问依赖：

```python
async def get_cached_profile(rt: Match3Runtime, user_id: int) -> dict | None:
    cached = await rt.cache.get(f"user:{user_id}")
    return json.loads(cached) if cached else None
```

单元测试直接 Mock Protocol，不启动真实服务。

---

## 报错规范

所有 Runtime 组件的错误必须遵循 [`error-design.md`](../design/solution-final/090-error/error-design.md)：

1. **每个 try 只包裹单一调用**，捕获后用 `Match3Exception.of(...).ctx(...).as_ex(e)` 链式包装。
2. **已知业务错误**使用 `Match3Exception.of_code(codes.<CODE>, ...)`，错误码取自 `app/common/constants/codes.py`。
3. **Runtime 组件对应的错误码**：

   | 组件 | 错误码 | 常量 |
   |------|--------|------|
   | DatabaseEngine | 500001 | `codes.DB_ERROR` |
   | CacheStore (Redis) | 500002 | `codes.REDIS_ERROR` |
   | MessageQueue (Redis) | 500002 | `codes.REDIS_ERROR` |
   | VectorDatabase (Milvus) | 500003 | `codes.MILVUS_ERROR` |
   | FullTextSearch (ES) | 500004 | `codes.ES_ERROR` |
   | GraphDatabase (Neo4j) | 500005 | `codes.NEO4J_ERROR` |
   | ObjectStorage (MinIO) | 500006 | `codes.MINIO_ERROR` |

4. **工厂函数的 provider 校验失败**使用 `codes.CONFIG_MISSING_REQUIRED (400011)`。
5. **`.ctx()` 键使用蛇形命名**，值为标量；集合只传长度。

统一的失败包装示例（在实现层的适配器方法中）：

```python
from app.common.exceptions import Match3Exception
from app.common.constants import codes

async def get(self, key: str) -> str | None:
    try:
        return await self._client.get(key)
    except Exception as e:
        raise Match3Exception.of_code(codes.REDIS_ERROR, "redis get failed") \
            .ctx(key=key).as_ex(e)
```
