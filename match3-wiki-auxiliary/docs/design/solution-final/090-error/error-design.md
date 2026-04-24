# 报错设计

本文规范 match3-wiki 的结构化错误体系——覆盖开发、测试和生产三个阶段，包括错误码分层、异常链路传播、日志格式、环境感知的 API 响应策略、前端处理规范，以及使 AI Agent 能够自动解析、定位、复现错误的机器可读约定。

---

## 一、错误码分层

所有业务错误码按所属系统层级分段，互不重叠：

| 段 | 范围 | 所属层 |
|----|------|--------|
| 通用参数 | 400001–400099 | API 层 |
| 认证鉴权 | 401001–401099 | API 中间件 |
| 资源不存在 | 404001–404099 | Service 层 |
| 业务逻辑 | 420001–420099 | Service 层 |
| 外部依赖 | 500001–500099 | Storage 层 |
| 智能层 | 600001–600099 | Intelligence 层 |

```python
# app/common/constants/codes.py
# This file is the single authoritative source of all business error codes.
# Frontend i18n keys, backend Match3Exception.of_code() calls, and API docs all reference values here.
# Never define business codes anywhere else.

# --- Success code (special: not an error) ---
SUCCESS                = 100000              # used when building a success response (ApiResp.ok())
SUCCESS_CODES          = frozenset({SUCCESS})  # use a frozenset for future extensibility

# --- Internal error (catch-all for unhandled exceptions) ---
INTERNAL_ERROR         = 500000   # generic fallback, used by unhandled_exception_handler

# --- 400xxx: parameter / request format errors ---
INVALID_PARAM          = 400001   # missing or invalid request field
UNSUPPORTED_FILE_TYPE  = 400002   # file extension not in allowed set
FILE_TOO_LARGE         = 400003   # upload exceeds size limit

# --- 400xxx: startup / config errors (thrown only during initialization) ---
CONFIG_FILE_NOT_FOUND  = 400010   # config.yaml not found at startup
CONFIG_MISSING_REQUIRED = 400011  # required config key is absent

# --- 401xxx: authentication / authorization errors ---
UNAUTHORIZED           = 401001   # JWT missing or invalid
FORBIDDEN              = 401002   # JWT valid but global role insufficient
PERMISSION_DENIED      = 401003   # workspace-level operation denied (role insufficient)

# --- 404xxx: resource not found ---
WORKSPACE_NOT_FOUND    = 404001
RAW_FILE_NOT_FOUND     = 404002
WIKI_NOT_FOUND         = 404003
CHUNK_NOT_FOUND        = 404004
SESSION_NOT_FOUND      = 404005
WORKSPACE_NOT_MEMBER   = 404006   # user has no membership record in this workspace

# --- 420xxx: business logic errors ---
WORKSPACE_LIMIT        = 420001   # workspace plan quota exceeded
ALREADY_PROCESSING     = 420002   # file is currently being ingested
WIKI_COMPILE_CONFLICT  = 420003   # a compile job for this topic is already running
CHUNK_EMPTY            = 420004   # chunking produced zero usable chunks

# --- 500xxx: external dependency errors ---
DB_ERROR               = 500001   # PostgreSQL failure
REDIS_ERROR            = 500002
MILVUS_ERROR           = 500003
ES_ERROR               = 500004
NEO4J_ERROR            = 500005
MINIO_ERROR            = 500006
EMBED_FAILED           = 500007   # vector embedding model call failed
RERANK_FAILED          = 500008

# --- 600xxx: intelligence-layer errors ---
LLM_FAILED             = 600001   # LLM API call failed or returned empty content
WHISPER_FAILED         = 600002   # audio transcription failed
PAGEINDEX_FAILED       = 600003   # PageIndex API error
VISION_FAILED          = 600004   # image description failed
GRAPH_EXTRACT_FAILED   = 600005   # entity/relationship extraction failed
```

错误码是前端 i18n 国际化的**唯一键**：前端根据 `code` 在本地语言包中查找对应的提示文案，不依赖后端返回的文字内容。详见第四节。

---

