# Repository 实现

## 双 ID 约定

每张表有两个 ID 列，Repository 层必须严格遵守使用规则：

| 列 | ORM 属性 | 用途 | Repository 中的使用规则 |
|---|---|---|---|
| `f_id BIGSERIAL PK` | `seq_id` | 数据库内部自增 PK；给存储引擎用 | **禁止**在 `WHERE`、`find_by_id` 等业务查询中使用；仅在极少数需要聚簇扫描的场景下使用 |
| `f_<table>_id VARCHAR UNIQUE` | `id` | 业务 UUID；对外暴露的唯一标识 | 所有按 ID 查找的方法均使用此列；对应 ORM 属性名为 `id` |

**禁止使用 `session.get(Entity, some_id)`**：`session.get()` 按 PK（`seq_id`/`f_id`）查找，而业务传入的都是业务 ID，应使用 `select().where(Entity.id == ...)` 代替。

---

## Repository 双接口模式

所有 Repository 遵循相同的双接口模式：

- **自动提交方法**（`insert`、`find_by_id`、`find_paginated`、`update`、`delete` 等）：
  每个方法自行打开 `Session`，完成操作后自动提交并关闭。
- **事务作用域方法**（`tx_insert`、`tx_update`、`tx_delete` 等）：
  调用方传入已打开的 `Session`；方法完成操作后调用 `flush()`，
  **但不提交**。提交（`session.commit()`）或回滚（`session.rollback()`）由调用方负责。

所有 Repository 的构造函数签名统一为 `def __init__(self, engine: Engine) -> None`。

---

## WorkspaceRepository

**文件**：`app/storage/repositories/workspace_repo.py`

| 方法 | 说明 |
|------|------|
| `insert(entity)` | `session.add → flush → refresh → commit` |
| `find_by_id(workspace_id)` | `WHERE id == ? AND delete_time IS NULL` |
| `find_paginated(page, size)` | `WHERE delete_time IS NULL ORDER BY created_at DESC` → `(items, total)` |
| `update(entity)` | `session.merge → flush → refresh → commit` |
| `delete(workspace_id)` | 软删除：`entity.delete_time = now()` |
| `tx_insert(tx, entity)` | `tx.add → flush → refresh`（不提交） |
| `tx_update(tx, entity)` | `tx.merge → flush → refresh`（不提交） |
| `tx_delete(tx, workspace_id)` | `entity.delete_time = now() → flush`（不提交） |

---

## WorkspaceMemberRepository

**文件**：`app/storage/repositories/workspace_member_repo.py`

| 方法 | 说明 |
|------|------|
| `insert(entity)` | 标准插入 |
| `find_by_id(member_id)` | 按业务 ID 查找 |
| `find_by_user_workspace(user_id, workspace_id)` | 联合查找，用于 upsert 逻辑 |
| `find_paginated(workspace_id, page, size)` | `ORDER BY joined_at ASC` → `(items, total)` |
| `update(entity)` | 标准更新（用于角色变更） |
| `delete_by_user_workspace(user_id, workspace_id)` | **硬删除**：成员关系不使用软删除 |
| `tx_insert` / `tx_update` | 同其他 Repository 的事务变体 |

---

## RawFileRepository

**文件**：`app/storage/repositories/raw_file_repo.py`

| 方法 | 说明 |
|------|------|
| `insert(entity)` | 标准插入 |
| `find_by_id(file_id)` | `WHERE id == ? AND delete_time IS NULL` |
| `find_paginated(workspace_id, page, size, status?, tag?)` | 可选 `status` 过滤；`tag` 用 PostgreSQL `@>` 数组包含操作符（`f_tags @> ARRAY['tag']`）；`ORDER BY created_at DESC` |
| `find_latest_by_topic_tag(topic, workspace_id)` | `WHERE tags @> [topic] ORDER BY created_at DESC LIMIT 1`；用于 Wiki 新鲜度检查 |
| `update(entity)` | 自动刷新 `entity.updated_at = now()` |
| `delete(file_id)` | 软删除 |
| `tx_insert` / `tx_update` / `tx_delete` | 事务变体；`tx_update` 同样刷新 `updated_at` |

---

## TextChunkRepository

**文件**：`app/storage/repositories/text_chunk_repo.py`

| 方法 | 说明 |
|------|------|
| `insert(entity)` | 单条插入 |
| `bulk_insert(entities)` | 单事务批量 `session.add_all`；返回刷新后的列表 |
| `find_by_id(chunk_id)` | 按业务 ID 查找 |
| `find_by_ids(chunk_ids)` | `WHERE id IN (...)` 批量查找；RAG 检索阶段补全 Milvus 命中结果 |
| `find_by_raw_file_id(raw_file_id)` | `ORDER BY chunk_index ASC`；embed/graph task 使用 |
| `find_parent_chunks(child_chunk_ids)` | 两步查询：① 取子块的 `parent_chunk_id` ② `WHERE id IN (parent_ids)`；父子 RAG 使用 |
| `count_by_raw_file_id(raw_file_id)` | `COUNT(id)` |
| `delete_by_raw_file_id(raw_file_id)` | 软删除文件的所有分块，返回删除数量 |
| `tx_bulk_insert` / `tx_delete_by_raw_file_id` | 事务变体 |

---

## QARepository

**文件**：`app/storage/repositories/qa_session_repo.py`

| 方法 | 说明 |
|------|------|
| `insert(entity)` | 标准插入 |
| `find_by_id(session_id)` | `WHERE id == ? AND delete_time IS NULL` |
| `find_paginated(workspace_id, user_id?, page, size)` | 可选 `user_id` 过滤；`ORDER BY created_at DESC` |
| `update(entity)` | 自动刷新 `entity.updated_at = now()` |
| `tx_insert` / `tx_update` | 事务变体；`tx_update` 同样刷新 `updated_at` |

---

## WikiPageRepository

**文件**：`app/storage/repositories/wiki_page_repo.py`

| 方法 | 说明 |
|------|------|
| `insert(entity)` | 标准插入 |
| `find_by_id(page_id)` | `WHERE id == ? AND delete_time IS NULL` |
| `find_by_topic(topic, workspace_id)` | `WHERE topic == ? AND workspace_id == ? AND delete_time IS NULL` |
| `find_paginated(workspace_id, category?, page, size)` | 可选 `category` 过滤；`ORDER BY topic ASC` |
| `update(entity)` | 自动刷新 `updated_at` |
| `upsert(entity)` | 按 `(workspace_id, topic)` 查找：存在则覆盖可变字段（`title / category / status / content / error / compiled_at`），不存在则插入；由编译 Celery 任务调用 |
| `delete(page_id)` | 软删除 |
| `tx_insert` / `tx_update` / `tx_upsert` | 事务变体；`tx_upsert` 逻辑同 `upsert` |

---

## 多操作事务示例

当 Service 需要跨多个 Repository 保证原子性时，打开一个 Session 并传给每个 `tx_` 方法：

```python
with Session(self._rt.db) as tx:
    with tx.begin():           # auto-rollback on exception
        raw_file = raw_file_repo.tx_insert(tx, raw_file)
        chunks = chunk_repo.tx_bulk_insert(tx, chunks)
        raw_file.chunk_count = len(chunks)
        raw_file_repo.tx_update(tx, raw_file)
    # tx.begin() context manager commits here
```

`session.begin()` 返回一个上下文管理器，正常退出时提交，发生任何异常时回滚，
因此在多 Repository 场景下 Service 无需手动调用 `commit()`。
