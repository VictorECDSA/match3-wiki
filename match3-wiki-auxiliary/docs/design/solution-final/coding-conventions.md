# 编码规范

本文汇总所有必须遵守的编码约定。**本目录中每个代码块均须符合这些规范。**

---

## 后端

### 1. Match3Exception 链式调用

每个 try 块**只包裹单一调用**，捕获后立即用 `Match3Exception` 封装并附加上下文：

```python
# correct — each try wraps a single call with explicit context
try:
    result = some_external_client.call(arg)
except Exception as e:
    raise Match3Exception.of("failed to <func>").ctx(key=val).as_ex(e)

# correct — business rule violation uses of_code
if not workspace:
    raise Match3Exception.of_code(codes.WORKSPACE_NOT_FOUND, "workspace not found") \
        .ctx(workspace_id=workspace_id)

# wrong — broad try block hides which call failed
try:
    a = repo_a.find(id)
    b = repo_b.find(id)
except Exception as e:
    raise Match3Exception.of("something failed").as_ex(e)  # origin unclear
```

`resolve_code()` 沿 `__cause__` 链向下查找，返回**第一个非零 code**，供 API 层用于响应和前端 i18n 查表。

### 2. 统一 API 信封（RPC 风格）

所有端点返回 `ApiResp[T]` — `{requestId, code, message, data}`。HTTP 状态码**始终为 200**，业务成功/失败**只通过** `code` 字段区分：

- 后端判断成功：`code in codes.SUCCESS_CODES`（集合成员判断，见原则 3）
- 前端判断成功：`SUCCESS_CODES.has(code)`（集合而非单值，见原则 12）
- 否则：业务错误，`data` 为 `null`，`message` 含描述

SSE 端点使用 `StreamingResponse`，不经过 `ApiResp` 包装。分页列表返回 `ApiResp[ApiRespPage[T]]`。

**禁止**使用 HTTP 4xx/5xx 表示业务错误（`unhandled_exception_handler` 除外）。

### 3. 业务码集中管理 — `codes.py`

所有业务码定义在 `app/common/constants/codes.py`，这是**唯一权威来源**。引用时使用 `codes.XXX`，**禁止**在代码中写 `100000`、`404001` 等内联数字字面量。完整码值表见 `090-error/error-design.md` 第一节。

判断成功时，使用 `codes.SUCCESS_CODES`（`frozenset`）而非单值比较，以便将来新增成功码时**调用方无需改动**：

```python
from app.common.constants import codes

# correct — set membership; adding a second success code only requires changing codes.py
if result_code in codes.SUCCESS_CODES:
    ...
raise Match3Exception.of_code(codes.WORKSPACE_NOT_FOUND, "workspace not found")

# wrong — single-value constant; breaks if a second success code is added later
if result_code == codes.SUCCESS: ...

# wrong — inline numeric literal, forbidden
if result_code == 100000: ...
```

### 4. 其他常量集中管理 — `constants.py`

所有其他后端魔法字符串（队列名、集合名、索引名、chunk 类型、文件类型、bucket 名等）统一定义在 `app/common/constants/constants.py`，**禁止**在代码中写 `"ingest"`、`"match3_chunks"` 等内联字符串字面量：

```python
# app/common/constants/constants.py

# Celery queue names
QUEUE_INGEST  = "ingest"
QUEUE_EMBED   = "embed"
QUEUE_GRAPH   = "graph"
QUEUE_COMPILE = "compile"
QUEUE_RAG     = "rag"

# chunk types
CHUNK_TYPE_TEXT           = "text"
CHUNK_TYPE_IMAGE          = "image"
CHUNK_TYPE_TABLE          = "table"

# file types
FILE_TYPE_PDF      = "pdf"
FILE_TYPE_IMAGE    = "image"
FILE_TYPE_VIDEO    = "video"
FILE_TYPE_AUDIO    = "audio"
FILE_TYPE_HTML     = "html"
FILE_TYPE_CSV      = "csv"
FILE_TYPE_MARKDOWN = "markdown"

# MinIO bucket
MINIO_BUCKET_RAW = "raw-files"

# Milvus collections and dimensions
MILVUS_COLLECTION        = "match3_chunks"    # text chunk collection
MILVUS_COLLECTION_IMAGES = "image_chunks"     # CLIP image chunk collection
MILVUS_DENSE_DIM         = 1536               # text-embedding-3-small output dim
MILVUS_SPARSE_DIM        = 250002             # BGE-M3 sparse vocab size
MILVUS_IMAGE_DIM         = 768                # CLIP ViT-L/14 output dim

# Elasticsearch indexes
ES_INDEX_CHUNKS = "text_chunks"
ES_INDEX_WIKI   = "wiki_pages"
```

