# 管理 API

## 端点

| 方法 | 路径 | 说明 |
|--------|------|-------------|
| POST | `/api/v1/admin/workspaces` | 创建工作区 |
| GET | `/api/v1/admin/workspaces` | 列出所有工作区 |
| GET | `/api/v1/admin/workspaces/{workspace_id}` | 获取工作区 |
| PUT | `/api/v1/admin/workspaces/{workspace_id}` | 更新工作区 |
| DELETE | `/api/v1/admin/workspaces/{workspace_id}` | 删除工作区 |
| POST | `/api/v1/admin/workspaces/{workspace_id}/members` | 添加成员 |
| DELETE | `/api/v1/admin/workspaces/{workspace_id}/members/{user_id}` | 移除成员 |
| GET | `/api/v1/admin/workspaces/{workspace_id}/members` | 列出成员 |
| GET | `/api/v1/admin/stats` | 全系统统计数据（文件数、块数等） |

---

## DTO

```python
# app/api/dto/admin_dto.py
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class CreateWorkspaceReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    owner_id: str = Field(..., alias="ownerId")
    description: Optional[str] = Field(default=None, max_length=500)
    plan: str = Field(default="free", description="free | pro | enterprise（订阅计划）")

    class Config:
        populate_by_name = True


class UpdateWorkspaceReq(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    plan: Optional[str] = None

    class Config:
        populate_by_name = True


class WorkspaceResp(BaseModel):
    id: str
    name: str
    owner_id: str = Field(..., alias="ownerId")
    description: Optional[str] = None
    plan: str
    member_count: int = Field(default=0, alias="memberCount")
    file_count: int = Field(default=0, alias="fileCount")
    wiki_page_count: int = Field(default=0, alias="wikiPageCount")
    created_at: str = Field(..., alias="createdAt")

    class Config:
        populate_by_name = True


class AddMemberReq(BaseModel):
    user_id: str = Field(..., alias="userId")
    role: str = Field(default="member", description="owner | admin | member | viewer（成员角色）")

    class Config:
        populate_by_name = True


class MemberResp(BaseModel):
    user_id: str = Field(..., alias="userId")
    workspace_id: str = Field(..., alias="workspaceId")
    role: str
    joined_at: str = Field(..., alias="joinedAt")

    class Config:
        populate_by_name = True


class StatsResp(BaseModel):
    total_workspaces: int = Field(..., alias="totalWorkspaces")
    total_raw_files: int = Field(..., alias="totalRawFiles")
    total_chunks: int = Field(..., alias="totalChunks")
    total_wiki_pages: int = Field(..., alias="totalWikiPages")
    total_qa_sessions: int = Field(..., alias="totalQaSessions")
    storage_bytes: int = Field(..., alias="storageBytes")

    class Config:
        populate_by_name = True
```

---

## 路由