## 二、Match3Exception 链式规范

### 基本模式

每个 try 块**只包裹单一调用**，捕获后立即用 `Match3Exception` 包装并附加上下文：

```python
# GOOD — one call per try block
try:
    doc = pi_client.submit_document(file_path=local_path)
except Exception as e:
    raise Match3Exception.of("failed to submit document to pageindex") \
        .ctx(raw_file_id=raw_file_id, path=local_path) \
        .as_ex(e)

# GOOD — business rule violation uses of_code
if not workspace:
    raise Match3Exception.of_code(codes.WORKSPACE_NOT_FOUND, "workspace not found") \
        .ctx(workspace_id=workspace_id)

# BAD — broad try block hides which call failed
try:
    ws = repo.find_by_id(workspace_id)
    member = member_repo.find_by_user_workspace(user_id, workspace_id)
    ...
except Exception as e:
    raise Match3Exception.of("something failed").as_ex(e)   # unclear origin
```

### `.ctx()` 键命名约定

`.ctx()` 中的键必须使用**蛇形命名**，值尽量是**标量**（字符串、整数、布尔），避免传入大型对象：

| 场景 | 推荐键 |
|------|--------|
| 数据库主键 | `workspace_id`, `raw_file_id`, `chunk_id`, `page_id` |
| 文件信息 | `filename`, `file_type`, `size_bytes` |
| 外部服务 | `model`, `status_code`, `latency_ms` |
| 任务信息 | `task_id`, `queue`, `retry_count` |
| RAG 上下文 | `rag_path`, `rag_method`, `query_len` |
| 数组/集合 | 传长度，例如 `chunk_count=len(chunks)`，不传完整列表 |

### resolve_code() 行为

`resolve_code()` 沿 `__cause__` 链向下查找，返回**第一个非零 code**：

```
Match3Exception(code=0, "failed to compile wiki")
  └── Match3Exception(code=0, "failed to call llm")
        └── Match3Exception(code=600001, "llm returned empty response")
```

API 层 `exception_handler` 调用 `e.resolve_code()` 返回 `600001`，前端据此在语言包中查找对应的错误提示文案。

---

## 三、后端：环境感知的错误响应

`ApiResp` 的 `message` 字段在不同环境有不同的信息密度，由 `APP_ENV` 环境变量（`development` / `staging` / `production`）控制：

| 环境 | `message` 内容 | 用途 |
|------|----------------|------|
| `production` | 简短人类可读描述（如 `"llm call failed"`） | 暴露给终端用户，不泄露内部细节 |
| `development` / `staging` | 完整错误链 JSON 序列化字符串 | 帮助开发者和 AI Agent 快速定位根因 |

`cause_chain` 始终完整地写入**结构化日志**，与环境无关——生产环境只是不把它放进 API 响应的 `message` 里，但日志里永远有完整链路。

```python
# app/api/exception_handler.py
import json
import logging
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from app.api.schemas import ApiResp

logger = logging.getLogger("match3.api")


async def match3_exception_handler(request: Request, exc: Match3Exception) -> JSONResponse:
    code = exc.resolve_code()
    ctx = dict(exc._context)
    chain = _build_cause_chain(exc)
    request_id = getattr(request.state, "request_id", "")

    log_record = {
        "event": "request_error",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "error_code": code,
        "error_message": exc.message,
        "error_context": ctx,
        "cause_chain": chain,   # always recorded in full
    }
    logger.error(json.dumps(log_record, ensure_ascii=False))

    # production: expose brief description only; non-production: expose full chain
    rt = request.app.state.rt
    if rt.config.app_env == "production":
        response_message = exc.message
    else:
        response_message = json.dumps(chain, ensure_ascii=False)

    # RPC convention: HTTP status is always 200; business result is carried in the response body.
    resp = ApiResp.error(code=code, message=response_message, request_id=request_id)
    return JSONResponse(status_code=200, content=resp.model_dump(by_alias=True))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    log_record = {
        "event": "unhandled_exception",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "traceback": traceback.format_exc(),
    }
    logger.critical(json.dumps(log_record, ensure_ascii=False))
    # The only place in this codebase that returns a non-200 HTTP status code.
    # All Match3Exception business errors use the RPC-style status_code=200 above.
    return JSONResponse(
        status_code=500,
        content={"requestId": request_id, "code": codes.INTERNAL_ERROR, "message": "internal server error", "data": None},
    )


def _build_cause_chain(exc: Exception) -> list[dict]:
    chain = []
    current = exc
    while current is not None:
        chain.append({
            "type": type(current).__name__,
            "message": str(current),
            "code": getattr(current, "code", 0),
            "context": dict(getattr(current, "_context", [])),
        })
        current = getattr(current, "__cause__", None)
    return chain


# app/main.py registration
# app.add_exception_handler(Match3Exception, match3_exception_handler)
# app.add_exception_handler(Exception, unhandled_exception_handler)
```

