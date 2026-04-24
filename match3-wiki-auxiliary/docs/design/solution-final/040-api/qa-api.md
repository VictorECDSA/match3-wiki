# Q&A API（SSE 流式）

## 端点

| 方法 | 路径 | 说明 |
|--------|------|-------------|
| POST | `/api/v1/qa/ask` | 提问（SSE 流式响应） |
| GET | `/api/v1/qa/sessions` | 列出工作区的 Q&A 会话 |
| GET | `/api/v1/qa/sessions/{session_id}` | 获取含完整答案的 Q&A 会话 |

---

## SSE 流式协议

Q&A 端点以 Server-Sent Events（SSE）方式流式输出 token。响应不使用 `ApiResp` 包装。

```
POST /api/v1/qa/ask
{ "requestId": "req-abc123",
  "data": { "query": "...", "workspaceId": "ws-001", "userId": "user-001", "rawFileId": null } }

Response: Content-Type: text/event-stream  X-Accel-Buffering: no  (disable nginx buffering)

data: {"token": "The"}
data: {"token": " top"}
...
data: [DONE]

On error: data: {"error": "...", "code": 420001}  then stream closes
```

---

## DTO

**文件**：`app/api/dto/qa_dto.py`

### AskReq

| 字段 | 类型 | alias | 说明 |
|------|------|-------|------|
| `query` | `str` | — | 1–4000 字符 |
| `workspace_id` | `str` | `workspaceId` | — |
| `user_id` | `str` | `userId` | — |
| `raw_file_id` | `str?` | `rawFileId` | 设置后强制走 doc-navigate 路径 |

### QASessionResp

| 字段 | 类型 | alias |
|------|------|-------|
| `id` | `str` | — |
| `workspace_id` | `str` | `workspaceId` |
| `user_id` | `str` | `userId` |
| `query` | `str` | — |
| `rag_path` | `str` | `ragPath` | `"chunk"` \| `"entry"` \| `"page"` |
| `rag_method` | `str?` | `ragMethod` | |
| `status` | `str` | — | `"generating"` \| `"done"` \| `"failed"` |
| `answer` | `str?` | — | |
| `error` | `str?` | — | |
| `created_at` | `str` | `createdAt` | ISO 8601 |

---

## 路由

**文件**：`app/api/routers/qa_router.py`

| 方法 | 说明 |
|------|------|
| `ask(req: ApiReq[AskReq])` | 调用 `QAService.ask()` generator，每个 token 包装为 `{"token": "..."}` SSE 事件；异常输出 `{"error": ..., "code": ...}`；最终发送 `[DONE]`；返回 `StreamingResponse(media_type="text/event-stream")` |
| `list_sessions(workspaceId, userId?, page, size)` | 委托 `QAService.list_sessions()` → `ApiRespPage` |
| `get_session(session_id)` | 委托 `QAService.get_session()` |

---

## QAService 会话持久化

`ask()` 核心逻辑见 `030-rag/retrieval/router.md`。`list_sessions()` / `get_session()` 直接委托 `QARepository`（`find_paginated` / `find_by_id`），未找到时抛 `SESSION_NOT_FOUND`。

---

## 前端集成（Next.js）

**文件**：`frontend/app/lib/qa-stream.ts`

```typescript
export async function streamAnswer(
  query, workspaceId, userId, rawFileId?,
  onToken?, onDone?, onError?
): Promise<void>
```

用 `fetch` + `ReadableStream` 读取 SSE：
- 逐块解码，按 `\n\n` 分帧
- `{"token": "..."}` → `onToken(token)`
- `{"error": ..., "code": ...}` → `onError(error, code)`
- `[DONE]` → `onDone()`
