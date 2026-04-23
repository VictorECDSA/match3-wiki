# 导入 API

## 端点

| 方法 | 路径 | 说明 |
|--------|------|-------------|
| POST | `/api/v1/ingest/upload` | 上传文件并触发导入 |
| GET | `/api/v1/ingest/tasks/{task_id}` | 轮询导入任务状态 |
| GET | `/api/v1/ingest/files` | 列出工作区内的原始文件 |
| GET | `/api/v1/ingest/files/{raw_file_id}` | 获取单个原始文件状态 |
| DELETE | `/api/v1/ingest/files/{raw_file_id}` | 删除原始文件及所有派生数据 |

---

## DTO

```python
# app/api/dto/ingest_dto.py
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class UploadResp(BaseModel):
    raw_file_id: str = Field(..., alias="rawFileId")
    filename: str
    file_type: str = Field(..., alias="fileType")
    size_bytes: int = Field(..., alias="sizeBytes")
    task_id: str = Field(..., alias="taskId")
    status: str  # "pending" | "processing" | "done" | "failed"

    class Config:
        populate_by_name = True


class TaskStatusResp(BaseModel):
    task_id: str = Field(..., alias="taskId")
    status: str   # "pending" | "processing" | "done" | "failed"
    error: Optional[str] = None
    progress: Optional[int] = None  # 0-100

    class Config:
        populate_by_name = True


class RawFileResp(BaseModel):
    id: str
    workspace_id: str = Field(..., alias="workspaceId")
    filename: str
    file_type: str = Field(..., alias="fileType")
    size_bytes: int = Field(..., alias="sizeBytes")
    status: str   # "pending" | "processing" | "done" | "failed"
    error: Optional[str] = None
    chunk_count: int = Field(default=0, alias="chunkCount")
    pageindex_doc_id: Optional[str] = Field(default=None, alias="pageindexDocId")
    page_count: Optional[int] = Field(default=None, alias="pageCount")
    created_at: str = Field(..., alias="createdAt")

    class Config:
        populate_by_name = True
```

---

## 路由

```python
# app/api/routers/ingest_router.py
from __future__ import annotations
from fastapi import APIRouter, Request, UploadFile, File, Query, Depends
from app.runtime import Match3Runtime
from app.api.dto.api_resp import ApiResp
from app.api.dto.api_resp_page import ApiRespPage
from app.api.dto.ingest_dto import UploadResp, TaskStatusResp, RawFileResp
from app.services.ingest_service import IngestService
from app.common.exceptions import Match3Exception
from app.common.constants import codes, constants


MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


class IngestAPI:

    def __init__(self, rt: Match3Runtime):
        self._rt = rt
        self._svc = IngestService(rt)

    async def upload(
        self,
        request: Request,
        file: UploadFile = File(...),
        workspace_id: str = Query(..., alias="workspaceId"),
        user_id: str = Query(..., alias="userId"),
        tags: str = Query(default="", description="逗号分隔的主题标签"),
    ) -> ApiResp[UploadResp]:
        request_id = request.state.request_id

        # 校验文件大小
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE_BYTES:
            raise Match3Exception.of_code(codes.FILE_TOO_LARGE).ctx(
                filename=file.filename,
                size=len(contents),
                max=MAX_FILE_SIZE_BYTES,
            )

        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        result = self._svc.upload(
            filename=file.filename,
            content_type=file.content_type,
            data=contents,
            workspace_id=workspace_id,
            user_id=user_id,
            tags=tag_list,
        )
        return ApiResp.ok(request_id=request_id, data=result)

    async def get_task_status(
        self,
        request: Request,
        task_id: str,
    ) -> ApiResp[TaskStatusResp]:
        request_id = request.state.request_id
        result = self._svc.get_task_status(task_id)
        return ApiResp.ok(request_id=request_id, data=result)

    async def list_files(
        self,
        request: Request,
        workspace_id: str = Query(..., alias="workspaceId"),
        page: int = Query(default=1, ge=1),
        size: int = Query(default=20, ge=1, le=100),
        status: str | None = Query(default=None),
    ) -> ApiResp[ApiRespPage[RawFileResp]]:
        request_id = request.state.request_id
        items, total = self._svc.list_files(
            workspace_id=workspace_id,
            page=page,
            size=size,
            status=status,
        )
        page_resp = ApiRespPage.create(items=items, total=total, page=page, size=size)
        return ApiResp.ok(request_id=request_id, data=page_resp)

    async def get_file(
        self,
        request: Request,
        raw_file_id: str,
    ) -> ApiResp[RawFileResp]:
        request_id = request.state.request_id
        result = self._svc.get_file(raw_file_id)
        return ApiResp.ok(request_id=request_id, data=result)

    async def delete_file(
        self,
        request: Request,
        raw_file_id: str,
        workspace_id: str = Query(..., alias="workspaceId"),
    ) -> ApiResp[None]:
        request_id = request.state.request_id
        self._svc.delete_file(raw_file_id, workspace_id)
        return ApiResp.ok(request_id=request_id)


def create(rt: Match3Runtime) -> APIRouter:
    router = APIRouter()
    api = IngestAPI(rt)

    router.post("/ingest/upload", response_model=ApiResp[UploadResp])(api.upload)
    router.get("/ingest/tasks/{task_id}", response_model=ApiResp[TaskStatusResp])(api.get_task_status)
    router.get("/ingest/files", response_model=ApiResp[ApiRespPage[RawFileResp]])(api.list_files)
    router.get("/ingest/files/{raw_file_id}", response_model=ApiResp[RawFileResp])(api.get_file)
    router.delete("/ingest/files/{raw_file_id}", response_model=ApiResp[None])(api.delete_file)

    return router
```