---

## 四、前端：统一错误处理

前端所有 API 调用必须经过 `lib/api.ts`——这是与后端通信的唯一入口（详见 `310-frontend/frontend.md`）。错误处理在 `lib/api.ts` 内统一完成，业务组件通常无需 `catch`。

### 4.1 Toast 提示（用户可见）

`lib/api.ts` 在收到业务错误响应时，自动根据 `code` 在 i18n 错误命名空间中查找文案，以 **sonner Toast** 形式展示给用户——自动消失，不打断操作流程。

i18n 语言包中为每个错误码预置对应文案，`code` 字符串即为查找键（`"error"` 命名空间，非 `"errors"`）：

```json
// messages/zh.json (partial — locale is "zh", NOT "zh-CN")
{
  "error": {
    "500000": "Internal server error, please try again later",
    "400001": "Invalid request parameters",
    "400002": "Unsupported file type",
    "400003": "File exceeds size limit",
    "401001": "Session expired, please log in again",
    "401002": "You do not have permission to perform this action",
    "404001": "Workspace not found",
    "404002": "File not found",
    "404003": "Wiki page not found",
    "420001": "Workspace quota reached",
    "420002": "File is currently being processed, please do not resubmit",
    "500001": "Database temporarily unavailable, please try again later",
    "600001": "AI service temporarily unavailable, please try again later",
    "600002": "Audio transcription failed, please check the file format"
  }
}
```

```json
// messages/en.json (partial)
{
  "error": {
    "500000": "Internal server error, please try again later",
    "400001": "Invalid request parameters",
    "400002": "Unsupported file type",
    "401001": "Session expired, please log in again",
    "401002": "You do not have permission to perform this action",
    "600001": "AI service temporarily unavailable"
  }
}
```

查找规则：用 `code` 字符串查 `error` 命名空间；找不到时降级到 `error["500000"]`（`FALLBACK_ERROR_CODE`）对应的通用文案。成功码 `100000` 对应 `null`（不展示 Toast）。

### 4.2 Console 日志（调试用）

`lib/api.ts` 在每次业务错误时，无论环境如何，都将完整的请求上下文打印到 `console.error`，供开发者和 AI Agent 在浏览器 DevTools 中快速定位问题：

```
[API] business error { method: "POST", url: "/api/v1/qa/ask", body: {...},
                       code: 600001, requestId: "req-xyz789", message: "..." }
```

`message` 的内容由后端环境决定：生产环境是简短描述，非生产环境是完整错误链 JSON——`lib/api.ts` 无脑打印即可（完整实现见 `310-frontend/frontend.md`）。

### 4.3 多语言（next-intl）

前端使用 **`next-intl`** 实现多语言支持：

- 语言包存放在 `messages/<locale>.json`，locale 值为 `zh`（默认）和 `en`
- 路由采用 URL 前缀：`/zh/wiki`、`/en/wiki`；访问 `/` 自动重定向到 `/zh`
- 错误码到用户文案的映射完全在语言包 `"error"` 命名空间中维护，后端无需关心
- 新增错误码时，同步在所有语言包中添加对应条目

### 4.4 多主题（next-themes）

前端使用 **`next-themes`** 管理主题，shadcn/ui 内置对 `dark` class 的支持：

