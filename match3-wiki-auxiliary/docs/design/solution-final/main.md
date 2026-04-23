# match3-wiki — 方案 A：全栈自研平台
## 设计文档 — 开发者参考

---

## 概述

match3-wiki 是一个用于三消游戏研究的内部知识库平台，涵盖市场数据、游戏机制、买量素材和竞品情报。本设计文档介绍**方案 A：全栈自研平台**——一套完全基于 FastAPI + Next.js + PostgreSQL + Milvus + Elasticsearch + Neo4j 自主构建的系统。

系统支持：
- 多模态导入（PDF、图片、视频、音频、HTML、CSV、Markdown）
- 所有主流 RAG 范式（16 种方法，按 3 条检索路径组织）
- LLM 驱动的 Wiki 并行编译
- 完整的 RBAC 与工作区隔离
- **RPC 风格 API**（HTTP 状态码始终为 200，业务成功/失败通过响应体 `code` 字段区分）+ SSE 流式端点
- 前端多语言（next-intl）与多主题（next-themes + shadcn/ui）

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│  Next.js 14 (App Router)  ·  Obsidian Vault (read-only sync)   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP/SSE
┌───────────────────────────────▼─────────────────────────────────┐
│                         API LAYER                               │
│  FastAPI  ·  JWT Auth  ·  RBAC Middleware  ·  Rate Limit        │
│  /api/v1/ingest  /api/v1/wiki  /api/v1/qa  /api/v1/admin       │
└──────┬────────────────────────────────────────────┬────────────┘
       │ sync                                        │ async tasks
┌──────▼──────────────────────────┐    ┌────────────▼────────────┐
│        SERVICE LAYER            │    │     WORKER LAYER         │
│  IngestService                  │    │  Celery + Redis           │
│  WikiCompileService             │    │  ingest_task              │
│  QAService                      │    │  embed_task               │
│  AdminService                   │    │  graph_extract_task       │
└──────┬──────────────────────────┘    │  wiki_compile_task        │
       │                               └────────────┬─────────────┘
┌──────▼──────────────────────────────────────────────────────────┐
│                       STORAGE LAYER                             │
│  PostgreSQL      Milvus           Elasticsearch    Neo4j        │
│  (relational)    (vectors)        (BM25 keyword)  (graph)       │
│                                                                  │
│  MinIO (raw files)   Redis (cache + queue)                      │
└─────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                     INTELLIGENCE LAYER                          │
│  OpenAI / Anthropic / Local LLM                                 │
│  Embedding: text-embedding-3-small  ·  CLIP (images)            │
│  Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2                 │
│  PageIndex: VectifyAI API (long-doc tree navigation)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三条知识检索路径

系统根据查询类型和内容特征，将每个查询路由到以下三条检索路径之一：

| 路径 | 适用场景 | 核心技术 |
|------|----------|----------------|
| `hybrid-search` | 事实性问答、对分块语料库的语义搜索 | 混合搜索（Milvus + ES）+ 重排序 + 16 种 RAG 方法 |
| `wiki-lookup` | Wiki 页面编译与查询 | LLM 编译一次模式，结构化条目页面 |
| `doc-navigate` | 长 PDF / 文档导航（≥20 页） | PageIndex 层级目录树，无需向量 |

---

## 文档目录