```python
# app/api/routers/admin_router.py
from __future__ import annotations
from fastapi import APIRouter, Request, Query
from app.runtime import Match3Runtime
from app.api.dto.api_req import ApiReq
from app.api.dto.api_resp import ApiResp
from app.api.dto.api_resp_page import ApiRespPage
from app.api.dto.admin_dto import (
    CreateWorkspaceReq, UpdateWorkspaceReq, WorkspaceResp,
    AddMemberReq, MemberResp, StatsResp,
)
from app.services.admin_service import AdminService
from app.common.exceptions import Match3Exception
from app.common.constants import codes


class AdminAPI:

    def __init__(self, rt: Match3Runtime):
        self._rt = rt
        self._svc = AdminService(rt)

    async def create_workspace(
        self,
        request: Request,
        req: ApiReq[CreateWorkspaceReq],
    ) -> ApiResp[WorkspaceResp]:
        request_id = request.state.request_id
        if not req.data:
            raise Match3Exception.of_code(codes.INVALID_PARAM, "invalid missing data")
        result = self._svc.create_workspace(req.data)
        return ApiResp.ok(request_id=request_id, data=result)

    async def list_workspaces(
        self,
        request: Request,
        page: int = Query(default=1, ge=1),
        size: int = Query(default=20, ge=1, le=100),
    ) -> ApiResp[ApiRespPage[WorkspaceResp]]:
        request_id = request.state.request_id
        items, total = self._svc.list_workspaces(page=page, size=size)
        page_resp = ApiRespPage.create(items=items, total=total, page=page, size=size)
        return ApiResp.ok(request_id=request_id, data=page_resp)

    async def get_workspace(
        self,
        request: Request,
        workspace_id: str,
    ) -> ApiResp[WorkspaceResp]:
        request_id = request.state.request_id
        result = self._svc.get_workspace(workspace_id)
        return ApiResp.ok(request_id=request_id, data=result)

    async def update_workspace(
        self,
        request: Request,
        workspace_id: str,
        req: ApiReq[UpdateWorkspaceReq],
    ) -> ApiResp[WorkspaceResp]:
        request_id = request.state.request_id
        if not req.data:
            raise Match3Exception.of_code(codes.INVALID_PARAM, "invalid missing data")
        result = self._svc.update_workspace(workspace_id, req.data)
        return ApiResp.ok(request_id=request_id, data=result)

    async def delete_workspace(
        self,
        request: Request,
        workspace_id: str,
    ) -> ApiResp[None]:
        request_id = request.state.request_id
        self._svc.delete_workspace(workspace_id)
        return ApiResp.ok(request_id=request_id)

    async def add_member(
        self,
        request: Request,
        workspace_id: str,
        req: ApiReq[AddMemberReq],
    ) -> ApiResp[MemberResp]:
        request_id = request.state.request_id
        if not req.data:
            raise Match3Exception.of_code(codes.INVALID_PARAM, "invalid missing data")
        result = self._svc.add_member(workspace_id, req.data)
        return ApiResp.ok(request_id=request_id, data=result)

    async def remove_member(
        self,
        request: Request,
        workspace_id: str,
        user_id: str,
    ) -> ApiResp[None]:
        request_id = request.state.request_id
        self._svc.remove_member(workspace_id, user_id)
        return ApiResp.ok(request_id=request_id)

    async def list_members(
        self,
        request: Request,
        workspace_id: str,
        page: int = Query(default=1, ge=1),
        size: int = Query(default=50, ge=1, le=200),
    ) -> ApiResp[ApiRespPage[MemberResp]]:
        request_id = request.state.request_id
        items, total = self._svc.list_members(workspace_id, page, size)
        page_resp = ApiRespPage.create(items=items, total=total, page=page, size=size)
        return ApiResp.ok(request_id=request_id, data=page_resp)

    async def get_stats(self, request: Request) -> ApiResp[StatsResp]:
        request_id = request.state.request_id
        result = self._svc.get_stats()
        return ApiResp.ok(request_id=request_id, data=result)


def create(rt: Match3Runtime) -> APIRouter:
    router = APIRouter()
    api = AdminAPI(rt)

    router.post("/admin/workspaces", response_model=ApiResp[WorkspaceResp])(api.create_workspace)
    router.get("/admin/workspaces", response_model=ApiResp[ApiRespPage[WorkspaceResp]])(api.list_workspaces)
    router.get("/admin/workspaces/{workspace_id}", response_model=ApiResp[WorkspaceResp])(api.get_workspace)
    router.put("/admin/workspaces/{workspace_id}", response_model=ApiResp[WorkspaceResp])(api.update_workspace)
    router.delete("/admin/workspaces/{workspace_id}", response_model=ApiResp[None])(api.delete_workspace)
    router.post("/admin/workspaces/{workspace_id}/members", response_model=ApiResp[MemberResp])(api.add_member)
    router.delete("/admin/workspaces/{workspace_id}/members/{user_id}", response_model=ApiResp[None])(api.remove_member)
    router.get("/admin/workspaces/{workspace_id}/members", response_model=ApiResp[ApiRespPage[MemberResp]])(api.list_members)
    router.get("/admin/stats", response_model=ApiResp[StatsResp])(api.get_stats)

    return router
```

---

## AdminService