- `ThemeProvider` 配置 `attribute="class"`（非 `data-theme`），`defaultTheme="dark"`，`enableSystem={false}`
- 主题切换仅在 `dark` / `light` 两个值之间切换
- 用户主题偏好由 `next-themes` 自动持久化，页面加载时无闪烁

---

## 五、Celery Worker 错误日志

Worker 任务失败时同样输出结构化 JSON，以便日志聚合平台（Loki、Datadog）和 AI Agent 解析：

```python
# app/workers/base_task.py
import json
import logging
from celery import Task
from app.common.exceptions import Match3Exception

logger = logging.getLogger("match3.worker")

class LoggedTask(Task):
    """Base task class — emits structured JSON log on failure."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        record = {
            "event": "task_failure",
            "task_name": self.name,
            "task_id": task_id,
            "args": list(args),
            "kwargs": kwargs,
            "error_type": type(exc).__name__,
            "error_code": exc.resolve_code() if isinstance(exc, Match3Exception) else 0,
            "error_message": str(exc),
            "cause_chain": _build_cause_chain(exc) if isinstance(exc, Match3Exception) else [],
            "traceback": str(einfo),
        }
        logger.error(json.dumps(record, ensure_ascii=False))

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        record = {
            "event": "task_retry",
            "task_name": self.name,
            "task_id": task_id,
            "retry_count": self.request.retries,
            "error_message": str(exc),
        }
        logger.warning(json.dumps(record, ensure_ascii=False))
```

---

## 六、结构化日志格式

所有日志行均为单行 JSON，字段固定，便于 `jq`、Loki、AI Agent 直接解析。

### API 请求日志（access log）

```json
{
  "event": "request",
  "ts": "2026-04-22T08:31:00.123Z",
  "request_id": "req-abc123",
  "method": "POST",
  "path": "/api/v1/wiki/compile",
  "status_code": 200,
  "latency_ms": 42,
  "workspace_id": "ws-001",
  "user_id": "user-001"
}
```

### 业务错误日志

```json
{
  "event": "request_error",
  "ts": "2026-04-22T08:31:05.456Z",
  "request_id": "req-xyz789",
  "method": "POST",
  "path": "/api/v1/qa/ask",
  "error_code": 600001,
  "error_message": "failed to call llm",
  "error_context": {
    "model": "gpt-4o",
    "workspace_id": "ws-001",
    "query_len": 128
  },
  "cause_chain": [
    {"type": "Match3Exception", "message": "failed to call llm", "code": 0, "context": {"model": "gpt-4o"}},
    {"type": "Match3Exception", "message": "llm returned empty response", "code": 600001, "context": {}},
    {"type": "openai.APIError", "message": "Rate limit exceeded", "code": 0, "context": {}}
  ]
}
```

### Worker 任务失败日志

```json
{
  "event": "task_failure",
  "ts": "2026-04-22T08:32:10.789Z",
  "task_name": "app.workers.ingest_task.ingest_file",
  "task_id": "celery-task-uuid-001",
  "args": ["raw-file-uuid-001"],
  "kwargs": {"workspace_id": "ws-001"},
  "error_code": 500006,
  "error_message": "failed to upload file to minio",
  "cause_chain": [
    {"type": "Match3Exception", "message": "failed to upload file to minio", "code": 0, "context": {"object_key": "ws-001/raw/file.pdf"}},
    {"type": "Match3Exception", "message": "minio put_object error", "code": 500006, "context": {"bucket": "match3-raw"}},
    {"type": "S3Error", "message": "connection refused", "code": 0, "context": {}}
  ],
  "traceback": "..."
}
```

---

## 七、排错协议

### 7.1 各阶段排错入口

| 阶段 | 错误入口 | 主要工具 |
|------|----------|---------|
| 开发 | 本地控制台输出 + 浏览器 Console | `docker compose logs`、DevTools、`pytest --tb=short` |
| 测试 | `test-results.json` + pytest 输出 | `jq`、`pytest --tb=short`、`coverage` |
| 生产 | 结构化日志（单行 JSON） | `docker compose logs`、Loki、Datadog |

