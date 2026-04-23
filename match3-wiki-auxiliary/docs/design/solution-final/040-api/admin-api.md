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
| GET | `/api/v1/admin/stats` | 全系统统计数据 |

---

## DTO

**文件**：`app/api/dto/admin_dto.py`

### CreateWorkspaceReq / UpdateWorkspaceReq

| 字段 | 类型 | alias | 说明 |
|------|------|-------|------|
| `name` | `str` | — | 1–100 字符（Create 必填，Update 可选）|
| `owner_id` | `str` | `ownerId` | Create 必填 |
| `description` | `str?` | — | 最长 500 字符 |
| `plan` | `str` | — | `"free"` \| `"pro"` \| `"enterprise"`，默认 `"free"` |

### WorkspaceResp

| 字段 | alias | 字段 | alias |
|------|-------|------|-------|
| `id` | — | `plan` | — |
| `name` | — | `member_count` | `memberCount` |
| `owner_id` | `ownerId` | `file_count` | `fileCount` |
| `description` | — | `wiki_page_count` | `wikiPageCount` |
| `created_at` | `createdAt` | — | — |

### AddMemberReq / MemberResp

| 字段 | 类型 | alias | 说明 |
|------|------|-------|------|
| `user_id` | `str` | `userId` | — |
| `workspace_id` | `str` | `workspaceId` | Response only |
| `role` | `str` | — | `"owner"` \| `"admin"` \| `"member"` \| `"viewer"` |
| `joined_at` | `str` | `joinedAt` | Response only，ISO 8601 |

### StatsResp

| 字段 | alias |
|------|-------|
| `total_workspaces` | `totalWorkspaces` |
| `total_raw_files` | `totalRawFiles` |
| `total_chunks` | `totalChunks` |
| `total_wiki_pages` | `totalWikiPages` |
| `total_qa_sessions` | `totalQaSessions` |
| `storage_bytes` | `storageBytes` |

---

## 路由

**文件**：`app/api/routers/admin_router.py`

所有方法均直接委托 `AdminService`，无额外逻辑。

---

## AdminService

**文件**：`app/services/admin_service.py`

| 方法 | 核心逻辑 |
|------|---------|
| `create_workspace(req)` | `uuid4()` 生成 ID → `ws_repo.insert()` → 自动以 `"owner"` 角色插入 `member_repo` |
| `list_workspaces(page, size)` | `ws_repo.find_paginated()` |
| `get_workspace(workspace_id)` | `ws_repo.find_by_id()` → `WORKSPACE_NOT_FOUND` if None |
| `update_workspace(workspace_id, req)` | `find_by_id` + 有值则更新 `name/description/plan` + `ws_repo.update()` |
| `delete_workspace(workspace_id)` | `find_by_id` → `ws_repo.delete()` |
| `add_member(workspace_id, req)` | 工作区存在性检查 → `find_by_user_workspace`：已存在则更新角色，否则 `insert` |
| `remove_member(workspace_id, user_id)` | `member_repo.delete_by_user_workspace()` |
| `list_members(workspace_id, page, size)` | `member_repo.find_paginated()` |
| `get_stats()` | 单次 SQL，COUNT 五张表 + SUM `size_bytes`（见下） |

### get_stats() SQL

```sql
SELECT
  (SELECT COUNT(*) FROM t_workspaces  WHERE delete_time IS NULL),
  (SELECT COUNT(*) FROM t_raw_files   WHERE delete_time IS NULL),
  (SELECT COUNT(*) FROM t_text_chunks WHERE delete_time IS NULL),
  (SELECT COUNT(*) FROM t_wiki_pages  WHERE delete_time IS NULL),
  (SELECT COUNT(*) FROM t_qa_sessions WHERE delete_time IS NULL),
  (SELECT COALESCE(SUM(size_bytes), 0) FROM t_raw_files WHERE delete_time IS NULL)
```