```
design/
├── main.md                         ← 本文件 — 概述、导航、规范原则
│
├── toolchain-decisions.md          ← 工具选型决策（技术栈选型理由与对比）
│
├── 010-architecture/
│   ├── overview.md                 ← 系统分层、数据流、运行时配置、Config/Env
│   ├── tech-stack.md               ← 技术选型与理由
│   └── directory-structure.md      ← 完整项目目录布局
│
├── 011-flows/
│   ├── flows.md                    ← 四条核心流程总览（导入/hybrid-search/Wiki编译/doc-navigate）
│   ├── flow-1-ingestion.md         ← 流程 1：文件导入流水线时序图
│   ├── flow-2-qa-chunk.md          ← 流程 2：Q&A 问答（hybrid-search 检索路径）时序图
│   ├── flow-3-wiki-compile.md      ← 流程 3：Wiki 页面编译时序图
│   └── flow-4-pageindex.md         ← 流程 4：Q&A 问答（doc-navigate 检索路径）时序图
│
├── 020-ingestion/
│   ├── pipeline.md                 ← 端到端导入流水线（所有文件类型）
│   ├── multimodal.md               ← 图片 / 视频 / 音频 / PDF 处理
│   └── pageindex.md                ← 长文档的 PageIndex 路径
│
├── 030-rag/
│   ├── overview.md                 ← 路径选择逻辑、自适应 RAG 路由器
│   ├── path-chunk.md               ← 分块语料库上的全部 16 种 RAG 方法
│   ├── path-entry.md               ← Wiki 编译流水线（OpenKB 五步法）
│   ├── path-page.md                ← PageIndex 检索实现
│   └── multi-agent.md              ← 多智能体 RAG（并行子智能体）
│
├── 040-api/
│   ├── conventions.md              ← ApiReq / ApiResp / Match3Exception 规范 + 业务码（唯一权威）
│   ├── ingest-api.md               ← POST /ingest，任务状态端点
│   ├── wiki-api.md                 ← Wiki CRUD、编译触发
│   ├── qa-api.md                   ← Q&A SSE 流式端点
│   └── admin-api.md                ← 工作区 / 用户 / RBAC 管理
│
├── 050-database/
│   ├── schema.md                   ← PostgreSQL 表结构（ORM 模型 + DDL）
│   ├── repositories.md             ← Repository 模式实现
│   ├── milvus.md                   ← 向量集合 Schema
│   └── neo4j.md                    ← 图节点 / 关系 Schema
│
├── 060-workers/
│   ├── celery-tasks.md              ← 总览：队列布局、Celery App 配置、Worker Runtime、重试策略、孤儿状态处理
│   ├── ingestion/                   ← 原文件导入流水线（三阶段串联）
│   │   ├── ingest-task.md           ← 第一阶段：文件解析、分块、写入 PostgreSQL
│   │   ├── embed-task.md            ← 第二阶段：嵌入生成、Milvus upsert、ES index
│   │   └── graph-task.md            ← 第三阶段：LLM 实体提取、Neo4j MERGE 写入
│   ├── wiki/                        ← Wiki 编译（独立，读 chunks 写 wiki_pages）
│   │   └── compile-task.md          ← OpenKB 五步流水线、WikiPage 状态机
│   └── qa/                          ← 问答（独立，读 chunks，无持久写入）
│       └── rag-task.md              ← 多智能体 RAG：Celery chord 异步路径（可选）
│
├── 070-rbac/
│   └── permissions.md              ← 角色、能力矩阵、工作区隔离
│
├── 080-testing/
│   └── unit-tests.md               ← pytest 目录、fixture、命名约定、AI 自动化命令
│
├── 090-error/
│   └── error-design.md             ← 错误码体系、环境感知响应、结构化日志、AI 排错协议
│
├── 310-frontend/
│   └── frontend.md                 ← Next.js 前端设计（组件、国际化、主题、API 客户端、SSE）
│
└── 999-deployment/
    └── cicd.md                     ← 云服务器规格、生产 docker-compose、remote.sh 远程部署脚本
```

---

## 核心设计原则

### 后端

**1. Match3Exception 链式调用**

每个 try 块**只包裹单一调用**，捕获后立即用 `Match3Exception` 封装并附加上下文：

```python
# GOOD — one call per try block, specific context attached
try:
    result = some_external_client.call(arg)
except Exception as e:
    raise Match3Exception.of("failed to <func>").ctx(key=val).as_ex(e)

# GOOD — business rule violation uses of_code
if not workspace:
    raise Match3Exception.of_code(codes.WORKSPACE_NOT_FOUND, "workspace not found") \
        .ctx(workspace_id=workspace_id)

# BAD — broad try block hides which call failed
try:
    a = repo_a.find(id)
    b = repo_b.find(id)
except Exception as e:
    raise Match3Exception.of("something failed").as_ex(e)  # unclear origin
```

`resolve_code()` 沿 `__cause__` 链向下查找，返回**第一个非零 code**，供 API 层用于响应和前端 i18n 查表。

**2. 统一 API 信封（RPC 风格）**

所有端点返回 `ApiResp[T]` — `{requestId, code, message, data}`。HTTP 状态码**始终为 200**，业务成功/失败**只通过** `code` 字段区分：
- `SUCCESS_CODES.has(code)`（前端）/ `code in codes.SUCCESS_CODES`（后端）：成功，`data` 含业务数据
- 否则：业务错误，`data` 为 `null`，`message` 含描述

`SUCCESS_CODES` 是一个集合（`new Set([100000])`），而非单一常量比较，以便将来无需修改调用方即可扩展成功码。

SSE 端点使用 `StreamingResponse`，不经过 `ApiResp` 包装。分页列表返回 `ApiResp[ApiRespPage[T]]`。

**禁止**使用 HTTP 4xx/5xx 表示业务错误（`unhandled_exception_handler` 除外）。

**3. 业务码与常量集中管理**

- 所有业务码定义在 `app/common/constants/codes.py`（见 `040-api/conventions.md`），这是**唯一权威来源**。引用时使用 `codes.XXX`，禁止在业务代码中出现内联数字字面量。新增错误码时，同步在所有语言包中添加对应文案。
- 所有其他魔法字符串（队列名、集合名、索引名、chunk 类型、文件类型、bucket 名、Milvus 维度等）统一定义在 `app/common/constants/constants.py`。前端对应文件为 `lib/constants.ts`（含 `SUCCESS_CODES`、API 路径、SSE 字段名等）。代码中禁止出现任何内联字面量。

