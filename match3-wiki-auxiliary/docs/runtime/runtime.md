# Runtime 运行时依赖系统

## 概述

Runtime 是 Match3 Wiki 的基础设施抽象层,采用 **Protocol-based Architecture** 设计模式,为业务层提供统一的依赖注入接口。通过协议层与实现层的分离,实现了高内聚、低耦合、易测试的架构。

**核心优势**:
- Protocol 层零外部依赖,类型安全
- 实现层可替换,不影响业务代码
- 业务层只依赖抽象,便于单元测试

---

## 🏗️ 设计原则

### 架构理念

基于 SOLID (Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, Dependency Inversion) 原则的 Protocol-based Architecture:

1. **依赖反转 (DIP)**: 业务层与实现层都依赖 Protocol 抽象,高层不依赖低层
2. **接口隔离 (ISP)**: 每个 Protocol 小而专注,单一职责
3. **开闭原则 (OCP)**: 对扩展开放(新增 `impl_xxx/`),对修改封闭

### 依赖方向

```
业务层 (API/RAG/Celery)
    ↓ 依赖
Runtime (runtime.py + protocols/)
    ↑ 实现
实现层 (runtime_impl/implements/)
```

**核心约定**:
- 业务层**只依赖** Protocol,不感知具体实现
- 实现层**实现** Protocol,不被业务层直接引用
- `build_runtime()` 在启动时完成依赖组装

---

## 📦 Runtime 定义

### Match3Runtime 容器

Runtime 是一个**不可变的依赖容器**,持有所有基础设施组件的 Protocol 接口:

```python
# backend/runtime/runtime.py
from dataclasses import dataclass
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
    """不可变运行时依赖容器"""
    config: Config           # 配置对象
    env: Env                # 环境变量
    logger: Logger          # 日志记录器
    cache: CacheStore       # 缓存存储
    queue: MessageQueue     # 消息队列
    vector_db: VectorDatabase  # 向量数据库
    graph_db: GraphDatabase    # 图数据库
    db: DatabaseEngine         # 关系数据库
    search: FullTextSearch     # 全文搜索
    storage: ObjectStorage     # 对象存储
```

### Runtime 组件列表

| 组件 | Protocol | 推荐实现 | 用途 | 配置路径 |
|------|----------|---------|------|---------|
| `logger` | `Logger` | Loguru | 结构化日志记录 (⚠️ 不由 Runtime 创建) | N/A |
| `cache` | `CacheStore` | Redis | 会话缓存、计数器、限流 | `config.runtime.cache_store` |
| `queue` | `MessageQueue` | Redis Stream | Celery Broker/Backend | `config.runtime.message_queue` |
| `vector_db` | `VectorDatabase` | Milvus | 混合向量搜索(稠密+稀疏) | `config.runtime.vector_db` |
| `graph_db` | `GraphDatabase` | Neo4j | GraphRAG 知识图谱查询 | `config.runtime.graph_db` |
| `db` | `DatabaseEngine` | PostgreSQL | 关系数据访问层 | `config.runtime.database` |
| `search` | `FullTextSearch` | Elasticsearch | BM25 关键词检索 | `config.runtime.fulltext_search` |
| `storage` | `ObjectStorage` | MinIO | S3 兼容对象存储 | `config.runtime.object_storage` |

---

## 🚀 使用方式

### 统一工厂函数规范

每个 Runtime 组件都通过 `create_xxx` 工厂函数创建，该函数：
- **命名规范**：统一使用 `create_` 前缀（如 `create_cache_store`, `create_database_engine`）
- **参数签名**：`(config: Config, env: Env, logger: Logger)` 三参数
- **返回类型**：返回实现了对应 Protocol 的具体实例
- **职责**：根据 `config.runtime.组件名.provider` 自动选择具体实现

**⚠️ 重要**: Logger 不属于 Runtime 管理范围，在调用 `build_runtime()` 之前由业务层自行创建。

**示例签名**：
```python
def create_cache_store(config: Config, env: Env, logger: Logger) -> CacheStore:
    """创建缓存存储实例，根据 provider 自动选择实现"""
    provider = config.runtime.cache_store.provider
    
    if provider == "redis":
        # 创建 Redis 实现
        return RedisAdapter(...)
    else:
        raise ValueError(f"Unsupported cache_store provider: {provider}")
```

### 构建 Runtime

