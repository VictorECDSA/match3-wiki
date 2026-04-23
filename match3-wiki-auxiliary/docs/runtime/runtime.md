# Runtime 运行时依赖系统

**设计原则**: Protocol-based Architecture (基于协议的架构)

---

## 📁 代码目录结构

```
backend/
├── runtime/                              # Protocol 层 (抽象接口)
│   ├── runtime.py                        # Match3Runtime 定义 + build_runtime()
│   └── protocols/
│       ├── logger/
│       │   ├── __init__.py
│       │   ├── logger.py                 # Logger Protocol
│       │   └── log_config.py             # LogConfig
│       ├── cache_store/
│       │   ├── __init__.py
│       │   └── cache_store.py            # CacheStore Protocol
│       ├── message_queue/
│       │   ├── __init__.py
│       │   └── message_queue.py          # MessageQueue Protocol
│       ├── vector_db/
│       │   ├── __init__.py
│       │   ├── vector_db.py              # VectorDatabase Protocol
│       │   └── search_result.py          # VectorSearchResult Protocol
│       ├── graph_db/
│       │   ├── __init__.py
│       │   ├── graph_db.py               # GraphDatabase Protocol
│       │   ├── query_result.py           # GraphQueryResult Protocol
│       │   └── transaction.py            # GraphTransaction Protocol
│       ├── relational_db/
│       │   ├── __init__.py
│       │   └── database_engine.py        # DatabaseEngine Protocol
│       ├── fulltext_search/
│       │   ├── __init__.py
│       │   └── fulltext_search.py        # FullTextSearch Protocol
│       └── object_storage/
│           ├── __init__.py
│           └── object_storage.py         # ObjectStorage Protocol
│
└── runtime_impl/                         # 实现层 (具体实现)
    └── implements/
        ├── logger/
        │   └── impl_loguru/
        │       ├── __init__.py
        │       ├── loguru_logger.py      # LoguruLogger 实现
        │       └── logger_factory.py     # create_logger()
        ├── cache_store/
        │   └── impl_redis/
        │       ├── __init__.py
        │       └── redis_adapter.py      # Redis 实现
        ├── message_queue/
        │   └── impl_redis/
        │       ├── __init__.py
        │       └── redis_adapter.py      # Redis 实现
        ├── vector_db/
        │   └── impl_milvus/
        │       ├── __init__.py
        │       └── milvus_adapter.py     # Milvus 实现
        ├── graph_db/
        │   └── impl_neo4j/
        │       ├── __init__.py
        │       └── neo4j_adapter.py      # Neo4j 实现
        ├── relational_db/
        │   └── impl_postgresql/
        │       ├── __init__.py
        │       └── sqlalchemy_adapter.py # SQLAlchemy 实现
        ├── fulltext_search/
        │   └── impl_elasticsearch/
        │       ├── __init__.py
        │       └── es_adapter.py         # Elasticsearch 实现
        └── object_storage/
            └── impl_minio/
                ├── __init__.py
                └── minio_adapter.py      # MinIO 实现
```

---

## 🎯 职责分离

### Protocol 层 (`backend/runtime/`)

**职责**: 定义抽象接口，零外部依赖

```python
# backend/runtime/protocols/cache_store/cache_store.py
from typing import Protocol

class CacheStore(Protocol):
    """缓存存储抽象接口 (不依赖任何缓存库)"""
    
    async def get(self, key: str) -> str | None:
        """获取缓存值"""
        ...
    
    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """设置缓存值"""
        ...
```

**特点**:
- ✅ 零外部依赖 (只用 Python 标准库)
- ✅ 类型安全 (编译时检查)
- ✅ 运行时零开销

---

### 实现层 (`backend/runtime_impl/`)

**职责**: 实现 Protocol 接口，依赖第三方库

```python
# backend/runtime_impl/implements/cache_store/impl_redis/redis_adapter.py
from redis.asyncio import Redis
from backend.runtime.protocols.cache_store import CacheStore

class RedisAdapter:
    """Redis implementation of CacheStore Protocol"""
    
    def __init__(self, client: Redis):
        self._client = client
    
    async def get(self, key: str) -> str | None:
        return await self._client.get(key)
    
    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        return await self._client.set(key, value, ex=ex)
```

**特点**:
- ✅ 实现细节隔离
- ✅ 可替换 (新增 impl_memcached/ 不影响业务)
- ✅ 易于测试 (Mock Protocol 即可)

---

## 📊 依赖方向

```
业务层 (API/RAG/Celery)
    ↓ 依赖
Runtime (runtime.py + protocols/)
    ↑ 实现
实现层 (runtime_impl/implements/)
```

**关键点**:
- 业务层**只依赖** Protocol，不知道具体实现
- 实现层**实现** Protocol，不被业务层直接引用
- `build_runtime()` 负责组装具体实现

---

## 📦 Runtime 定义

### Match3Runtime 结构

```python
# backend/runtime/runtime.py
from dataclasses import dataclass
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.cache_store import CacheStore
from backend.runtime.protocols.message_queue import MessageQueue
from backend.runtime.protocols.vector_db import VectorDatabase
from backend.runtime.protocols.graph_db import GraphDatabase
from backend.runtime.protocols.relational_db import DatabaseEngine
from backend.runtime.protocols.fulltext_search import FullTextSearch
from backend.runtime.protocols.object_storage import ObjectStorage

@dataclass(frozen=True)
class Match3Runtime:
    """不可变运行时依赖容器"""
    # 配置和环境变量
    config: Config
    env: Env
    logger: Logger
    
    # 运行时依赖组件
    cache: CacheStore
    queue: MessageQueue
    vector_db: VectorDatabase
    graph_db: GraphDatabase
    db: DatabaseEngine
    search: FullTextSearch
    storage: ObjectStorage
```

