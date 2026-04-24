# PostgreSQL 数据库结构

## 双 ID 约定

每张表都遵循与 anim-facade 一致的双 ID 规范：

| 列 | 类型 | 职责 | 是否对外暴露 |
|---|---|---|---|
| `f_id` | `BIGSERIAL PRIMARY KEY` | 数据库内部自增整型主键；给数据库引擎用（B-tree 效率、WAL、聚簇索引）；**永不出现在 API 响应、日志、URL 里** | ❌ 绝不暴露 |
| `f_<table>_id` | `VARCHAR(64) NOT NULL UNIQUE` | 业务 ID（UUID）；API 入参出参、跨服务引用、日志排查全部用这一个；不暴露行号，安全可枚举 | ✅ 唯一对外标识 |

FK 引用关系一律引用对方的**业务 ID 列**（`VARCHAR(64)`），不引用内部 `f_id`。

---

## 数据表概览

| 数据表 | 核心职责 |
|-------|---------|
| `t_workspaces` | 多租户隔离的顶层单元；系统内所有数据（文件、分块、问答、Wiki）都归属于某个工作区 |
| `t_workspace_members` | 记录用户与工作区的多对多归属关系及其角色；RBAC 权限判断的依据 |
| `t_raw_files` | 每次上传文件的元数据与导入状态机；是导入流水线的起点和贯穿全程的状态载体 |
| `t_text_chunks` | 从原始文件切分出的文本单元；PostgreSQL 存内容，Milvus 存向量，ES 存倒排，三者以 `f_chunk_id` 对齐 |
| `t_qa_sessions` | 每次问答请求的完整记录；保存问题、答案、RAG 路径和来源，支持历史查看和效果分析 |
| `t_wiki_pages` | LLM 编译生成的 Wiki 词条页面；以 `(workspace_id, topic)` 为唯一键，支持重新编译覆盖 |

---

## ORM 基类

**文件**：`app/storage/orm_base.py`

```python
from sqlalchemy.orm import DeclarativeBase

class ORMBase(DeclarativeBase):
    pass
```

---

## 实体类

### Workspace — 工作区

**表名**：`t_workspaces` | **文件**：`app/storage/entities/workspace.py`

**作用**：系统的多租户隔离单元。每个团队或项目拥有一个独立工作区，工作区内的文件、分块、问答记录、Wiki 页面互相隔离。所有带 `workspace_id` 过滤的查询都依赖本表的 `f_workspace_id`。

| 列（ORM 属性） | 类型 | 说明 |
|--------------|------|------|
| `f_id` (`seq_id`) | `BIGSERIAL PK` | 数据库内部自增 PK，仅供引擎使用，从不对外暴露 |
| `f_workspace_id` (`id`) | `VARCHAR(64) UNIQUE` | 业务 UUID；API 响应、跨表 FK、日志排查都用这个值 |
| `f_name` (`name`) | `VARCHAR(100)` | 工作区显示名称 |
| `f_owner_id` (`owner_id`) | `VARCHAR(64)` | 创建者的用户业务 ID（来自认证系统） |
| `f_description` (`description`) | `VARCHAR(500)` | 描述，默认 `""` |
| `f_plan` (`plan`) | `VARCHAR(32)` | `"free"` \| `"pro"` \| `"enterprise"`，默认 `"free"` |
| `f_created_at` / `f_updated_at` | `DateTime(tz)` | 创建/最后修改时间 |
| `f_delete_time` (`delete_time`) | `DateTime(tz)?` | 软删除时间戳；`NULL` = 活跃 |

**索引**：`f_workspace_id`、`f_owner_id`、`f_delete_time`

---

### WorkspaceMember — 工作区成员

**表名**：`t_workspace_members` | **文件**：`app/storage/entities/workspace_member.py`

**作用**：记录用户和工作区之间的多对多归属关系。RBAC 中间件查询本表，判断当前用户对目标工作区拥有哪个角色。

