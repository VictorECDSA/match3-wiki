# 项目目录结构

## 后端（FastAPI）

```
backend/
├── app/
│   ├── main.py                         # FastAPI 应用工厂——构建 Config、Env、Runtime，挂载路由
│   ├── runtime.py                      # Match3Runtime 冻结 dataclass + Protocol 接口 + build_runtime()
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config.py                   # Config（来自 config.yaml）：连接池大小、模型名称、功能开关、日志级别
│   │   └── env.py                      # Env（来自 .env）：数据库凭证、API Key、JWT 密钥——全部必填
│   │
│   ├── intelligence/                   # Runtime Protocol 接口的具体实现
│   │   ├── __init__.py
│   │   ├── llm.py                      # OpenAILLMCaller、AnthropicLLMCaller——实现 LLMCaller
│   │   ├── embedder.py                 # OpenAIEmbedder——实现 Embedder
│   │   ├── image_embedder.py           # CLIPImageEmbedder——实现 ImageEmbedder
│   │   ├── transcriber.py              # WhisperTranscriber——实现 Transcriber
│   │   ├── reranker.py                 # CrossEncoderReranker——实现 Reranker
│   │   ├── storage.py                  # MinioObjectStorage——实现 ObjectStorage
│   │   └── pageindex.py               # VectifyPageIndexClient——实现 PageIndexClient
│   │
│   ├── common/
│   │   ├── __init__.py
│   │   ├── exceptions.py               # Match3Exception（of / of_code / ctx / as_ex）
│   │   └── constants/
│   │       ├── __init__.py
│   │       ├── codes.py                # 业务码常量（SUCCESS、AUTH_FAILED 等）
│   │       └── constants.py            # 非错误码魔法常量（队列名、集合名、chunk 类型等）
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── api.py                      # register_routers(app)——挂载所有路由
│   │   ├── api_req.py                  # ApiReq[T]——带 request_id 的请求包装器
│   │   ├── api_resp.py                 # ApiResp[T]——统一响应信封
│   │   ├── api_resp_page.py            # ApiRespPage[T]——分页响应
│   │   ├── middleware.py               # JWT + RBAC + 限流中间件
│   │   │
│   │   ├── ingest/
│   │   │   ├── __init__.py
│   │   │   ├── router.py               # /api/v1/ingest 路由
│   │   │   ├── models.py               # 请求/响应 Pydantic 模型
│   │   │   └── handler.py              # 路由处理器（精简，委托给 service）
│   │   │
│   │   ├── wiki/
│   │   │   ├── __init__.py
│   │   │   ├── router.py               # /api/v1/wiki 路由
│   │   │   ├── models.py
│   │   │   └── handler.py
│   │   │
│   │   ├── qa/
│   │   │   ├── __init__.py
│   │   │   ├── router.py               # /api/v1/qa 路由（SSE）
│   │   │   ├── models.py
│   │   │   └── handler.py
│   │   │
│   │   └── admin/
│   │       ├── __init__.py
│   │       ├── router.py               # /api/v1/admin 路由
│   │       ├── models.py
│   │       └── handler.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingest_service.py           # 编排文件上传→任务入队
│   │   ├── wiki_compile_service.py     # 触发 wiki 编译任务
│   │   ├── qa_service.py               # RAG 路由→答案生成→SSE
│   │   └── admin_service.py            # 用户/工作区/权限管理
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── router.py                   # AdaptiveRAG：将查询路由至对应 path
│   │   ├── chunker.py                  # markdown_header / fixed_size chunking
│   │   │
│   │   ├── hybrid_search_engine.py     # HybridSearchEngine: config-driven 5-stage pipeline
│   │   ├── retrieval_config.py         # RetrievalConfig, RerankLevel, ValidationMode
│   │   ├── retrieval_profiles.py       # PROFILE_MAP: complexity → RetrievalConfig
│   │   ├── multi_agent.py              # multi-agent RAG (domain agents + verifier + writer)
│   │   │
│   │   ├── entry/                      # wiki-lookup: wiki compile + query
│   │   │   ├── __init__.py
│   │   │   ├── compile_pipeline.py     # 5-step OpenKB pipeline
│   │   │   └── entry_lookup.py
│   │   │
│   │   └── page/                       # doc-navigate: PageIndex long-document retrieval
│   │       ├── __init__.py
│   │       └── pageindex_retriever.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── orm_base.py                 # DeclarativeBase
│   │   ├── graph_store.py              # GraphStore（Neo4j 封装）
│   │   ├── milvus_store.py             # MilvusStore（Milvus 封装）
│   │   ├── models/                     # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py
│   │   │   ├── workspace.py
│   │   │   ├── user.py
│   │   │   ├── raw_file.py
│   │   │   ├── chunk.py
│   │   │   ├── wiki_page.py
│   │   │   ├── qa_session.py
│   │   │   └── qa_turn.py
│   │   │
│   │   └── repositories/               # Repository 模式
│   │       ├── __init__.py
│   │       ├── base_repo.py            # BaseRepository[T]，含 insert/tx_insert/find 等方法
│   │       ├── workspace_repo.py
│   │       ├── user_repo.py
│   │       ├── raw_file_repo.py
│   │       ├── chunk_repo.py
│   │       ├── wiki_page_repo.py
│   │       └── qa_repo.py
│   │
│   └── workers/
│       ├── __init__.py
│       ├── celery_app.py               # Celery 应用工厂
│       ├── ingest_task.py
│       ├── embed_task.py
│       ├── graph_task.py
│       ├── compile_task.py
│       └── rag_task.py
│
├── alembic/                            # Alembic 迁移（与 alembic.ini 同级）
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
│   ├── layout.tsx                      # 根布局（认证 Provider、侧边栏）
│   ├── page.tsx                        # 仪表盘/首页
│   │
│   ├── wiki/
│   │   ├── page.tsx                    # Wiki 列表——按主题列出所有页面
│   │   ├── [slug]/
│   │   │   └── page.tsx                # Wiki 单页查看器
│   │   └── compile/
│   │       └── page.tsx                # 触发 wiki 编译
│   │
│   ├── raw/
│   │   ├── page.tsx                    # 原始文件列表
│   │   └── upload/
│   │       └── page.tsx                # 上传并追踪摄入状态
│   │
│   ├── qa/
│   │   └── page.tsx                    # Q&A 聊天界面（SSE 流式）
│   │
│   └── admin/
│       ├── page.tsx                    # 管理员仪表盘
│       ├── users/page.tsx
│       └── workspace/page.tsx
│
├── components/
│   ├── wiki/
│   │   ├── WikiViewer.tsx              # Markdown 渲染器，含 wikilink 支持
│   │   ├── WikiEditor.tsx              # 浏览器内 wiki 编辑（可选）
│   │   └── WikiGraph.tsx              # Neo4j 图可视化
│   ├── qa/
│   │   ├── QAChat.tsx                 # 聊天 UI，含 SSE token 流式渲染
│   │   ├── QAMessage.tsx
│   │   └── SourceCitations.tsx        # 展示检索到的来源 chunk
│   ├── ingest/
│   │   ├── IngestDropzone.tsx         # 拖拽文件上传
│   │   └── IngestStatus.tsx           # 任务状态轮询
│   └── shared/
│       ├── Sidebar.tsx
│       ├── TopBar.tsx
│       └── LoadingSpinner.tsx
│
├── lib/
│   ├── api.ts                          # API 客户端（带认证的 fetch 封装）
│   ├── constants.ts                    # SUCCESS_CODES 集合、错误码、API 路径、SSE 字段名
│   ├── sse.ts                          # SSE 客户端 hook
│   └── types.ts                        # 共享 TypeScript 类型
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
├── docker-compose.yml                  # 完整本地技术栈（详见 08-deployment/）
├── docker-compose.override.yml         # 开发环境覆盖（热重载、调试端口）
├── postgres/
│   └── init.sql                        # 数据库 + 用户创建
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
├── backend/                            # FastAPI 后端
├── frontend/                           # Next.js 前端
├── docker/                             # 基础设施配置
├── scripts/
│   ├── init_db.py                      # 执行 Alembic 迁移 + 种子数据
│   ├── init_milvus.py                  # 创建集合
│   ├── init_es.py                      # 创建索引
│   ├── init_neo4j.py                   # 创建约束 + 索引
│   └── test_connections.py             # 验证所有服务可达
└── README.md
```