### 7.2 读取日志的推荐命令

```bash
# filter the last 100 error log entries (any service)
docker compose logs --tail=200 api | grep '"event":"request_error"' | tail -20

# filter by error code
docker compose logs api | jq -c 'select(.error_code == 600001)'

# view full trace for a specific request_id
docker compose logs api | jq -c 'select(.request_id == "req-xyz789")'

# worker task failure
docker compose logs worker-ingest | jq -c 'select(.event == "task_failure")'
```

### 7.3 根因定位流程

```
1. Obtain error_code
   └─ Look up codes.py to identify the system layer (4xx/5xx/6xx)

2. Read error_context
   └─ Retrieve key identifiers at the time of failure: workspace_id / raw_file_id / task_id, etc.

3. Walk cause_chain to find the root cause
   └─ Find the first entry whose type is not Match3Exception (usually a third-party library exception)
   └─ That node's message is the underlying real cause

4. Locate the code based on the root cause
   └─ Error code segment → corresponding file (see quick-reference table 7.4)

5. Check infrastructure connectivity
   └─ docker compose ps  # confirm container running status
   └─ docker compose logs <service> --tail=50  # check the relevant middleware logs
```

### 7.4 错误码 → 负责文件速查表

| 错误码 | 负责文件 | 关键函数 |
|--------|----------|---------|
| 400001–400099 | `app/api/routers/*.py` | 入参校验 |
| 401001–401002 | `app/api/middleware/auth_middleware.py` | JWT/RBAC |
| 404001–404005 | `app/services/*.py` | `find_by_id()` |
| 420001–420004 | `app/services/*.py` | 业务规则校验 |
| 500001 | `app/storage/repositories/*.py` | SQLAlchemy 操作 |
| 500002 | `app/workers/*/celery_app.py` | Redis 连接 |
| 500003 | `app/rag/path_chunk.py` | `milvus.search()` |
| 500004 | `app/rag/path_chunk.py` | `es.search()` |
| 500005 | `app/workers/graph_task.py` | Neo4j write |
| 500006 | `app/workers/ingest_task.py` | MinIO put |
| 500007–500008 | `app/services/embed_service.py` | 向量化/重排序 |
| 600001 | `app/rag/path_chunk.py`, `path_entry.py`, `path_page.py` | LLM 调用 |
| 600002 | `app/workers/ingest_task.py` | Whisper 转录 |
| 600003 | `app/services/ingest_service.py` | PageIndex API |
| 600004 | `app/workers/ingest_task.py` | 视觉描述 |
| 600005 | `app/workers/graph_task.py` | 图谱抽取 |

---

## 八、健康检查端点

`/health` 接口供 CI/CD 部署验收和 AI 监控使用，轻量探测所有下游连接：

```python
# app/api/routers/health_router.py
from fastapi import APIRouter
from app.runtime.runtime import Match3Runtime

router = APIRouter()

@router.get("/health")
async def health(rt: Match3Runtime):
    """Lightweight liveness probe — checks all downstream connections."""
    checks = {}
    try:
        with rt.db.connect() as conn:
            conn.execute("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = str(e)

    try:
        rt.cache.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)

    try:
        rt.vector_db.list_collections()
        checks["milvus"] = "ok"
    except Exception as e:
        checks["milvus"] = str(e)

    try:
        rt.search.ping()
        checks["elasticsearch"] = "ok"
    except Exception as e:
        checks["elasticsearch"] = str(e)

    try:
        rt.graph_db.verify_connectivity()
        checks["neo4j"] = "ok"
    except Exception as e:
        checks["neo4j"] = str(e)

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}
```

健康检查响应示例（所有服务正常）：

```json
{
  "status": "ok",
  "checks": {
    "postgres": "ok",
    "redis": "ok",
    "milvus": "ok",
    "elasticsearch": "ok",
    "neo4j": "ok"
  }
}
```

CI/CD 部署后的验收脚本直接 `curl /health` 并断言 `status == "ok"`，任何服务异常均会使部署失败（详见 `999-deployment/cicd.md`）。
