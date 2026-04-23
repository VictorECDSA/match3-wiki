# Q&A API（SSE 流式）

## 端点

| 方法 | 路径 | 说明 |
|--------|------|-------------|
| POST | `/api/v1/qa/ask` | 提问（SSE 流式响应） |
| GET | `/api/v1/qa/sessions` | 列出工作区的 Q&A 会话 |
| GET | `/api/v1/qa/sessions/{session_id}` | 获取含完整答案的 Q&A 会话 |

---

## SSE 流式协议

Q&A 端点以 Server-Sent Events（SSE）方式流式输出 token。响应不使用 `ApiResp` 包装——由于响应是增量式的，直接使用原始 SSE 协议。

```
POST /api/v1/qa/ask
Content-Type: application/json

{
  "requestId": "req-abc123",
  "data": {
    "query": "What are the top match-3 games by revenue?",
    "workspaceId": "ws-001",
    "userId": "user-001",
    "rawFileId": null
  }
}

响应：
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
X-Request-Id: req-abc123

data: {"token": "The"}
data: {"token": " top"}
data: {"token": " match"}
data: {"token": "-3"}
data: {"token": " games"}
data: {"token": " by"}
data: {"token": " revenue"}
data: {"token": " are"}
data: {"token": "..."}
data: [DONE]
```

出错时，在流关闭前会发出一个 `data: {"error": "...", "code": 420001}` 事件。

---

## DTO

```python
# app/api/dto/qa_dto.py
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class AskReq(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    workspace_id: str = Field(..., alias="workspaceId")
    user_id: str = Field(..., alias="userId")
    raw_file_id: Optional[str] = Field(default=None, alias="rawFileId",
                                       description="若设置，则强制对该文件走 doc-navigate 路径")

    class Config:
        populate_by_name = True


class QASessionResp(BaseModel):
    id: str
    workspace_id: str = Field(..., alias="workspaceId")
    user_id: str = Field(..., alias="userId")
    query: str
    rag_path: str = Field(..., alias="ragPath")       # "chunk" | "entry" | "page"
    rag_method: Optional[str] = Field(default=None, alias="ragMethod")
    status: str                                        # "generating" | "done" | "failed"
    answer: Optional[str] = None
    error: Optional[str] = None
    created_at: str = Field(..., alias="createdAt")

    class Config:
        populate_by_name = True
```

---

## 路由

```python
# app/api/routers/qa_router.py
from __future__ import annotations
import json
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from app.runtime import Match3Runtime
from app.api.dto.api_req import ApiReq
from app.api.dto.api_resp import ApiResp
from app.api.dto.api_resp_page import ApiRespPage
from app.api.dto.qa_dto import AskReq, QASessionResp
from app.services.qa_service import QAService
from app.common.exceptions import Match3Exception


class QAAPI:

    def __init__(self, rt: Match3Runtime):
        self._rt = rt
        self._svc = QAService(rt)

    async def ask(
        self,
        request: Request,
        req: ApiReq[AskReq],
    ) -> StreamingResponse:
        if not req.data:
            from app.common.constants import codes
            raise Match3Exception.of_code(codes.INVALID_PARAM).ctx(reason="missing data")

        d = req.data

        async def event_stream():
            try:
                gen = self._svc.ask(
                    query=d.query,
                    workspace_id=d.workspace_id,
                    user_id=d.user_id,
                    raw_file_id=d.raw_file_id,
                )
                for token in gen:
                    payload = json.dumps({"token": token}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
            except Match3Exception as e:
                error_payload = json.dumps({"error": e.message, "code": e.resolve_code()})
                yield f"data: {error_payload}\n\n"
            except Exception as e:
                error_payload = json.dumps({"error": str(e), "code": 0})
                yield f"data: {error_payload}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Request-Id": req.request_id,
                "X-Accel-Buffering": "no",   # 禁用 nginx 对 SSE 的缓冲
            },
        )

    async def list_sessions(
        self,
        request: Request,
        workspace_id: str = Query(..., alias="workspaceId"),
        user_id: str | None = Query(default=None, alias="userId"),
        page: int = Query(default=1, ge=1),
        size: int = Query(default=20, ge=1, le=100),
    ) -> ApiResp[ApiRespPage[QASessionResp]]:
        request_id = request.state.request_id
        items, total = self._svc.list_sessions(
            workspace_id=workspace_id,
            user_id=user_id,
            page=page,
            size=size,
        )
        page_resp = ApiRespPage.create(items=items, total=total, page=page, size=size)
        return ApiResp.ok(request_id=request_id, data=page_resp)

    async def get_session(
        self,
        request: Request,
        session_id: str,
    ) -> ApiResp[QASessionResp]:
        request_id = request.state.request_id
        session = self._svc.get_session(session_id)
        return ApiResp.ok(request_id=request_id, data=session)


def create(rt: Match3Runtime) -> APIRouter:
    router = APIRouter()
    api = QAAPI(rt)

    router.post("/qa/ask")(api.ask)
    router.get("/qa/sessions", response_model=ApiResp[ApiRespPage[QASessionResp]])(api.list_sessions)
    router.get("/qa/sessions/{session_id}", response_model=ApiResp[QASessionResp])(api.get_session)

    return router
```

---

## QAService 会话持久化方法

`QAService` 的核心 `ask()` 逻辑见 `030-rag/path-page.md`。会话列表/查询方法位于同一服务类中：

```python
# app/services/qa_service.py  （会话查询方法）

    def list_sessions(
        self,
        workspace_id: str,
        user_id: str | None,
        page: int,
        size: int,
    ) -> tuple[list[QASessionResp], int]:
        qa_repo = QARepository(self._rt.db_engine)
        items, total = qa_repo.find_paginated(
            workspace_id=workspace_id,
            user_id=user_id,
            page=page,
            size=size,
        )
        return [_to_session_resp(s) for s in items], total

    def get_session(self, session_id: str) -> QASessionResp:
        qa_repo = QARepository(self._rt.db_engine)
        session = qa_repo.find_by_id(session_id)
        if not session:
            from app.common.constants import codes
            raise Match3Exception.of_code(codes.SESSION_NOT_FOUND).ctx(session_id=session_id)
        return _to_session_resp(session)


def _to_session_resp(s) -> "QASessionResp":
    from app.api.dto.qa_dto import QASessionResp
    return QASessionResp(
        id=s.id,
        workspaceId=s.workspace_id,
        userId=s.user_id,
        query=s.query,
        ragPath=s.rag_path,
        ragMethod=s.rag_method,
        status=s.status,
        answer=s.answer,
        error=s.error,
        createdAt=s.created_at.isoformat(),
    )
```

---

## 前端集成（Next.js）

```typescript
// frontend/app/lib/qa-stream.ts

export async function streamAnswer(
  query: string,
  workspaceId: string,
  userId: string,
  rawFileId?: string,
  onToken?: (token: string) => void,
  onDone?: () => void,
  onError?: (error: string, code: number) => void,
): Promise<void> {
  const resp = await fetch("/api/v1/qa/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      requestId: `req-${crypto.randomUUID()}`,
      data: { query, workspaceId, userId, rawFileId },
    }),
  });

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (raw === "[DONE]") {
        onDone?.();
        return;
      }
      try {
        const parsed = JSON.parse(raw);
        if (parsed.error) {
          onError?.(parsed.error, parsed.code);
          return;
        }
        if (parsed.token) {
          onToken?.(parsed.token);
        }
      } catch {
        // 格式异常的事件，跳过
      }
    }
  }
}
```
