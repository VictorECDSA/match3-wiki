# Wiki API

## 端点

| 方法 | 路径 | 说明 |
|--------|------|-------------|
| POST | `/api/v1/wiki/compile` | 触发 Wiki 页面编译 |
| GET | `/api/v1/wiki/pages` | 列出已编译的 Wiki 页面 |
| GET | `/api/v1/wiki/pages/{topic}` | 按主题 slug 获取 Wiki 页面 |
| PUT | `/api/v1/wiki/pages/{topic}` | 强制重新编译页面 |
| DELETE | `/api/v1/wiki/pages/{topic}` | 删除 Wiki 页面 |
| GET | `/api/v1/wiki/tasks/{task_id}` | 轮询编译任务状态 |

---

## DTO

```python
# app/api/dto/wiki_dto.py
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class CompileReq(BaseModel):
    topic: str = Field(..., min_length=1, max_length=255,
                       description="主题 slug，例如 'entities/royal-match'")
    workspace_id: str = Field(..., alias="workspaceId")
    force: bool = Field(default=False, description="是否强制重新编译，即使页面已是最新")

    class Config:
        populate_by_name = True


class CompileResp(BaseModel):
    task_id: str = Field(..., alias="taskId")
    topic: str
    status: str  # "queued" | "already_up_to_date"

    class Config:
        populate_by_name = True


class WikiPageResp(BaseModel):
    id: str
    topic: str
    title: str
    workspace_id: str = Field(..., alias="workspaceId")
    status: str   # "compiling" | "published" | "failed"
    category: Optional[str] = None
    content: Optional[str] = None  # 状态非 "published" 时为 null
    error: Optional[str] = None
    compiled_at: Optional[str] = Field(default=None, alias="compiledAt")
    created_at: str = Field(..., alias="createdAt")

    class Config:
        populate_by_name = True


class WikiTaskStatusResp(BaseModel):
    task_id: str = Field(..., alias="taskId")
    topic: str
    status: str   # "pending" | "compiling" | "published" | "failed"
    error: Optional[str] = None

    class Config:
        populate_by_name = True
```

---

## 路由

```python
# app/api/routers/wiki_router.py
from __future__ import annotations
from fastapi import APIRouter, Request, Query
from app.runtime import Match3Runtime
from app.api.dto.api_req import ApiReq
from app.api.dto.api_resp import ApiResp
from app.api.dto.api_resp_page import ApiRespPage
from app.api.dto.wiki_dto import CompileReq, CompileResp, WikiPageResp, WikiTaskStatusResp
from app.services.wiki_compile_service import WikiCompileService
from app.common.exceptions import Match3Exception
from app.common.constants import codes


class WikiAPI:

    def __init__(self, rt: Match3Runtime):
        self._rt = rt
        self._svc = WikiCompileService(rt)

    async def compile(
        self,
        request: Request,
        req: ApiReq[CompileReq],
    ) -> ApiResp[CompileResp]:
        request_id = request.state.request_id
        if not req.data:
            raise Match3Exception.of_code(codes.INVALID_PARAM).ctx(reason="missing data")

        result = self._svc.compile(
            topic=req.data.topic,
            workspace_id=req.data.workspace_id,
            force=req.data.force,
        )
        return ApiResp.ok(request_id=request_id, data=result)

    async def list_pages(
        self,
        request: Request,
        workspace_id: str = Query(..., alias="workspaceId"),
        category: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        size: int = Query(default=20, ge=1, le=100),
    ) -> ApiResp[ApiRespPage[WikiPageResp]]:
        request_id = request.state.request_id
        items, total = self._svc.list_pages(
            workspace_id=workspace_id,
            category=category,
            page=page,
            size=size,
        )
        page_resp = ApiRespPage.create(items=items, total=total, page=page, size=size)
        return ApiResp.ok(request_id=request_id, data=page_resp)

    async def get_page(
        self,
        request: Request,
        topic: str,
        workspace_id: str = Query(..., alias="workspaceId"),
    ) -> ApiResp[WikiPageResp]:
        request_id = request.state.request_id
        page = self._svc.get_page(topic, workspace_id)
        if not page:
            raise Match3Exception.of_code(codes.WIKI_NOT_FOUND).ctx(topic=topic)
        return ApiResp.ok(request_id=request_id, data=page)

    async def recompile(
        self,
        request: Request,
        topic: str,
        req: ApiReq[CompileReq],
    ) -> ApiResp[CompileResp]:
        """强制重新编译已有页面。"""
        request_id = request.state.request_id
        workspace_id = req.data.workspace_id if req.data else None
        if not workspace_id:
            raise Match3Exception.of_code(codes.INVALID_PARAM).ctx(reason="missing workspaceId")

        result = self._svc.compile(topic=topic, workspace_id=workspace_id, force=True)
        return ApiResp.ok(request_id=request_id, data=result)

    async def delete_page(
        self,
        request: Request,
        topic: str,
        workspace_id: str = Query(..., alias="workspaceId"),
    ) -> ApiResp[None]:
        request_id = request.state.request_id
        self._svc.delete_page(topic, workspace_id)
        return ApiResp.ok(request_id=request_id)

    async def get_task_status(
        self,
        request: Request,
        task_id: str,
    ) -> ApiResp[WikiTaskStatusResp]:
        request_id = request.state.request_id
        result = self._svc.get_task_status(task_id)
        return ApiResp.ok(request_id=request_id, data=result)


def create(rt: Match3Runtime) -> APIRouter:
    router = APIRouter()
    api = WikiAPI(rt)

    router.post("/wiki/compile", response_model=ApiResp[CompileResp])(api.compile)
    router.get("/wiki/pages", response_model=ApiResp[ApiRespPage[WikiPageResp]])(api.list_pages)
    router.get("/wiki/pages/{topic:path}", response_model=ApiResp[WikiPageResp])(api.get_page)
    router.put("/wiki/pages/{topic:path}", response_model=ApiResp[CompileResp])(api.recompile)
    router.delete("/wiki/pages/{topic:path}", response_model=ApiResp[None])(api.delete_page)
    router.get("/wiki/tasks/{task_id}", response_model=ApiResp[WikiTaskStatusResp])(api.get_task_status)

    return router
```

