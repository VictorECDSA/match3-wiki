# Runtime 代码目录结构

规则：

1. **一个类一个文件**。数据类、Protocol、实现类、异常类都不例外。
2. 文件名使用蛇形命名，与类名一一对应（`CacheStore` → `cache_store.py`，`RedisCacheStore` → `redis_cache_store.py`）。
3. **Protocol 层** (`app/runtime/protocols/`) 零外部依赖。
4. **实现层** (`app/runtime_impl/implements/`) 按 provider 分子目录（`impl_<provider>/`），一个 provider 一组文件。
5. 每个组件目录根下的 `<组件>.py` 文件只包含 `create_<组件>()` 工厂函数。
6. **不使用 `__init__.py`**：所有包均为隐式命名空间包（PEP 420），目录中不存在 `__init__.py`。

---

## Protocol 层

```
app/runtime/
├── runtime.py                              # Match3Runtime (frozen dataclass)
└── protocols/
    ├── logger/
    │   ├── logger.py                       # Logger (Protocol)
    │   └── log_config.py                   # LogConfig (dataclass)
    │
    ├── cache_store/
    │   └── cache_store.py                  # CacheStore (Protocol)
    │
    ├── message_queue/
    │   └── message_queue.py                # MessageQueue (Protocol)
    │
    ├── vector_db/
    │   ├── vector_db.py                    # VectorDatabase (Protocol)
    │   └── vector_search_result.py         # VectorSearchResult (Protocol)
    │
    ├── graph_db/
    │   ├── graph_db.py                     # GraphDatabase (Protocol)
    │   ├── graph_session.py                # GraphSession (Protocol)
    │   ├── graph_transaction.py            # GraphTransaction (Protocol)
    │   └── graph_query_result.py           # GraphQueryResult (Protocol)
    │
    ├── database/
    │   ├── database_engine.py              # DatabaseEngine (Protocol)
    │   └── database_session.py             # DatabaseSession (Protocol)
    │
    ├── fulltext_search/
    │   ├── fulltext_search.py              # FullTextSearch (Protocol)
    │   └── search_result.py                # SearchResult (Protocol)
    │
    └── object_storage/
        ├── object_storage.py               # ObjectStorage (Protocol)
        └── storage_object.py               # StorageObject (Protocol)
```

---

## 实现层

```
app/runtime_impl/
├── runtime.py                              # build_runtime()
└── implements/
    ├── logger/
    │   ├── logger.py                       # create_logger(config) -> Logger
    │   └── impl_loguru/
    │       └── loguru_logger.py            # LoguruLogger
    │
    ├── cache_store/
    │   ├── cache_store.py                  # create_cache_store(config, env, logger) -> CacheStore
    │   └── impl_redis/
    │       └── redis_cache_store.py        # RedisCacheStore
    │
    ├── message_queue/
    │   ├── message_queue.py                # create_message_queue(config, env, logger) -> MessageQueue
    │   └── impl_redis/
    │       └── redis_message_queue.py      # RedisMessageQueue
    │
    ├── vector_db/
    │   ├── vector_db.py                    # create_vector_database(config, env, logger) -> VectorDatabase
    │   └── impl_milvus/
    │       ├── milvus_vector_db.py         # MilvusVectorDatabase
    │       └── milvus_vector_search_result.py  # MilvusVectorSearchResult
    │
    ├── graph_db/
    │   ├── graph_db.py                     # create_graph_database(config, env, logger) -> GraphDatabase
    │   └── impl_neo4j/
    │       ├── neo4j_graph_db.py           # Neo4jGraphDatabase
    │       ├── neo4j_graph_session.py      # Neo4jGraphSession
    │       ├── neo4j_graph_transaction.py  # Neo4jGraphTransaction
    │       └── neo4j_graph_query_result.py # Neo4jGraphQueryResult
    │
    ├── database/
    │   ├── database.py                     # create_database_engine(config, env, logger) -> DatabaseEngine
    │   └── impl_postgresql/
    │       ├── postgresql_engine.py        # PostgreSQLEngine
    │       └── postgresql_session.py       # PostgreSQLSession
    │
    ├── fulltext_search/
    │   ├── fulltext_search.py              # create_fulltext_search(config, env, logger) -> FullTextSearch
    │   └── impl_elasticsearch/
    │       ├── elasticsearch_search.py     # ElasticsearchSearch
    │       └── elasticsearch_search_result.py  # ElasticsearchSearchResult
    │
    └── object_storage/
        ├── object_storage.py               # create_object_storage(config, env, logger) -> ObjectStorage
        └── impl_minio/
            ├── minio_object_storage.py     # MinIOObjectStorage
            └── minio_storage_object.py     # MinIOStorageObject
```

---

## 命名与导入约定

- **实现类命名**：`<Provider><Capability>`。例如 Redis 同时实现了 `CacheStore` 和 `MessageQueue`，但类名分别是 `RedisCacheStore` 与 `RedisMessageQueue`，分别位于不同的 `impl_redis/` 子目录下。
- **实现类不导出 Protocol 类型**：业务层不允许从 `runtime_impl` 导入任何符号；只能从 `app.runtime.protocols.*` 导入。
- **工厂函数只做装配**：`create_xxx()` 内部根据 `config.runtime.<组件>.provider` 分派到对应 `impl_<provider>`，不包含业务逻辑。
- **新增 provider**：新增 `impl_<new_provider>/` 子目录 + 新增类，然后在对应的 `create_xxx()` 里加一个 `elif` 分支。Protocol、Runtime、业务层均不需要改动。
