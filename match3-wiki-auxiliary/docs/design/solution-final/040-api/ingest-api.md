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

**文件**：`app/api/dto/ingest_dto.py`

所有响应字段均使用 camelCase alias（`populate_by_name = True`）。

### UploadResp

| 字段 | 类型 | alias |
|------|------|-------|
| `raw_file_id` | `str` | `rawFileId` |
| `filename` | `str` | — |
| `file_type` | `str` | `fileType` |
| `size_bytes` | `int` | `sizeBytes` |
| `task_id` | `str` | `taskId` |
| `status` | `str` | — | `"pending"` \| `"processing"` \| `"done"` \| `"failed"` |

### TaskStatusResp

| 字段 | 类型 | alias |
|------|------|-------|
| `task_id` | `str` | `taskId` |
| `status` | `str` | — |
| `error` | `str?` | — |
| `progress` | `int?` | — | 0–100，预留字段 |

### RawFileResp

| 字段 | 类型 | alias |
|------|------|-------|
| `id` | `str` | — |
| `workspace_id` | `str` | `workspaceId` |
| `filename` | `str` | — |
| `file_type` | `str` | `fileType` |
| `size_bytes` | `int` | `sizeBytes` |
| `status` | `str` | — |
| `error` | `str?` | — |
| `chunk_count` | `int` | `chunkCount` |
| `pageindex_doc_id` | `str?` | `pageindexDocId` |
| `page_count` | `int?` | `pageCount` |
| `created_at` | `str` | `createdAt` | ISO 8601 |

---

## 路由

**文件**：`app/api/routers/ingest_router.py`

`MAX_FILE_SIZE_BYTES = 500 MB`（超过则抛 `FILE_TOO_LARGE`）

| 方法 | 参数来源 | 转发 |
|------|---------|------|
| `upload` | `file`（form）, `workspaceId`/`userId`/`tags`（query） | `IngestService.upload()` |
| `get_task_status` | `task_id`（path） | `IngestService.get_task_status()` |
| `list_files` | `workspaceId`, `page`, `size`, `status`（query） | `IngestService.list_files()` → `ApiRespPage` |
| `get_file` | `raw_file_id`（path） | `IngestService.get_file()` |
| `delete_file` | `raw_file_id`（path）, `workspaceId`（query） | `IngestService.delete_file()` |

---

## IngestService

**文件**：`app/services/ingest_service.py`

### 支持的文件类型

| MIME 类型 | `file_type` |
|-----------|-------------|
| `application/pdf` | `pdf` |
| `image/jpeg`, `image/png`, `image/gif`, `image/webp` | `image` |
| `video/mp4`, `video/quicktime` | `video` |
| `audio/mpeg`, `audio/wav`, `audio/ogg` | `audio` |
| `text/csv` | `csv` |
| `text/plain` | `text` |
| `text/html` | `html` |
| `text/markdown` | `markdown` |

未匹配时先用 `mimetypes.guess_type(filename)` 推断，仍未知则抛 `UNSUPPORTED_FILE_TYPE`。

### upload()

```
1. MIME 检测 → file_type（未知时 guess_type → UNSUPPORTED_FILE_TYPE）
2. object_key = "{workspace_id}/{raw_file_id}/{filename}"
3. storage.put_object(object_key, data)              # MINIO_ERROR on failure
4. raw_file_repo.insert(RawFile(status=PENDING, ...))
5. ingest_task.apply_async(args=[raw_file_id], queue=QUEUE_INGEST)
6. return UploadResp(rawFileId, taskId, status="pending", ...)
```

### get_task_status()

Celery `AsyncResult` 状态映射：

| Celery 状态 | API status |
|-------------|-----------|
| `PENDING` | `pending` |
| `STARTED` / `RETRY` | `processing` |
| `SUCCESS` | `done` |
| `FAILURE` / `REVOKED` | `failed` |

### delete_file()

```
1. find_by_id(raw_file_id)  → RAW_FILE_NOT_FOUND
2. rf.workspace_id != workspace_id → FORBIDDEN
3. storage.delete_object(rf.object_key)   # MINIO_ERROR on failure
4. raw_file_repo.delete(raw_file_id)      # soft delete
```

### list_files() / get_file()

直接委托 `RawFileRepository`，分别调用 `find_paginated()` 和 `find_by_id()`，结果通过 `_to_raw_file_resp()` 转换为 `RawFileResp`。