```python
# app/services/admin_service.py
from __future__ import annotations
from uuid import uuid4
from datetime import datetime, timezone
from app.runtime import Match3Runtime
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from app.storage.repositories.workspace_repo import WorkspaceRepository
from app.storage.repositories.workspace_member_repo import WorkspaceMemberRepository
from app.storage.repositories.raw_file_repo import RawFileRepository
from app.storage.repositories.wiki_page_repo import WikiPageRepository
from app.storage.repositories.qa_session_repo import QARepository
from app.storage.entities.workspace import Workspace
from app.storage.entities.workspace_member import WorkspaceMember
from app.api.dto.admin_dto import (
    CreateWorkspaceReq, UpdateWorkspaceReq, WorkspaceResp,
    AddMemberReq, MemberResp, StatsResp,
)


class AdminService:

    def __init__(self, rt: Match3Runtime):
        self._rt = rt

    def create_workspace(self, req: CreateWorkspaceReq) -> WorkspaceResp:
        ws_repo = WorkspaceRepository(self._rt.db_engine)
        now = datetime.now(timezone.utc)
        ws = Workspace(
            id=str(uuid4()),
            name=req.name,
            owner_id=req.owner_id,
            description=req.description or "",
            plan=req.plan,
            created_at=now,
            updated_at=now,
        )
        ws = ws_repo.insert(ws)

        # 自动将 owner 以 "owner" 角色添加为成员
        member_repo = WorkspaceMemberRepository(self._rt.db_engine)
        member_repo.insert(WorkspaceMember(
            id=str(uuid4()),
            workspace_id=ws.id,
            user_id=req.owner_id,
            role="owner",
            joined_at=now,
        ))

        return _to_workspace_resp(ws, member_count=1, file_count=0, wiki_page_count=0)

    def list_workspaces(self, page: int, size: int) -> tuple[list[WorkspaceResp], int]:
        ws_repo = WorkspaceRepository(self._rt.db_engine)
        items, total = ws_repo.find_paginated(page=page, size=size)
        return [_to_workspace_resp(ws) for ws in items], total

    def get_workspace(self, workspace_id: str) -> WorkspaceResp:
        ws_repo = WorkspaceRepository(self._rt.db_engine)
        ws = ws_repo.find_by_id(workspace_id)
        if not ws:
            raise Match3Exception.of_code(codes.WORKSPACE_NOT_FOUND).ctx(
                workspace_id=workspace_id,
            )
        return _to_workspace_resp(ws)

    def update_workspace(self, workspace_id: str, req: UpdateWorkspaceReq) -> WorkspaceResp:
        ws_repo = WorkspaceRepository(self._rt.db_engine)
        ws = ws_repo.find_by_id(workspace_id)
        if not ws:
            raise Match3Exception.of_code(codes.WORKSPACE_NOT_FOUND).ctx(
                workspace_id=workspace_id,
            )
        if req.name is not None:
            ws.name = req.name
        if req.description is not None:
            ws.description = req.description
        if req.plan is not None:
            ws.plan = req.plan
        ws.updated_at = datetime.now(timezone.utc)
        ws = ws_repo.update(ws)
        return _to_workspace_resp(ws)

    def delete_workspace(self, workspace_id: str) -> None:
        ws_repo = WorkspaceRepository(self._rt.db_engine)
        ws = ws_repo.find_by_id(workspace_id)
        if not ws:
            raise Match3Exception.of_code(codes.WORKSPACE_NOT_FOUND).ctx(
                workspace_id=workspace_id,
            )
        ws_repo.delete(workspace_id)

    def add_member(self, workspace_id: str, req: AddMemberReq) -> MemberResp:
        ws_repo = WorkspaceRepository(self._rt.db_engine)
        if not ws_repo.find_by_id(workspace_id):
            raise Match3Exception.of_code(codes.WORKSPACE_NOT_FOUND).ctx(
                workspace_id=workspace_id,
            )

        member_repo = WorkspaceMemberRepository(self._rt.db_engine)
        existing = member_repo.find_by_user_workspace(req.user_id, workspace_id)
        if existing:
            # 成员已存在则更新角色
            existing.role = req.role
            member = member_repo.update(existing)
        else:
            now = datetime.now(timezone.utc)
            member = member_repo.insert(WorkspaceMember(
                id=str(uuid4()),
                workspace_id=workspace_id,
                user_id=req.user_id,
                role=req.role,
                joined_at=now,
            ))

        return MemberResp(
            userId=member.user_id,
            workspaceId=member.workspace_id,
            role=member.role,
            joinedAt=member.joined_at.isoformat(),
        )

    def remove_member(self, workspace_id: str, user_id: str) -> None:
        member_repo = WorkspaceMemberRepository(self._rt.db_engine)
        member_repo.delete_by_user_workspace(user_id, workspace_id)

    def list_members(
        self,
        workspace_id: str,
        page: int,
        size: int,
    ) -> tuple[list[MemberResp], int]:
        member_repo = WorkspaceMemberRepository(self._rt.db_engine)
        items, total = member_repo.find_paginated(workspace_id=workspace_id, page=page, size=size)
        return [
            MemberResp(
                userId=m.user_id,
                workspaceId=m.workspace_id,
                role=m.role,
                joinedAt=m.joined_at.isoformat(),
            )
            for m in items
        ], total

    def get_stats(self) -> StatsResp:
        from sqlalchemy import text
        with self._rt.db_engine.connect() as conn:
            try:
                row = conn.execute(text("""
                    SELECT
                      (SELECT COUNT(*) FROM t_workspaces WHERE delete_time IS NULL) AS workspaces,
                      (SELECT COUNT(*) FROM t_raw_files WHERE delete_time IS NULL) AS raw_files,
                      (SELECT COUNT(*) FROM t_text_chunks WHERE delete_time IS NULL) AS chunks,
                      (SELECT COUNT(*) FROM t_wiki_pages WHERE delete_time IS NULL) AS wiki_pages,
                      (SELECT COUNT(*) FROM t_qa_sessions WHERE delete_time IS NULL) AS qa_sessions,
                      (SELECT COALESCE(SUM(size_bytes), 0) FROM t_raw_files WHERE delete_time IS NULL) AS storage
                """)).fetchone()
            except Exception as e:
                raise Match3Exception.of("failed to query admin stats").as_ex(e)

        return StatsResp(
            totalWorkspaces=row[0],
            totalRawFiles=row[1],
            totalChunks=row[2],
            totalWikiPages=row[3],
            totalQaSessions=row[4],
            storageBytes=row[5],
        )


def _to_workspace_resp(
    ws: Workspace,
    member_count: int = 0,
    file_count: int = 0,
    wiki_page_count: int = 0,
) -> WorkspaceResp:
    return WorkspaceResp(
        id=ws.id,
        name=ws.name,
        ownerId=ws.owner_id,
        description=ws.description,
        plan=ws.plan,
        memberCount=member_count,
        fileCount=file_count,
        wikiPageCount=wiki_page_count,
        createdAt=ws.created_at.isoformat(),
    )
```
