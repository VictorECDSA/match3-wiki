# 项目目录结构

## 后端（FastAPI）

```
backend/
├── app/
│   ├── cli/
│   │   ├── __main__.py                     # python -m app.cli entry point
│   │   ├── api.py                          # Start FastAPI: load Config/Env, build_runtime(), mount routers
│   │   └── worker.py                       # Start Celery worker for specified queue
│   │
│   ├── runtime/
│   │   ├── runtime.py                      # Match3Runtime (frozen dataclass, all fields are Protocol types)
│   │   └── protocols/
│   │       ├── logger/
│   │       │   ├── logger.py               # Logger (Protocol)
│   │       │   └── log_config.py           # LogConfig (dataclass)
│   │       ├── cache_store/
│   │       │   └── cache_store.py          # CacheStore (Protocol)
│   │       ├── message_queue/
│   │       │   └── message_queue.py        # MessageQueue (Protocol)
│   │       ├── vector_db/
│   │       │   ├── vector_db.py            # VectorDatabase (Protocol)
│   │       │   └── vector_search_result.py # VectorSearchResult (Protocol)
│   │       ├── graph_db/
│   │       │   ├── graph_db.py             # GraphDatabase (Protocol)
│   │       │   ├── graph_session.py        # GraphSession (Protocol)
│   │       │   ├── graph_transaction.py    # GraphTransaction (Protocol)
│   │       │   └── graph_query_result.py   # GraphQueryResult (Protocol)
│   │       ├── database/
│   │       │   ├── database_engine.py      # DatabaseEngine (Protocol)
│   │       │   └── database_session.py     # DatabaseSession (Protocol)
│   │       ├── fulltext_search/
│   │       │   ├── fulltext_search.py      # FullTextSearch (Protocol)
│   │       │   └── search_result.py        # SearchResult (Protocol)
│   │       └── object_storage/
│   │           ├── object_storage.py       # ObjectStorage (Protocol)
│   │           └── storage_object.py       # StorageObject (Protocol)
│   │
│   ├── runtime_impl/
│   │   ├── runtime.py                      # build_runtime(config, env, logger) -> Match3Runtime
│   │   └── implements/
│   │       ├── logger/
│   │       │   ├── logger.py               # create_logger(config) -> Logger
│   │       │   └── impl_loguru/
│   │       │       └── loguru_logger.py    # LoguruLogger
│   │       ├── cache_store/
│   │       │   ├── cache_store.py          # create_cache_store(config, env, logger) -> CacheStore
│   │       │   └── impl_redis/
│   │       │       └── redis_cache_store.py
│   │       ├── message_queue/
│   │       │   ├── message_queue.py        # create_message_queue(config, env, logger) -> MessageQueue
│   │       │   └── impl_redis/
│   │       │       └── redis_message_queue.py
│   │       ├── vector_db/
│   │       │   ├── vector_db.py            # create_vector_database(...) -> VectorDatabase
│   │       │   └── impl_milvus/
│   │       │       ├── milvus_vector_db.py
│   │       │       └── milvus_vector_search_result.py
│   │       ├── graph_db/
│   │       │   ├── graph_db.py             # create_graph_database(...) -> GraphDatabase
│   │       │   └── impl_neo4j/
│   │       │       ├── neo4j_graph_db.py
│   │       │       ├── neo4j_graph_session.py
│   │       │       ├── neo4j_graph_transaction.py
│   │       │       └── neo4j_graph_query_result.py
│   │       ├── database/
│   │       │   ├── database.py             # create_database_engine(...) -> DatabaseEngine
│   │       │   └── impl_postgresql/
│   │       │       ├── postgresql_engine.py
│   │       │       └── postgresql_session.py
│   │       ├── fulltext_search/
│   │       │   ├── fulltext_search.py      # create_fulltext_search(...) -> FullTextSearch
│   │       │   └── impl_elasticsearch/
│   │       │       ├── elasticsearch_search.py
│   │       │       └── elasticsearch_search_result.py
│   │       └── object_storage/
│   │           ├── object_storage.py       # create_object_storage(...) -> ObjectStorage
│   │           └── impl_minio/
│   │               ├── minio_object_storage.py
│   │               └── minio_storage_object.py
│   │
│   ├── config/
│   │   ├── config.py                       # Config (from config.yaml): pool sizes, model names, feature flags
│   │   └── env.py                          # Env (from .env): DB credentials, API keys, JWT secret — all required
│   │
│   ├── intelligence/                       # Intelligence layer implementations (LLM, Embedder, Reranker, etc.)
│   │   ├── llm.py                          # OpenAILLMCaller, AnthropicLLMCaller
│   │   ├── embedder.py                     # OpenAIEmbedder (Dense + BGE-M3 Sparse)
│   │   ├── image_embedder.py               # CLIPImageEmbedder
│   │   ├── transcriber.py                  # WhisperTranscriber
│   │   ├── reranker.py                     # CrossEncoderReranker
│   │   └── pageindex.py                    # VectifyPageIndexClient
│   │
│   ├── common/
│   │   ├── exceptions.py                   # Match3Exception (of / of_code / ctx / as_ex)
│   │   └── constants/
│   │       ├── codes.py                    # Business code constants (SUCCESS, AUTH_FAILED, etc.)
│   │       └── constants.py                # Non-error-code magic constants (queue names, collection names, chunk types, etc.)
│   │
│   ├── api/
│   │   ├── api.py                          # register_routers(app) — mount all routers
│   │   ├── api_req.py                      # ApiReq[T] — request wrapper with request_id
│   │   ├── api_resp.py                     # ApiResp[T] — unified response envelope
│   │   ├── api_resp_page.py                # ApiRespPage[T] — paginated response
│   │   ├── middleware.py                   # JWT + RBAC + rate-limit middleware
│   │   ├── ingest/
│   │   │   ├── router.py                   # /api/v1/ingest routes
│   │   │   ├── models.py                   # Request/response Pydantic models
│   │   │   └── handler.py                  # Route handlers (thin, delegates to service)
│   │   ├── wiki/
│   │   │   ├── router.py                   # /api/v1/wiki routes
│   │   │   ├── models.py
│   │   │   └── handler.py
│   │   ├── qa/
│   │   │   ├── router.py                   # /api/v1/qa routes (SSE)
│   │   │   ├── models.py
│   │   │   └── handler.py
│   │   └── admin/
│   │       ├── router.py                   # /api/v1/admin routes
│   │       ├── models.py
│   │       └── handler.py
│   │
│   ├── services/
│   │   ├── ingest_service.py               # Orchestrate file upload → task enqueue
│   │   ├── wiki_compile_service.py         # Trigger wiki compilation task
│   │   ├── qa_service.py                   # RAG routing → answer generation → SSE
│   │   └── admin_service.py                # User / workspace / permission management
│   │
│   ├── rag/
│   │   ├── router.py                       # AdaptiveRAGRouter: route query to appropriate path
│   │   ├── chunker.py                      # semantic_chunk(): semantic chunking (fixed-size fallback)
│   │   ├── hybrid_search_engine.py         # HybridSearchEngine: config-driven five-stage retrieval pipeline
│   │   ├── retrieval_config.py             # RetrievalConfig, RerankLevel, ValidationMode
│   │   ├── retrieval_profiles.py           # PROFILE_MAP: complexity → RetrievalConfig
│   │   ├── multi_agent.py                  # Multi-agent RAG (domain agents + validator + writer)
│   │   ├── entry/                          # wiki-lookup: entry lookup + wiki compilation
│   │   │   ├── compile_pipeline.py         # OpenKB five-step compilation pipeline
│   │   │   └── entry_lookup.py
│   │   └── page/                           # doc-navigate: PageIndex long-document retrieval
│   │       └── pageindex_retriever.py
│   │
│   ├── storage/
│   │   ├── orm_base.py                     # DeclarativeBase
│   │   ├── graph_store.py                  # GraphStore (Neo4j wrapper)
│   │   ├── milvus_store.py                 # MilvusStore (Milvus wrapper)
│   │   ├── models/                         # SQLAlchemy ORM models
│   │   │   ├── workspace.py
│   │   │   ├── user.py
│   │   │   ├── raw_file.py
│   │   │   ├── chunk.py
│   │   │   ├── wiki_page.py
│   │   │   ├── qa_session.py
│   │   │   └── qa_turn.py
│   │   └── repositories/                   # Repository pattern
│   │       ├── base_repo.py                # BaseRepository[T] with insert/tx_insert/find etc.
│   │       ├── workspace_repo.py
│   │       ├── user_repo.py
│   │       ├── raw_file_repo.py
│   │       ├── chunk_repo.py
│   │       ├── wiki_page_repo.py
│   │       └── qa_repo.py
│   │
│   └── workers/
│       ├── celery_app.py                   # Celery application factory
│       ├── ingest_task.py
│       ├── embed_task.py
│       ├── graph_task.py
│       ├── compile_task.py
│       └── rag_task.py
│
├── tests/
│   ├── unit/                               # Unit tests (pure Mock, no real services started)
│   └── integration/                        # Integration tests
│
├── alembic/                                # Alembic migrations (same level as alembic.ini)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
│
├── alembic.ini
├── pyproject.toml
├── Dockerfile
└── .env.example
```