通过 `build_runtime()` 函数在应用启动时初始化：

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
    """构建 Match3 Runtime 实例
    
    执行流程:
    1. 接收业务层创建的 Logger
    2. 使用统一的 create_xxx 工厂函数初始化各个组件
    3. 返回不可变 Runtime 容器
    
    Args:
        config: 配置对象
        env: 环境变量
        logger: 日志记录器 (由业务层在调用前创建)
    
    Returns:
        完整的 Runtime 实例
    """
    logger.info("Building runtime...")
    
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

### 业务层使用示例

业务代码通过依赖注入接收 `Match3Runtime`,只依赖 Protocol 接口:

```python
# 应用启动入口 (如 FastAPI startup)
from backend.config import load_config
from backend.env import load_env
from backend.runtime_impl.implements.logger.logger import create_logger
from backend.runtime_impl.runtime import build_runtime

# 初始化流程
config = load_config("config.yaml")
env = load_env()
logger = create_logger(config)  # Logger 在 Runtime 外创建
runtime = build_runtime(config, env, logger)  # 传入 logger

# 业务层代码 (API/RAG/Celery)
async def process_document(rt: Match3Runtime, doc_id: int):
    """处理文档 (只依赖 Protocol)"""
    # 访问配置
    max_results = rt.config.runtime.fulltext_search.max_results
    
    # 记录日志
    rt.logger.info(f"Processing document {doc_id}")
    
    # 全文搜索
    results = await rt.search.search(index_name="documents", query="test")
    
    # 缓存结果
    await rt.cache.set(f"doc:{doc_id}", json.dumps(results), ex=3600)
    
    # 向量检索
    vectors = await rt.vector_db.search(
        collection="docs",
        vector=embedding,
        limit=max_results
    )
```

**优势**:
- ✅ 业务代码不感知具体实现(Redis/Memcached/本地缓存)
- ✅ 切换实现只需修改 `build_runtime()`,业务代码零改动
- ✅ 单元测试直接 Mock Protocol 即可,无需启动真实服务

---

## 📊 Protocol 与实现层

### Protocol 层职责

定义抽象接口,**零外部依赖**(只使用 Python 标准库):

```python
# backend/runtime/protocols/cache_store/cache_store.py
from typing import Protocol

class CacheStore(Protocol):
    """缓存存储抽象接口"""
    
    async def get(self, key: str) -> str | None:
        """获取缓存值"""
        ...
    
    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """设置缓存值,可选过期时间(秒)"""
        ...
    
    async def delete(self, key: str) -> bool:
        """删除缓存键"""
        ...
```

**特点**:
- ✅ 类型安全,编译时检查
- ✅ 运行时零开销(无虚表)
- ✅ IDE 友好,自动补全和类型提示

### 实现层职责

实现 Protocol 接口,依赖第三方库:

```python
# backend/runtime_impl/implements/cache_store/impl_redis/redis_adapter.py
from redis.asyncio import Redis
from backend.runtime.protocols.cache_store import CacheStore

class RedisAdapter:
    """Redis implementation of CacheStore Protocol"""
    
    def __init__(self, client: Redis):
        self._client = client
    
    async def get(self, key: str) -> str | None:
        result = await self._client.get(key)
        return result.decode() if result else None
    
    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        return await self._client.set(key, value, ex=ex)
    
    async def delete(self, key: str) -> bool:
        return await self._client.delete(key) > 0
```

**特点**:
- ✅ 实现细节完全隔离
- ✅ 可无缝替换(新增 `impl_memcached/` 不影响业务)
- ✅ 实现层可独立测试

---

## ⚙️ 配置与环境变量

### 配置文件结构

所有 Runtime 组件配置统一在 `config.yaml` 的 `runtime` 节点下:

