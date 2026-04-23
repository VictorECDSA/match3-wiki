# API 规范

## 概述

所有 API 端点遵循 anim-facade 的统一模式：
- 请求体封装于 `ApiReq[T]`
- 响应体封装于 `ApiResp[T]`
- 分页响应使用 `ApiResp[ApiRespPage[T]]`
- 错误通过 `Match3Exception` → 映射到 `ApiResp.error()`
- SSE 流式端点使用 `StreamingResponse`（无 `ApiResp` 包装）

---

## ApiReq

```python
# app/api/dto/api_req.py
from typing import Optional, TypeVar, Generic
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4

T = TypeVar("T")


def _default_request_id() -> str:
    return f"req-{uuid4()}"


class ApiReq(BaseModel, Generic[T]):
    """
    统一请求信封。
    所有 POST/PUT 端点接受 ApiReq[SomePayload]。
    requestId 会在 ApiResp 中回传，供客户端关联请求。
    """
    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(
        default_factory=_default_request_id,
        alias="requestId",
    )
    data: Optional[T] = Field(default=None)
```

---

## ApiResp

```python
# app/api/dto/api_resp.py
from typing import Optional, TypeVar, Generic
from pydantic import BaseModel, Field, ConfigDict
from app.common.constants import codes

T = TypeVar("T")


class ApiResp(BaseModel, Generic[T]):
    """
    统一响应信封。
    成功时 code=100000；出错时为非零值。
    """
    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(..., alias="requestId")
    code: int = Field(default=codes.SUCCESS)
    message: Optional[str] = Field(default=None)
    data: Optional[T] = Field(default=None)

    @classmethod
    def ok(cls, request_id: str, data: Optional[T] = None) -> "ApiResp[T]":
        return cls.model_construct(
            request_id=request_id,
            code=codes.SUCCESS,
            message=None,
            data=data,
        )

    @classmethod
    def error(cls, request_id: str, code: int, message: str) -> "ApiResp[None]":
        return cls.model_construct(
            request_id=request_id,
            code=code,
            message=message,
            data=None,
        )
```

---

## ApiRespPage

```python
# app/api/dto/api_resp_page.py
import math
from typing import List, TypeVar, Generic
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class ApiRespPage(BaseModel, Generic[T]):
    """分页数据载体——作为 ApiResp 的 data 字段使用。"""
    model_config = ConfigDict(populate_by_name=True)

    total: int = Field(default=0)
    page: int = Field(default=1)
    size: int = Field(default=10)
    total_pages: int = Field(default=0, alias="totalPages")
    list: List[T] = Field(default_factory=list)

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int = 1,
        size: int = 10,
    ) -> "ApiRespPage[T]":
        total_pages = math.ceil(total / size) if size > 0 else 0
        return cls(
            total=total,
            page=page,
            size=size,
            total_pages=total_pages,
            list=items,
        )
```

---

## 错误处理中间件

`Match3Exception` 由全局异常处理器捕获，映射为 `ApiResp.error()`，HTTP 状态码为 200（业务层错误使用业务码，而非 HTTP 错误码）。

```python
# app/api/middleware.py
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.common.exceptions import Match3Exception
from app.api.dto.api_resp import ApiResp
from app.common.constants import codes
import logging

logger = logging.getLogger(__name__)


async def match3_exception_handler(request: Request, exc: Match3Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    # resolve_code() 遍历 __cause__ 链，返回第一个非零业务码。
    code = exc.resolve_code()

    logger.error(
        "Match3Exception: code=%s msg=%s ctx=%s",
        code,
        exc.message,
        exc._context,
        exc_info=exc.__cause__,
    )

    resp = ApiResp.error(
        request_id=request_id,
        code=code,
        message=exc.message,
    )
    # RPC 约定：HTTP 状态码始终为 200，业务结果通过响应体中的 code 字段传递。
    return JSONResponse(status_code=200, content=resp.model_dump(by_alias=True))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")

    logger.exception("Unhandled exception: %s", exc)

    # 这是整个代码库中唯一返回非 200 HTTP 状态码的地方。
    # 所有 Match3Exception 业务错误均通过上方的 RPC 风格（status_code=200）处理。
    return JSONResponse(
        status_code=500,
        content={"requestId": request_id, "code": codes.INTERNAL_ERROR, "message": "服务器内部错误，请稍后重试。", "data": None},
    )


async def request_id_middleware(request: Request, call_next) -> Response:
    """从请求头注入 request_id，若无则自动生成。"""
    request_id = request.headers.get("X-Request-Id", f"req-{__import__('uuid').uuid4()}")
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response
```