---

## 前端（Next.js 14）

```
frontend/
├── app/
│   ├── layout.tsx                      # Root layout (auth Provider, sidebar)
│   ├── page.tsx                        # Dashboard / home page
│   │
│   ├── wiki/
│   │   ├── page.tsx                    # Wiki list — all pages listed by topic
│   │   ├── [slug]/
│   │   │   └── page.tsx                # Single wiki page viewer
│   │   └── compile/
│   │       └── page.tsx                # Trigger wiki compilation
│   │
│   ├── raw/
│   │   ├── page.tsx                    # Raw file list
│   │   └── upload/
│   │       └── page.tsx                # Upload and track ingest status
│   │
│   ├── qa/
│   │   └── page.tsx                    # Q&A chat interface (SSE streaming)
│   │
│   └── admin/
│       ├── page.tsx                    # Admin dashboard
│       ├── users/page.tsx
│       └── workspace/page.tsx
│
├── components/
│   ├── wiki/
│   │   ├── WikiViewer.tsx              # Markdown renderer with wikilink support
│   │   ├── WikiEditor.tsx              # In-browser wiki editing (optional)
│   │   └── WikiGraph.tsx              # Neo4j graph visualisation
│   ├── qa/
│   │   ├── QAChat.tsx                 # Chat UI with SSE token streaming
│   │   ├── QAMessage.tsx
│   │   └── SourceCitations.tsx        # Display retrieved source chunks
│   ├── ingest/
│   │   ├── IngestDropzone.tsx         # Drag-and-drop file upload
│   │   └── IngestStatus.tsx           # Task status polling
│   └── shared/
│       ├── Sidebar.tsx
│       ├── TopBar.tsx
│       └── LoadingSpinner.tsx
│
├── lib/
│   ├── api.ts                          # API client (authenticated fetch wrapper)
│   ├── constants.ts                    # SUCCESS_CODES set, error codes, API paths, SSE field names
│   ├── sse.ts                          # SSE client hook
│   └── types.ts                        # Shared TypeScript types
│
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── Dockerfile
```

---

## 基础设施

```
docker/
├── docker-compose.yml                  # Full local stack (see 08-deployment/)
├── docker-compose.override.yml         # Dev environment overrides (hot-reload, debug ports)
├── postgres/
│   └── init.sql                        # Database + user creation
├── milvus/
│   └── standalone.yaml
├── elasticsearch/
│   └── elasticsearch.yml
└── neo4j/
    └── neo4j.conf
```

---

## 根目录布局

```
match3-wiki/
├── backend/                            # FastAPI backend
├── frontend/                           # Next.js frontend
├── docker/                             # Infrastructure configuration
├── scripts/
│   ├── init_db.py                      # Run Alembic migrations + seed data
│   ├── init_milvus.py                  # Create collections
│   ├── init_es.py                      # Create indices
│   ├── init_neo4j.py                   # Create constraints + indices
│   └── test_connections.py             # Verify all services are reachable
└── README.md
```