需要新常量时先加到这里，再在其他地方引用。**禁止**导入后重新导出子集——始终直接引用原始来源。

### 5. Config / Env 严格分层

- `config.yaml` → `Config`：**非敏感**配置（连接池大小、模型名称、功能开关、日志级别、Worker 并发数）
- `.env` → `Env`：**敏感**凭证（数据库密码、API Key、JWT Secret）

两者在 `main.py` 中构建，注入 `Match3Runtime`。业务代码通过 `rt.config.xxx` / `rt.env.XXX` 访问。**禁止**在业务代码中调用 `os.getenv()` 或引用全局实例。

### 6. 无全局状态

`Match3Runtime`（冻结数据类）在 `main.py` 中构建**一次**，注入每个服务和任务。`app.state.rt` 是 FastAPI 应用上的 Runtime 属性名。禁止创建全局单例或模块级连接对象。

### 7. Runtime 只持有 Protocol 接口

`rt.db`、`rt.vector_db`、`rt.search`、`rt.graph_db`、`rt.cache`、`rt.queue`、`rt.storage` 均以 **Protocol 接口**存储，从不持有具体实现类。LLM、Embedder、Reranker、PageIndex 等智能层组件**不挂载在 Runtime 上**，而是在任务或服务内部按需本地实例化（通过 `rt.env.OPENAI_API_KEY`、`rt.config.*` 获取凭证和配置）：

- 测试时直接用 `MagicMock()` 替换 Runtime 字段，无需 `@patch` 任何全局符号
- 换实现（如 OpenAI → Anthropic）只需修改 `build_runtime()`，业务代码零改动

**禁止**在业务代码中直接实例化 `MilvusClient(...)`、`Elasticsearch(...)` 等具体基础设施客户端；必须通过 `rt.xxx` 协议接口访问。智能层（`OpenAILLMCaller`、`OpenAIEmbedder` 等）在本地实例化后即用即弃，不缓存到全局变量。

### 8. Repository 双模式

`insert(entity)` 自动提交；`tx_insert(tx, entity)` 用于显式事务。

### 9. Celery 异步优先

导入和嵌入始终异步执行，API 立即返回任务 ID。任务入队时使用 `constants.QUEUE_XXX` 常量指定队列名。

### 10. RAG 路径选择

`AdaptiveRAGRouter` 在运行时对查询分类，选择合适路径（`hybrid-search` / `wiki-lookup` / `doc-navigate`）。路由决策通过本地实例化的 LLM 调用完成，所有 LLM 凭证来自 `rt.env`，模型名称来自 `rt.config`。

---

## 前端

### 11. API 调用统一入口

所有对后端的调用必须经过 `lib/api.ts`，禁止在组件或 Server Action 中直接裸调 `fetch`。`lib/api.ts` 是前端与后端通信的**唯一入口**。

### 12. SUCCESS_CODES 集合

用 `SUCCESS_CODES = new Set([100000])` + `.has(code)` 判断成功，**不用单一常量对比**。未来新增成功码只需修改 `lib/constants.ts`，所有调用方无需改动：

```typescript
import { SUCCESS_CODES } from "@/lib/constants";

// correct — set lookup; adding a second success code only requires changing constants.ts
if (SUCCESS_CODES.has(resp.code)) { ... }

// wrong — inline literal
if (resp.code === 100000) { ... }

// wrong — single-value constant; breaks if a second success code is added later
if (resp.code === SUCCESS_CODE) { ... }
```

