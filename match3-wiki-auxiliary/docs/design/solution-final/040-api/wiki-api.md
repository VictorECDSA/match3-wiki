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

注意：`{topic:path}` 允许主题 slug 中包含斜杠（例如 `entities/royal-match`）。

---

## DTO

**文件**：`app/api/dto/wiki_dto.py`

### CompileReq

| 字段 | 类型 | 说明 |
|------|------|------|
| `topic` | `str` | 主题 slug，如 `entities/royal-match`（1–255 字符）|
| `workspace_id` | `str` | alias: `workspaceId` |
| `force` | `bool` | 默认 `false`；强制重编即使页面已是最新 |

### CompileResp

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | `str` | alias: `taskId` |
| `topic` | `str` | — |
| `status` | `str` | `"queued"` \| `"already_up_to_date"` |

### WikiPageResp

| 字段 | 类型 | alias |
|------|------|-------|
| `id` | `str` | — |
| `topic` | `str` | — |
| `title` | `str` | — |
| `workspace_id` | `str` | `workspaceId` |
| `status` | `str` | — | `"compiling"` \| `"published"` \| `"failed"` |
| `category` | `str?` | — |
| `content` | `str?` | — | 仅 `get_page()` 时返回，列表接口为 null |
| `error` | `str?` | — |
| `compiled_at` | `str?` | `compiledAt` | ISO 8601 |
| `created_at` | `str` | `createdAt` | ISO 8601 |

### WikiTaskStatusResp

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | `str` | alias: `taskId` |
| `topic` | `str` | — |
| `status` | `str` | `"pending"` \| `"compiling"` \| `"published"` \| `"failed"` |
| `error` | `str?` | — |

---

## 路由

**文件**：`app/api/routers/wiki_router.py`

所有方法均委托 `WikiCompileService`，无额外逻辑。

| 方法 | 参数来源 | 转发 |
|------|---------|------|
| `compile` | body: `CompileReq` | `svc.compile(topic, workspace_id, force)` |
| `list_pages` | query: `workspaceId`, `category?`, `page`, `size` | `svc.list_pages()` → `ApiRespPage` |
| `get_page` | path: `topic`, query: `workspaceId` | `svc.get_page()` → `WIKI_NOT_FOUND` if None |
| `recompile` | path: `topic`, body: `workspaceId` | `svc.compile(force=True)` |
| `delete_page` | path: `topic`, query: `workspaceId` | `svc.delete_page()` |
| `get_task_status` | path: `task_id` | `svc.get_task_status()` |

---

## WikiCompileService

**文件**：`app/services/wiki_compile_service.py`

编译触发逻辑见 `030-rag/path-entry.md`。

### get_task_status()

`task_id` 有两种形式：

| 形式 | 处理方式 |
|------|---------|
| `"wiki_page:{id}"` 哨兵值 | 查 `wiki_repo.find_by_id(id)`，取 `page.status` |
| Celery 任务 ID | `AsyncResult(task_id).status` → 映射为 `pending/compiling/published/failed` |

### get_stats() SQL

```sql
SELECT
  COUNT(*) FROM t_workspaces  WHERE delete_time IS NULL,
  COUNT(*) FROM t_raw_files   WHERE delete_time IS NULL,
  COUNT(*) FROM t_text_chunks WHERE delete_time IS NULL,
  COUNT(*) FROM t_wiki_pages  WHERE delete_time IS NULL,
  COUNT(*) FROM t_qa_sessions WHERE delete_time IS NULL,
  COALESCE(SUM(size_bytes), 0) FROM t_raw_files WHERE delete_time IS NULL
```

（单次查询，返回 `StatsResp`）