注意：`{topic:path}` 允许主题 slug 中包含斜杠（例如 `entities/royal-match`）。

---

## WikiCompileService（扩展部分）

```python
# app/services/wiki_compile_service.py  (wiki-lookup 之外的扩展内容)
from app.api.dto.wiki_dto import CompileResp, WikiPageResp, WikiTaskStatusResp
from app.storage.entities.wiki_page import WikiPage, WikiPageStatus
from app.common.constants import constants


class WikiCompileService:

    # ... (compile() 和 get_page() 见 030-rag/path-entry.md)

    def compile(self, topic: str, workspace_id: str, force: bool = False) -> CompileResp:
        wiki_repo = WikiPageRepository(self._rt.db_engine)
        existing = wiki_repo.find_by_topic(topic, workspace_id)

        if existing and not force:
            raw_file_repo = RawFileRepository(self._rt.db_engine)
            latest_raw = raw_file_repo.find_latest_by_topic_tag(topic, workspace_id)
            if not (latest_raw and existing.compiled_at < latest_raw.created_at):
                return CompileResp(
                    taskId=f"wiki_page:{existing.id}",
                    topic=topic,
                    status="already_up_to_date",
                )
        task = compile_task.apply_async(
            args=[topic, workspace_id],
            queue=constants.QUEUE_COMPILE,
        )
        return CompileResp(taskId=task.id, topic=topic, status="queued")

    def get_page(self, topic: str, workspace_id: str) -> WikiPageResp | None:
        wiki_repo = WikiPageRepository(self._rt.db_engine)
        page = wiki_repo.find_by_topic(topic, workspace_id)
        if not page:
            return None
        return _to_wiki_page_resp(page, include_content=True)

    def list_pages(
        self,
        workspace_id: str,
        category: str | None,
        page: int,
        size: int,
    ) -> tuple[list[WikiPageResp], int]:
        wiki_repo = WikiPageRepository(self._rt.db_engine)
        items, total = wiki_repo.find_paginated(
            workspace_id=workspace_id,
            category=category,
            page=page,
            size=size,
        )
        return [_to_wiki_page_resp(p, include_content=False) for p in items], total

    def delete_page(self, topic: str, workspace_id: str) -> None:
        wiki_repo = WikiPageRepository(self._rt.db_engine)
        page = wiki_repo.find_by_topic(topic, workspace_id)
        if not page:
            raise Match3Exception.of_code(codes.WIKI_NOT_FOUND).ctx(topic=topic)
        wiki_repo.delete(page.id)

    def get_task_status(self, task_id: str) -> WikiTaskStatusResp:
        # task_id 可能是 Celery 任务 ID，也可能是 "wiki_page:{id}" 哨兵值
        if task_id.startswith("wiki_page:"):
            page_id = task_id.split(":")[1]
            wiki_repo = WikiPageRepository(self._rt.db_engine)
            page = wiki_repo.find_by_id(page_id)
            if page:
                return WikiTaskStatusResp(
                    taskId=task_id,
                    topic=page.topic,
                    status=page.status,
                    error=page.error,
                )

        from celery.result import AsyncResult
        result = AsyncResult(task_id)
        status_map = {
            "PENDING": "pending",
            "STARTED": "compiling",
            "SUCCESS": "published",
            "FAILURE": "failed",
        }
        return WikiTaskStatusResp(
            taskId=task_id,
            topic="",
            status=status_map.get(result.status, "pending"),
            error=str(result.result) if result.status == "FAILURE" else None,
        )


def _to_wiki_page_resp(page: WikiPage, include_content: bool) -> WikiPageResp:
    return WikiPageResp(
        id=page.id,
        topic=page.topic,
        title=page.title,
        workspaceId=page.workspace_id,
        status=page.status,
        category=page.category,
        content=page.content if include_content else None,
        error=page.error,
        compiledAt=page.compiled_at.isoformat() if page.compiled_at else None,
        createdAt=page.created_at.isoformat(),
    )
```