---

## IngestService

```python
# app/services/ingest_service.py
from __future__ import annotations
import mimetypes
from app.runtime import Match3Runtime
from app.common.exceptions import Match3Exception
from app.common.constants import codes, constants
from app.storage.repositories.raw_file_repo import RawFileRepository
from app.storage.entities.raw_file import RawFile, RawFileStatus
from app.workers.ingest_task import ingest_task
from app.api.dto.ingest_dto import UploadResp, TaskStatusResp, RawFileResp
from uuid import uuid4
from datetime import datetime, timezone
import io


SUPPORTED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
    "image/gif": "image",
    "image/webp": "image",
    "video/mp4": "video",
    "video/quicktime": "video",
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/ogg": "audio",
    "text/csv": "csv",
    "text/plain": "text",
    "text/html": "html",
    "text/markdown": "markdown",
}


class IngestService:

    def __init__(self, rt: Match3Runtime):
        self._rt = rt

    def upload(
        self,
        filename: str,
        content_type: str | None,
        data: bytes,
        workspace_id: str,
        user_id: str,
        tags: list[str],
    ) -> UploadResp:
        # 检测文件类型
        if not content_type or content_type not in SUPPORTED_TYPES:
            guessed, _ = mimetypes.guess_type(filename)
            content_type = guessed or content_type

        file_type = SUPPORTED_TYPES.get(content_type or "", "unknown")
        if file_type == "unknown":
            raise Match3Exception.of_code(codes.UNSUPPORTED_FILE_TYPE).ctx(
                filename=filename,
                content_type=content_type,
            )

        # 存入对象存储
        raw_file_id = str(uuid4())
        object_key = f"{workspace_id}/{raw_file_id}/{filename}"

        try:
            self._rt.storage.put_object(object_key, io.BytesIO(data), len(data))
        except Exception as e:
            raise Match3Exception.of_code(codes.MINIO_ERROR).ctx(
                filename=filename,
                step="put_object",
            ).as_ex(e)

        # 创建 RawFile 记录
        now = datetime.now(timezone.utc)
        rf = RawFile(
            id=raw_file_id,
            workspace_id=workspace_id,
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            content_type=content_type or "",
            size_bytes=len(data),
            object_key=object_key,
            tags=tags,
            status=RawFileStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        raw_file_repo = RawFileRepository(self._rt.db_engine)
        rf = raw_file_repo.insert(rf)

        # 入队导入任务
        task = ingest_task.apply_async(
            args=[raw_file_id, workspace_id],
            queue=constants.QUEUE_INGEST,
        )

        return UploadResp(
            rawFileId=raw_file_id,
            filename=filename,
            fileType=file_type,
            sizeBytes=len(data),
            taskId=task.id,
            status="pending",
        )

    def get_task_status(self, task_id: str) -> TaskStatusResp:
        from celery.result import AsyncResult
        result = AsyncResult(task_id)

        status_map = {
            "PENDING": "pending",
            "STARTED": "processing",
            "SUCCESS": "done",
            "FAILURE": "failed",
            "RETRY": "processing",
            "REVOKED": "failed",
        }
        status = status_map.get(result.status, "pending")
        error = str(result.result) if result.status == "FAILURE" else None

        return TaskStatusResp(
            taskId=task_id,
            status=status,
            error=error,
        )

    def list_files(
        self,
        workspace_id: str,
        page: int,
        size: int,
        status: str | None,
    ) -> tuple[list[RawFileResp], int]:
        raw_file_repo = RawFileRepository(self._rt.db_engine)
        items, total = raw_file_repo.find_paginated(
            workspace_id=workspace_id,
            page=page,
            size=size,
            status=status,
        )
        return [_to_raw_file_resp(rf) for rf in items], total

    def get_file(self, raw_file_id: str) -> RawFileResp:
        raw_file_repo = RawFileRepository(self._rt.db_engine)
        rf = raw_file_repo.find_by_id(raw_file_id)
        if not rf:
            raise Match3Exception.of_code(codes.RAW_FILE_NOT_FOUND).ctx(
                raw_file_id=raw_file_id,
            )
        return _to_raw_file_resp(rf)

    def delete_file(self, raw_file_id: str, workspace_id: str) -> None:
        raw_file_repo = RawFileRepository(self._rt.db_engine)
        rf = raw_file_repo.find_by_id(raw_file_id)
        if not rf:
            raise Match3Exception.of_code(codes.RAW_FILE_NOT_FOUND).ctx(
                raw_file_id=raw_file_id,
            )
        if rf.workspace_id != workspace_id:
            raise Match3Exception.of_code(codes.FORBIDDEN).ctx(
                raw_file_id=raw_file_id,
            )

        # 从对象存储中删除
        try:
            self._rt.storage.delete_object(rf.object_key)
        except Exception as e:
            raise Match3Exception.of_code(codes.MINIO_ERROR).ctx(
                raw_file_id=raw_file_id,
                object_key=rf.object_key,
            ).as_ex(e)

        # 软删除记录
        raw_file_repo.delete(raw_file_id)


def _to_raw_file_resp(rf: RawFile) -> RawFileResp:
    return RawFileResp(
        id=rf.id,
        workspaceId=rf.workspace_id,
        filename=rf.filename,
        fileType=rf.file_type,
        sizeBytes=rf.size_bytes,
        status=rf.status,
        error=rf.error,
        chunkCount=rf.chunk_count or 0,
        pageindexDocId=rf.pageindex_doc_id,
        pageCount=rf.page_count,
        createdAt=rf.created_at.isoformat(),
    )
```