---

## FastAPI 应用启动

```python
# app/api/app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.runtime import Match3Runtime
from app.common.exceptions import Match3Exception
from app.api.middleware import (
    match3_exception_handler,
    unhandled_exception_handler,
    request_id_middleware,
)
from app.api.routers import (
    ingest_router,
    wiki_router,
    qa_router,
    admin_router,
    health_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    rt: Match3Runtime = app.state.rt
    rt.logger.info("Match3 API starting")
    yield
    rt.logger.info("Match3 API shutting down")


def create_app(rt: Match3Runtime) -> FastAPI:
    app = FastAPI(
        title="Match3 Wiki API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.rt = rt

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID 中间件
    app.middleware("http")(request_id_middleware)

    # 异常处理器
    app.add_exception_handler(Match3Exception, match3_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # 路由
    PREFIX = "/api/v1"
    app.include_router(health_router.create(rt), prefix=PREFIX, tags=["health"])
    app.include_router(ingest_router.create(rt), prefix=PREFIX, tags=["ingest"])
    app.include_router(wiki_router.create(rt), prefix=PREFIX, tags=["wiki"])
    app.include_router(qa_router.create(rt), prefix=PREFIX, tags=["qa"])
    app.include_router(admin_router.create(rt), prefix=PREFIX, tags=["admin"])

    return app
```

---

## 请求/响应 JSON 格式

### 标准 POST 请求
```json
{
  "requestId": "req-550e8400-e29b-41d4-a716-446655440000",
  "data": {
    "field": "value"
  }
}
```

### 成功响应
```json
{
  "requestId": "req-550e8400-e29b-41d4-a716-446655440000",
  "code": 100000,
  "message": null,
  "data": { "id": "abc123" }
}
```

### 错误响应
```json
{
  "requestId": "req-550e8400-e29b-41d4-a716-446655440000",
  "code": 404001,
  "message": "raw file not found: abc123",
  "data": null
}
```

### 分页响应
```json
{
  "requestId": "req-...",
  "code": 100000,
  "message": null,
  "data": {
    "total": 42,
    "page": 1,
    "size": 10,
    "totalPages": 5,
    "list": [...]
  }
}
```

### SSE 流式响应（Q&A）
```
Content-Type: text/event-stream
Cache-Control: no-cache

data: {"token": "The"}
data: {"token": " match"}
data: {"token": "-3"}
data: {"token": " market"}
data: [DONE]
```

---

## 业务码

所有业务码定义在 `app/common/constants/codes.py`——这是**唯一权威来源**，禁止在业务代码中出现内联数字字面量。完整的码值定义及分层规则见 `090-error/error-design.md`。

常用码速查（不要在代码中硬编码这些数字，始终通过 `codes.XXX` 引用）：

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `codes.SUCCESS` | 100000 | 成功（`ApiResp.ok()` 默认值） |
| `codes.INTERNAL_ERROR` | 500000 | 未处理异常兜底（仅 `unhandled_exception_handler` 使用） |
| `codes.INVALID_PARAM` | 400001 | 请求参数有误 |
| `codes.UNAUTHORIZED` | 401001 | JWT 缺失或无效 |
| `codes.FORBIDDEN` | 401002 | 权限不足 |
| `codes.WORKSPACE_NOT_FOUND` | 404001 | 工作区不存在 |
| `codes.RAW_FILE_NOT_FOUND` | 404002 | 文件不存在 |
| `codes.WIKI_NOT_FOUND` | 404003 | Wiki 页面不存在 |
| `codes.LLM_FAILED` | 600001 | LLM 调用失败 |

完整码表见 `090-error/error-design.md` 第一节。