**4. Config / Env 严格分层**

- `config.yaml` → `Config`：**非敏感**配置（连接池大小、模型名称、功能开关、日志级别、Worker 并发数）
- `.env` → `Env`：**敏感**凭证（数据库密码、API Key、JWT Secret）

两者在 `main.py` 中构建，注入 `Match3Runtime`。业务代码通过 `rt.config.xxx` / `rt.env.XXX` 访问。**禁止**在业务代码中调用 `os.getenv()` 或引用全局实例。

**5. 无全局状态**

`Match3Runtime`（冻结数据类）在 `main.py` 中构建**一次**，注入每个服务和任务。`app.state.rt` 是 FastAPI 应用上的 Runtime 属性名。禁止创建全局单例或模块级连接对象。

**6. Runtime 只持有 Protocol 接口**

`rt.llm`、`rt.embedder`、`rt.image_embedder`、`rt.transcriber`、`rt.reranker`、`rt.storage`、`rt.pageindex` 均以 **Protocol 接口**存储，从不持有具体实现类。两个关键收益：
- 测试时直接用 `MagicMock()` 替换，无需 `@patch` 任何全局符号
- 换实现（如 OpenAI → Anthropic）只需修改 `build_runtime()`，业务代码零改动

**7. Repository 双模式**

`insert(entity)` 自动提交；`tx_insert(tx, entity)` 用于显式事务。

**8. Celery 异步优先**

导入和嵌入始终异步执行，API 立即返回任务 ID。

**9. RAG 路径选择**

`AdaptiveRAG` 路由器在运行时对查询分类，选择合适路径（`hybrid-search` / `wiki-lookup` / `doc-navigate`）。

---

### 前端

**10. API 调用统一入口**

所有对后端的调用必须经过 `lib/api.ts`，禁止在组件或 Server Action 中直接裸调 `fetch`。`lib/api.ts` 是前端与后端通信的**唯一入口**。

**11. SUCCESS_CODES 集合**

判断一个响应是否成功，前后端均使用集合，而非单值比较，以便将来新增成功码时**调用方无需改动**：

- **后端**：`code in codes.SUCCESS_CODES`（`frozenset`，定义于 `codes.py`）
- **前端**：`SUCCESS_CODES.has(code)`（`Set`，定义于 `lib/constants.ts`）

禁止使用 `== codes.SUCCESS`、`=== 100000` 等单值比较。

**12. 禁止内联魔法值**

前端所有魔法值（业务码、localStorage 键名、SSE 事件名、API 路径等）统一定义在 `lib/constants.ts`，代码中禁止出现内联字面量。

**13. 错误处理自动化**

`lib/api.ts` 统一处理所有 API 错误：
- **Toast**（sonner）：展示翻译后的用户友好文案，自动消失
- **`console.error`**：记录完整请求上下文（`method`、`url`、`body`、`code`/`httpStatus`、`requestId`、`message`），供开发者和 AI Agent 排查

业务组件通常**无需** `catch`；只有需要对特定 `code` 做特殊 UI 响应时才 catch `ApiError`。

**14. i18n 错误码即键名**

`messages/<locale>.json` 中 `error` 命名空间以**业务码字符串**为 key，`lib/api.ts` 直接用 `code` 查表，查不到时降级到 `FALLBACK_ERROR_CODE`（`500000`）对应的通用文案。

---

### 通用

**15. 文档自包含**

本目录中的每个文件都包含实现该组件所需的全部内容，无需参考外部文档。每个文件的代码示例可直接复制使用。

---

## 快速开发顺序

1. `999-deployment/cicd.md` — 参考 docker-compose 配置启动所有基础设施（本地开发）
2. `050-database/schema.md` — 创建表并运行迁移
3. `010-architecture/overview.md` + `010-architecture/directory-structure.md` — 搭建项目骨架
4. `040-api/conventions.md` — 实现共享 API 层（含 Match3Exception + 业务码）
5. `090-error/error-design.md` — 实现报错体系与结构化日志（越早越好，贯穿全程）
6. `020-ingestion/pipeline.md` — 实现导入流水线
7. `030-rag/path-chunk.md` — 实现核心 RAG（大多数查询使用此路径）
8. `030-rag/path-entry.md` — 实现 Wiki 编译
9. `030-rag/path-page.md` — 实现 PageIndex 路径
10. `040-api/qa-api.md` — 接入带 SSE 的 Q&A 端点
11. `070-rbac/permissions.md` — 添加认证与访问控制
12. `080-testing/unit-tests.md` — 补充单元测试
13. `310-frontend/frontend.md` — 实现前端
14. `999-deployment/cicd.md` — 配置云服务器与远程部署脚本
