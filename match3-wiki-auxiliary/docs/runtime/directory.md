# Runtime 代码目录结构

规则：

1. **一个类一个文件**。数据类、Protocol、实现类、异常类都不例外。
2. 文件名使用蛇形命名，与类名一一对应（`CacheStore` → `cache_store.py`，`RedisCacheStore` → `redis_cache_store.py`）。
3. **Protocol 层** (`backend/runtime/protocols/`) 零外部依赖。
4. **实现层** (`backend/runtime_impl/implements/`) 按 provider 分子目录（`impl_<provider>/`），一个 provider 一组文件。
5. 每个组件目录根下的 `<组件>.py` 文件只包含 `create_<组件>()` 工厂函数。

---

## Protocol 层

```
backend/runtime/
├── __init__.py
├── runtime.py                              # Match3Runtime (frozen dataclass)
└── protocols/
    ├── __init__.py
    │
    ├── logger/
    │   ├── __init__.py
    │   ├── logger.py                       # Logger (Protocol)
    │   └── log_config.py                   # LogConfig (dataclass)
    │
    ├── cache_store/
    │   ├── __init__.py
    │   └── cache_store.py                  # CacheStore (Protocol)
    │
    ├── message_queue/
    │   ├── __init__.py
    │   └── message_queue.py                # MessageQueue (Protocol)
    │
    ├── vector_db/
    │   ├── __init__.py
    │   ├── vector_db.py                    # VectorDatabase (Protocol)
    │   └── vector_search_result.py         # VectorSearchResult (Protocol)
    │
    ├── graph_db/
    │   ├── __init__.py
    │   ├── graph_db.py                     # GraphDatabase (Protocol)
    │   ├── graph_session.py                # GraphSession (Protocol)
    │   ├── graph_transaction.py            # GraphTransaction (Protocol)
    │   └── graph_query_result.py           # GraphQueryResult (Protocol)
    │
    ├── database/
    │   ├── __init__.py
    │   ├── database_engine.py              # DatabaseEngine (Protocol)
    │   └── database_session.py             # DatabaseSession (Protocol)
    │
    ├── fulltext_search/
    │   ├── __init__.py
    │   ├── fulltext_search.py              # FullTextSearch (Protocol)
    │   └── search_result.py                # SearchResult (Protocol)
    │
    └── object_storage/
        ├── __init__.py
        ├── object_storage.py               # ObjectStorage (Protocol)
        └── storage_object.py               # StorageObject (Protocol)
```

---

## 实现层

```
backend/runtime_impl/
├── __init__.py
├── runtime.py                              # build_runtime()
└── implements/
    ├── __init__.py
    │
    ├── logger/
    │   ├── __init__.py
    │   ├── logger.py                       # create_logger(config) -> Logger
    │   └── impl_loguru/
    │       ├── __init__.py
    │       └── loguru_logger.py            # LoguruLogger
    │
    ├── cache_store/
    │   ├── __init__.py
    │   ├── cache_store.py                  # create_cache_store(config, env, logger) -> CacheStore
    │   └── impl_redis/
    │       ├── __init__.py
    │       └── redis_cache_store.py        # RedisCacheStore
    │
    ├── message_queue/
    │   ├── __init__.py
    │   ├── message_queue.py                # create_message_queue(config, env, logger) -> MessageQueue
    │   └── impl_redis/
    │       ├── __init__.py
    │       └── redis_message_queue.py      # RedisMessageQueue
    │
    ├── vector_db/
    │   ├── __init__.py
    │   ├── vector_db.py                    # create_vector_database(config, env, logger) -> VectorDatabase
    │   └── impl_milvus/
    │       ├── __init__.py
    │       ├── milvus_vector_db.py         # MilvusVectorDatabase
    │       └── milvus_vector_search_result.py  # MilvusVectorSearchResult
    │
    ├── graph_db/
    │   ├── __init__.py
    │   ├── graph_db.py                     # create_graph_database(config, env, logger) -> GraphDatabase
    │   └── impl_neo4j/
    │       ├── __init__.py
    │       ├── neo4j_graph_db.py           # Neo4jGraphDatabase
    │       ├── neo4j_graph_session.py      # Neo4jGraphSession
    │       ├── neo4j_graph_transaction.py  # Neo4jGraphTransaction
    │       └── neo4j_graph_query_result.py # Neo4jGraphQueryResult
    │
    ├── database/
    │   ├── __init__.py
    │   ├── database.py                     # create_database_engine(config, env, logger) -> DatabaseEngine
    │   └── impl_postgresql/
    │       ├── __init__.py
    │       ├── postgresql_engine.py        # PostgreSQLEngine
    │       └── postgresql_session.py       # PostgreSQLSession
    │
    ├── fulltext_search/
    │   ├── __init__.py
    │   ├── fulltext_search.py              # create_fulltext_search(config, env, logger) -> FullTextSearch
    │   └── impl_elasticsearch/
    │       ├── __init__.py
    │       ├── elasticsearch_search.py     # ElasticsearchSearch
    │       └── elasticsearch_search_result.py  # ElasticsearchSearchResult
    │
    └── object_storage/
        ├── __init__.py
        ├── object_storage.py               # create_object_storage(config, env, logger) -> ObjectStorage
        └── impl_minio/
            ├── __init__.py
            ├── minio_object_storage.py     # MinIOObjectStorage
            └── minio_storage_object.py     # MinIOStorageObject
```

---

## 命名与导入约定

- **实现类命名**：`<Provider><Capability>`。例如 Redis 同时实现了 `CacheStore` 和 `MessageQueue`，但类名分别是 `RedisCacheStore` 与 `RedisMessageQueue`，分别位于不同的 `impl_redis/` 子目录下。
- **实现类不导出 Protocol 类型**：业务层不允许从 `runtime_impl` 导入任何符号；只能从 `backend.runtime.protocols.*` 导入。
- **工厂函数只做装配**：`create_xxx()` 内部根据 `config.runtime.<组件>.provider` 分派到对应 `impl_<provider>`，不包含业务逻辑。
- **新增 provider**：新增 `impl_<new_provider>/` 子目录 + 新增类，然后在对应的 `create_xxx()` 里加一个 `elif` 分支。Protocol、Runtime、业务层均不需要改动。