```yaml
runtime:
  # Logger 配置
  logger:
    level: INFO                # 日志级别: DEBUG/INFO/WARNING/ERROR
    format: json              # 格式: json/text
    rotation: 1 day           # 轮转周期
    retention: 7 days         # 保留时长

  # PostgreSQL 配置
  database:
    provider: postgresql      # 实现类型
    implementations:
      postgresql:
        pool_size: 10         # 连接池大小
        max_overflow: 20      # 最大溢出连接数
        pool_timeout: 30      # 连接超时(秒)
        pool_recycle: 3600    # 连接回收时间(秒)

  # Redis Cache 配置
  cache_store:
    provider: redis
    implementations:
      redis:
        max_connections: 50   # 最大连接数
        socket_timeout: 5     # Socket 超时(秒)

  # Redis Message Queue 配置
  message_queue:
    provider: redis
    implementations:
      redis:
        max_connections: 50
        socket_timeout: 5

  # Milvus 配置
  vector_db:
    provider: milvus
    implementations:
      milvus:
        timeout: 30           # 请求超时(秒)
        consistency_level: Eventually  # 一致性级别

  # Neo4j 配置
  graph_db:
    provider: neo4j
    implementations:
      neo4j:
        max_connection_lifetime: 3600  # 连接生命周期(秒)
        max_connection_pool_size: 50   # 连接池大小

  # Elasticsearch 配置
  fulltext_search:
    provider: elasticsearch
    implementations:
      elasticsearch:
        request_timeout: 30   # 请求超时(秒)
        max_retries: 3       # 最大重试次数

  # MinIO 配置
  object_storage:
    provider: minio
    implementations:
      minio:
        bucket: match3-wiki-files  # 默认 bucket
        secure: false              # 是否使用 HTTPS
```

### 环境变量列表

敏感信息(连接串、密码)通过环境变量注入:

```bash
# PostgreSQL
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DB=match3
POSTGRESQL_USER=match3_user
POSTGRESQL_PASSWORD=your_password

# Redis (Cache)
REDIS_CACHE_URL=redis://localhost:6379/0

# Redis (Message Queue - Celery)
REDIS_BROKER_URL=redis://localhost:6379/1
REDIS_RESULT_URL=redis://localhost:6379/2

# Milvus
MILVUS_URI=http://localhost:19530

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Elasticsearch
ELASTICSEARCH_URL=http://localhost:9200

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

**注意**: Logger 不由 Runtime 管理，配置方式由业务层决定。

---

## 📁 代码目录结构

```
backend/
├── runtime/
│   ├── runtime.py                        # Match3Runtime 容器定义
│   └── protocols/
│       ├── logger/
│       │   ├── logger.py                 # Logger Protocol
│       │   └── log_config.py             # LogConfig 数据类
│       ├── cache_store/
│       │   └── cache_store.py            # CacheStore Protocol
│       ├── message_queue/
│       │   └── message_queue.py          # MessageQueue Protocol
│       ├── vector_db/
│       │   ├── vector_db.py              # VectorDatabase Protocol
│       │   └── search_result.py          # VectorSearchResult 数据类
│       ├── graph_db/
│       │   ├── graph_db.py               # GraphDatabase Protocol
│       │   ├── query_result.py           # GraphQueryResult 数据类
│       │   └── transaction.py            # GraphTransaction Protocol
│       ├── database/
│       │   └── database_engine.py        # DatabaseEngine Protocol
│       ├── fulltext_search/
│       │   └── fulltext_search.py        # FullTextSearch Protocol
│       └── object_storage/
│           └── object_storage.py         # ObjectStorage Protocol
│
└── runtime_impl/
    ├── runtime.py                        # build_runtime() 定义
    └── implements/
        ├── logger/
        │   ├── logger.py                 # create_logger(config)
        │   └── impl_loguru/
        │       └── loguru_logger.py      # LoguruLogger 实现
        ├── cache_store/
        │   ├── cache_store.py            # create_cache_store(config, env, logger)
        │   └── impl_redis/
        │       └── redis_adapter.py      # RedisAdapter 实现
        ├── message_queue/
        │   ├── message_queue.py          # create_message_queue(config, env, logger)
        │   └── impl_redis/
        │       └── redis_adapter.py      # RedisMessageQueue 实现
        ├── vector_db/
        │   ├── vector_db.py              # create_vector_database(config, env, logger)
        │   └── impl_milvus/
        │       └── milvus_adapter.py     # MilvusAdapter 实现
        ├── graph_db/
        │   ├── graph_db.py               # create_graph_database(config, env, logger)
        │   └── impl_neo4j/
        │       └── neo4j_adapter.py      # Neo4jAdapter 实现
        ├── database/
        │   ├── database.py               # create_database_engine(config, env, logger)
        │   └── impl_postgresql/
        │       └── postgresql_adapter.py # PostgreSQLEngine 实现
        ├── fulltext_search/
        │   ├── fulltext_search.py        # create_fulltext_search(config, env, logger)
        │   └── impl_elasticsearch/
        │       └── es_adapter.py         # ElasticsearchAdapter 实现
        └── object_storage/
            ├── object_storage.py         # create_object_storage(config, env, logger)
            └── impl_minio/
                └── minio_adapter.py      # MinIOAdapter 实现
```