---

### build_runtime() 函数

```python
# backend/runtime/runtime.py
from backend.runtime_impl.implements.logger.impl_loguru import create_logger
from backend.runtime_impl.implements.cache_store.impl_redis import build_cache_client
from backend.runtime_impl.implements.message_queue.impl_redis import build_queue_client
# ... 其他 imports

def build_runtime(config: Config, env: Env) -> Match3Runtime:
    """构建 Match3 Runtime 实例
    
    职责:
    1. 创建 Logger 实例
    2. 使用 config + env + logger 初始化各个客户端
    3. 返回不可变 Runtime 实例
    """
    # Step 1: 创建 logger
    logger = create_logger(config)
    logger.info("Building runtime...")
    
    # Step 2: 初始化各个客户端
    cache = build_cache_client(config, env, logger)
    queue = build_queue_client(config, env, logger)
    vector_db = build_vector_db_client(config, env, logger)
    graph_db = build_graph_db_client(config, env, logger)
    db = build_db_engine(config, env, logger)
    search = build_search_client(config, env, logger)
    storage = build_storage_client(config, env, logger)
    
    logger.info("Runtime built successfully")
    
    # Step 3: 返回不可变 Runtime 实例
    return Match3Runtime(
        config=config,
        env=env,
        logger=logger,
        cache=cache,
        queue=queue,
        vector_db=vector_db,
        graph_db=graph_db,
        db=db,
        search=search,
        storage=storage,
    )
```

---

### 使用方式

```python
# 业务层代码 (API/RAG/Celery)
def process_document(rt: Match3Runtime, doc_id: int):
    """处理文档 (只依赖 Protocol)"""
    # 访问配置
    max_results = rt.config.search.max_results
    
    # 记录日志
    rt.logger.info(f"Processing document {doc_id}")
    
    # 访问运行时组件
    results = rt.search.search(index_name="documents", query="test")
    
    # 缓存结果
    await rt.cache.set(f"doc:{doc_id}", results)
```

**关键点**:
- ✅ 业务代码**只依赖 Protocol**，不知道具体实现
- ✅ 切换实现（Redis → Memcached）不影响业务代码
- ✅ 单元测试直接 Mock Protocol 即可

---

## 📊 Runtime 组件

| 组件 | Protocol | 推荐实现 | 用途 |
|------|----------|---------|------|
| `logger` | `Logger` | Loguru | 应用日志记录 |
| `cache` | `CacheStore` | Redis | 会话缓存、计数器、限流 |
| `queue` | `MessageQueue` | Redis Stream | Celery Broker/Backend |
| `vector_db` | `VectorDatabase` | Milvus | 混合向量搜索 (稠密+稀疏) |
| `graph_db` | `GraphDatabase` | Neo4j | GraphRAG 知识图谱查询 |
| `db` | `DatabaseEngine` | SQLAlchemy + PostgreSQL | 关系数据访问层 |
| `search` | `FullTextSearch` | Elasticsearch | BM25 关键词检索 |
| `storage` | `ObjectStorage` | MinIO | S3 兼容对象存储 |

---

## 🔧 环境变量

```bash
# Logger
# (无环境变量，使用 config.yaml 配置)

# PostgreSQL
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DB=match3
POSTGRESQL_USER=match3_user
POSTGRESQL_PASSWORD=your_password

# Redis (Cache)
REDIS_CACHE_URL=redis://localhost:6379/0

# Redis (Message Queue)
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

---

## ⚙️ 配置参数

```yaml
# Logger
logger:
  level: INFO
  format: json
  rotation: 1 day
  retention: 7 days

# PostgreSQL
relational_db:
  provider: postgresql
  implementations:
    postgresql:
      pool_size: 10
      max_overflow: 20
      pool_timeout: 30
      pool_recycle: 3600

# Redis (Cache)
cache_store:
  provider: redis
  implementations:
    redis:
      max_connections: 50
      socket_timeout: 5

# Redis (Message Queue)
message_queue:
  provider: redis
  implementations:
    redis:
      max_connections: 50
      socket_timeout: 5

# Milvus
vector_db:
  provider: milvus
  implementations:
    milvus:
      timeout: 30
      consistency_level: Eventually

# Neo4j
graph_db:
  provider: neo4j
  implementations:
    neo4j:
      max_connection_lifetime: 3600
      max_connection_pool_size: 50

# Elasticsearch
fulltext_search:
  provider: elasticsearch
  implementations:
    elasticsearch:
      request_timeout: 30
      max_retries: 3

# MinIO
object_storage:
  provider: minio
  implementations:
    minio:
      bucket: match3-wiki-files
      secure: false
```

---

## 🏗️ 设计原则

1. **依赖反转 (DIP)**: 高层不依赖低层，都依赖抽象 (Protocol)
2. **接口隔离 (ISP)**: Protocol 小而专注，单一职责
3. **开闭原则 (OCP)**: 对扩展开放 (新增 impl_xxx/)，对修改封闭

**关键特性**:
- ✅ Protocol 层零外部依赖
- ✅ 类型安全 (编译时检查)
- ✅ 运行时零开销
- ✅ 易于测试 (Mock Protocol)
- ✅ 易于替换实现