| 列（ORM 属性） | 类型 | 说明 |
|--------------|------|------|
| `f_id` (`seq_id`) | `BIGSERIAL PK` | 内部自增 PK |
| `f_member_id` (`id`) | `VARCHAR(64) UNIQUE` | 本条成员关系记录的业务 UUID |
| `f_workspace_id` (`workspace_id`) | `VARCHAR(64)` | FK → `t_workspaces.f_workspace_id` |
| `f_user_id` (`user_id`) | `VARCHAR(64)` | FK → 认证系统用户业务 ID |
| `f_role` (`role`) | `VARCHAR(32)` | `"owner"` \| `"admin"` \| `"member"`，默认 `"member"` |
| `f_joined_at` (`joined_at`) | `DateTime(tz)` | 加入时间；成员列表按此字段排序 |

**约束**：`uq_workspace_member (f_workspace_id, f_user_id)` — 防止同一用户重复加入同一工作区

**索引**：`f_member_id`、`f_workspace_id`、`f_user_id`

---

### RawFile — 原始文件

**表名**：`t_raw_files` | **文件**：`app/storage/entities/raw_file.py`

**作用**：记录每次文件上传的元数据，以及该文件在导入流水线中的实时状态（状态机）。`f_tags` 用于 Wiki 新鲜度检查和 Milvus 标量过滤。PageIndex 相关字段缓存目录树，避免重复调用外部 API。

```python
class RawFileStatus(str, Enum):
    PENDING = "pending"; PROCESSING = "processing"; DONE = "done"; FAILED = "failed"
```

| 列（ORM 属性） | 类型 | 说明 |
|--------------|------|------|
| `f_id` (`seq_id`) | `BIGSERIAL PK` | 内部自增 PK |
| `f_raw_file_id` (`id`) | `VARCHAR(64) UNIQUE` | 业务 UUID；在 MinIO object key、Milvus 标量过滤字段、`t_text_chunks` FK 中使用 |
| `f_workspace_id` (`workspace_id`) | `VARCHAR(64)` | FK → `t_workspaces`；租户隔离键 |
| `f_user_id` (`user_id`) | `VARCHAR(64)` | 上传者用户 ID |
| `f_filename` (`filename`) | `VARCHAR(512)` | 原始文件名 |
| `f_file_type` (`file_type`) | `VARCHAR(32)` | `pdf / image / video / audio / html / csv / markdown` |
| `f_content_type` (`content_type`) | `VARCHAR(128)` | MIME 类型，如 `application/pdf` |
| `f_size_bytes` (`size_bytes`) | `Integer` | 文件大小（字节） |
| `f_object_key` (`object_key`) | `VARCHAR(512)` | MinIO 对象 key：`{workspace_id}/{raw_file_id}/{filename}` |
| `f_tags` (`tags`) | `ARRAY(Text)` | 主题标签，如 `["entities/royal-match"]`；GIN 索引支持 `@>` 数组包含查询 |
| `f_status` (`status`) | `VARCHAR(32)` | `RawFileStatus`：`PENDING → PROCESSING → DONE / FAILED` |
| `f_error` (`error`) | `Text?` | 失败时的错误信息 |
| `f_chunk_count` (`chunk_count`) | `Integer` | 分块完成后的实际数量，默认 0 |
| `f_use_pageindex` (`use_pageindex`) | `Boolean` | 是否已向 PageIndex 注册（PDF 页数 ≥ 阈值时为 `True`）|
| `f_pageindex_doc_id` (`pageindex_doc_id`) | `VARCHAR(255)?` | VectifyAI 文档 ID |
| `f_pageindex_tree` (`pageindex_tree`) | `JSONB?` | 缓存的层级目录树，避免重复调用 `get_tree()` |
| `f_page_count` (`page_count`) | `Integer?` | PDF 总页数 |
| `f_created_at` / `f_updated_at` | `DateTime(tz)` | 创建/最后状态更新时间 |
| `f_delete_time` (`delete_time`) | `DateTime(tz)?` | 软删除时间戳 |

**索引**：`f_raw_file_id`、`f_workspace_id`、`f_status`、`f_delete_time`、`f_tags`（GIN）

---

### TextChunk — 文本块

**表名**：`t_text_chunks` | **文件**：`app/storage/entities/text_chunk.py`