### 13. 禁止内联魔法值

所有前端魔法值（业务码集合、localStorage 键名、SSE 事件名、API 路径等）统一定义在 `lib/constants.ts`，代码中禁止出现内联字面量：

```typescript
// lib/constants.ts

// success code set — use SUCCESS_CODES.has(code), never === 100000
export const SUCCESS_CODES = new Set([100000]);

// fallback error code when i18n key is not found
export const FALLBACK_ERROR_CODE = 500000;

// localStorage / cookie keys
export const ACCESS_TOKEN_KEY = "access_token";

// SSE field names and done sentinel
export const SSE_FIELD_TOKEN   = "token";
export const SSE_FIELD_ERROR   = "error";
export const SSE_DONE_SENTINEL = "[DONE]";

// API paths — components and hooks must not inline path strings
export const API_QA_ASK        = "/api/v1/qa/ask";
export const API_QA_SESSIONS   = "/api/v1/qa/sessions";
export const API_INGEST_UPLOAD = "/api/v1/ingest/upload";
export const API_WIKI_PAGES    = "/api/v1/wiki/pages";
// add new endpoints here
```

### 14. 错误处理自动化

`lib/api.ts` 统一处理所有 API 错误：

- **Toast**（sonner）：展示翻译后的用户友好文案，自动消失
- **`console.error`**：记录完整请求上下文（`method`、`url`、`body`、`code`/`httpStatus`、`requestId`、`message`），供开发者和 AI Agent 排查

业务组件通常**无需** `catch`；只有需要对特定 `code` 做特殊 UI 响应时才 catch `ApiError`。

### 15. i18n 错误码即键名

`messages/<locale>.json` 中 `error` 命名空间以**业务码字符串**为 key，`lib/api.ts` 直接用 `code` 查表，查不到时降级到 `FALLBACK_ERROR_CODE`（`500000`）对应的通用文案。

---

## 通用

### 16. 文档自包含

本目录中的每个文件都包含实现该组件所需的全部内容，无需参考外部文档。每个文件的代码示例可直接复制使用。

---

## 规则速查

| # | 规则 | 后端 | 前端 |
|---|------|:----:|:----:|
| 1 | 每个 try 块只包裹一次调用，附加明确上下文 | ✓ | |
| 2 | API 信封始终 HTTP 200，code 字段区分成功/失败 | ✓ | ✓ |
| 3 | 业务码只在 `codes.py` 定义；判断成功用集合（`in codes.SUCCESS_CODES`），不用 `==` | ✓ | |
| 4 | 其他魔法字符串只在 `constants.py` 定义，禁止内联字符串 | ✓ | |
| 5 | 配置与凭证严格分层（`config.yaml` vs `.env`）| ✓ | |
| 6 | 禁止全局单例，所有依赖通过 Runtime 注入 | ✓ | |
| 7 | Runtime 字段全部是 Protocol 接口；智能层（LLM/Embedder 等）在本地实例化，不挂载在 Runtime 上 | ✓ | |
| 8 | Repository 双模式：`insert` 自动提交，`tx_insert` 显式事务 | ✓ | |
| 9 | 导入/嵌入始终异步，API 立即返回任务 ID | ✓ | |
| 10 | AdaptiveRAGRouter 在运行时选择检索路径（hybrid-search / wiki-lookup / doc-navigate） | ✓ | |
| 11 | 所有 API 调用必须经过 `lib/api.ts` | | ✓ |
| 12 | 用 `SUCCESS_CODES.has(code)` 判断成功，不用 `===` | | ✓ |
| 13 | 所有魔法值定义在 `lib/constants.ts`，禁止内联字面量 | | ✓ |
| 14 | `lib/api.ts` 统一处理错误（Toast + console.error）| | ✓ |
| 15 | i18n 以业务码字符串为 key，查不到降级到通用文案 | | ✓ |
| 16 | 文档自包含，代码示例可直接复制 | ✓ | ✓ |