**作用**：存储从原始文件切分出的每一个文本单元。本表是文本内容和父子关系的**唯一权威来源**；Milvus 存同一块的向量（以 `f_chunk_id` 对齐），ES 存同一块的倒排索引（以 `f_chunk_id` 作为文档 `_id`）。三者必须保持一致。

| 列（ORM 属性） | 类型 | 说明 |
|--------------|------|------|
| `f_id` (`seq_id`) | `BIGSERIAL PK` | 内部自增 PK |
| `f_chunk_id` (`id`) | `VARCHAR(64) UNIQUE` | 业务 UUID；必须与 Milvus `id` 字段和 ES 文档 `_id` 完全一致 |
| `f_workspace_id` (`workspace_id`) | `VARCHAR(64)` | FK → `t_workspaces`；检索时 Milvus/ES 均用此做标量过滤 |
| `f_raw_file_id` (`raw_file_id`) | `VARCHAR(64)` | FK → `t_raw_files.f_raw_file_id`；按文件批量操作分块 |
| `f_parent_chunk_id` (`parent_chunk_id`) | `VARCHAR(64)?` | 自引用 → 同表 `f_chunk_id`；`NULL` 表示顶层块；父子 RAG 使用 |
| `f_chunk_index` (`chunk_index`) | `Integer` | 在原始文件中的顺序编号（0-based） |
| `f_chunk_type` (`chunk_type`) | `VARCHAR(32)` | `"text"` \| `"image"` \| `"parent"`；决定向量化策略 |
| `f_content` (`content`) | `Text` | 原始文本、图片描述或语音转写内容 |
| `f_token_count` (`token_count`) | `Integer` | 近似 token 数；LLM 上下文预算管理使用 |
| `f_topic_tags` (`topic_tags`) | `ARRAY(Text)` | 从父 `RawFile.tags` 继承；Milvus 标量过滤支持 `topic_tags IN [...]` |
| `f_created_at` | `DateTime(tz)` | 分块创建时间 |
| `f_delete_time` (`delete_time`) | `DateTime(tz)?` | 软删除时间戳 |

**索引**：`f_chunk_id`、`f_workspace_id`、`f_raw_file_id`、`f_parent_chunk_id`、`f_delete_time`、`f_topic_tags`（GIN）

---

### QASession — 问答会话

**表名**：`t_qa_sessions` | **文件**：`app/storage/entities/qa_session.py`

**作用**：记录每一次用户问答的完整生命周期。服务三个场景：历史记录展示、RAG 路径效果分析、故障排查。

```python
class QASessionStatus(str, Enum):
    GENERATING = "generating"; DONE = "done"; FAILED = "failed"
```

| 列（ORM 属性） | 类型 | 说明 |
|--------------|------|------|
| `f_id` (`seq_id`) | `BIGSERIAL PK` | 内部自增 PK |
| `f_session_id` (`id`) | `VARCHAR(64) UNIQUE` | 业务 UUID；SSE 流开始前写入，前端用此 ID 查历史 |
| `f_workspace_id` (`workspace_id`) | `VARCHAR(64)` | FK → `t_workspaces`；历史记录按工作区过滤 |
| `f_user_id` (`user_id`) | `VARCHAR(64)` | 提问者用户 ID |
| `f_query` (`query`) | `Text` | 用户原始问题文本 |
| `f_rag_path` (`rag_path`) | `VARCHAR(32)` | `"chunk"` \| `"entry"` \| `"page"` |
| `f_rag_method` (`rag_method`) | `VARCHAR(32)?` | hybrid-search 下的具体方法（如 `"hybrid"` / `"graph_rag"`） |
| `f_status` (`status`) | `VARCHAR(32)` | `GENERATING`（流中，answer 为 NULL）→ `DONE` / `FAILED` |
| `f_answer` (`answer`) | `Text?` | 流式结束后写入的完整回答 |
| `f_source_chunk_ids` (`source_chunk_ids`) | `ARRAY(Text)?` | 来源分块 ID 数组；前端渲染"来源引用"面板 |
| `f_error` (`error`) | `Text?` | 失败时的错误信息 |
| `f_created_at` / `f_updated_at` | `DateTime(tz)` | 创建/最后更新时间 |
| `f_delete_time` (`delete_time`) | `DateTime(tz)?` | 软删除时间戳 |

**索引**：`f_session_id`、`f_workspace_id`、`f_user_id`、`f_created_at`、`f_delete_time`

---

### WikiPage — Wiki 词条页面

**表名**：`t_wiki_pages` | **文件**：`app/storage/entities/wiki_page.py`

**作用**：存储 LLM 编译生成的 Wiki 知识页面。以 `(workspace_id, topic)` 作为业务唯一键，支持重新编译覆盖。`status` 字段充当编译任务的进度载体，`content` 存储带 `[[wikilinks]]` 标记的 Markdown 正文。

```python
class WikiPageStatus(str, Enum):
    QUEUED = "queued"; COMPILING = "compiling"; PUBLISHED = "published"; FAILED = "failed"
```

| 列（ORM 属性） | 类型 | 说明 |
|--------------|------|------|
| `f_id` (`seq_id`) | `BIGSERIAL PK` | 内部自增 PK |
| `f_page_id` (`id`) | `VARCHAR(64) UNIQUE` | 业务 UUID；API 响应中作为页面句柄 |
| `f_workspace_id` (`workspace_id`) | `VARCHAR(64)` | FK → `t_workspaces`；租户隔离键 |
| `f_topic` (`topic`) | `VARCHAR(255)` | URL slug / 查询键，如 `"royal-match"`；与 `workspace_id` 构成联合唯一键 |
| `f_title` (`title`) | `VARCHAR(255)` | 页面显示标题，如 `"Royal Match"` |
| `f_category` (`category`) | `VARCHAR(64)?` | 可选分类：`"entities"` \| `"mechanics"` \| `"market"` |
| `f_status` (`status`) | `VARCHAR(32)` | `QUEUED → COMPILING → PUBLISHED / FAILED`；前端轮询此字段 |
| `f_content` (`content`) | `Text?` | 编译生成的 Markdown（含 `[[wikilinks]]`）；`PUBLISHED` 后可读 |
| `f_source_chunk_ids` (`source_chunk_ids`) | `ARRAY(Text)?` | 编译时使用的分块 ID；前端"数据来源"面板使用 |
| `f_error` (`error`) | `Text?` | 编译失败时的错误信息 |
| `f_compiled_at` (`compiled_at`) | `DateTime(tz)?` | 最近一次成功编译的时间戳；前端展示新鲜度 |
| `f_created_at` / `f_updated_at` | `DateTime(tz)` | 首次创建/最后修改时间 |
| `f_delete_time` (`delete_time`) | `DateTime(tz)?` | 软删除时间戳 |

**约束**：`uq_wiki_page_workspace_topic (f_workspace_id, f_topic)` — 保证工作区内每个主题只有一个词条

**索引**：`f_page_id`、`f_workspace_id`、`f_topic`、`f_category`、`f_delete_time`

---

## 关于 DDL

**不需要手写 DDL，也不需要维护 `create-tables.sql` 文件。**

原因：ORM 实体类是数据库结构的**唯一权威来源**。Alembic 会自动对比 ORM 元数据与数据库现状，生成精确的迁移脚本。

### 迁移目录结构

```
backend/
  alembic/
    env.py
    versions/
      0001_initial_schema.py   ← generated by: alembic revision --autogenerate
```

### alembic/env.py（关键配置）

```python
from app.storage.orm_base import ORMBase
import app.storage.entities  # noqa: F401 — import all entity modules to register metadata

target_metadata = ORMBase.metadata
```

必须 `import app.storage.entities` 以确保所有实体类的元数据注册到 `ORMBase.metadata`，否则 autogenerate 无法感知这些表。

### 常用命令

```bash
alembic revision --autogenerate -m "initial schema"   # first init
alembic upgrade head                                   # apply all migrations
alembic revision --autogenerate -m "add field"        # after ORM changes
alembic current                                        # show current version
```
