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

```python
# app/storage/orm_base.py
from sqlalchemy.orm import DeclarativeBase


class ORMBase(DeclarativeBase):
    pass
```

---

## 实体类

### Workspace — 工作区

**表的作用**：系统的多租户隔离单元。每个团队或项目拥有一个独立工作区，工作区内的文件、分块、问答记录、Wiki 页面互相隔离，不同工作区之间的数据无法互查。所有带 `workspace_id` 过滤的查询都依赖本表的 `f_workspace_id`。

```python
# app/storage/entities/workspace.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.orm_base import ORMBase


class Workspace(ORMBase):
    __tablename__ = "t_workspaces"

    seq_id: Mapped[int] = mapped_column("f_id", BigInteger, primary_key=True, autoincrement=True)
    # 数据库内部自增主键；仅供引擎使用，永不对外暴露

    id: Mapped[str] = mapped_column("f_workspace_id", String(64), unique=True, nullable=False)
    # 业务 UUID；API 响应、跨服务引用等对外场景唯一使用此值

    name: Mapped[str] = mapped_column("f_name", String(100), nullable=False)
    owner_id: Mapped[str] = mapped_column("f_owner_id", String(64), nullable=False)
    # owner_id 引用认证系统的用户业务 ID（非内部自增主键）
    description: Mapped[str] = mapped_column("f_description", String(500), nullable=False, default="")
    plan: Mapped[str] = mapped_column("f_plan", String(32), nullable=False, default="free")
    # "free" | "pro" | "enterprise"
    created_at: Mapped[datetime] = mapped_column("f_created_at", DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("f_updated_at", DateTime(timezone=True), nullable=False)
    delete_time: Mapped[Optional[datetime]] = mapped_column(
        "f_delete_time", DateTime(timezone=True), nullable=True
    )  # 软删除时间戳；NULL 表示活跃记录

    __table_args__ = (
        Index("idx_workspaces_workspace_id", "f_workspace_id"),
        Index("idx_workspaces_owner_id", "f_owner_id"),
        Index("idx_workspaces_delete_time", "f_delete_time"),
    )
```

**字段说明**

| 字段 | 作用 |
|------|------|
| `f_id` | 数据库内部自增 PK，仅供引擎使用，从不对外暴露 |
| `f_workspace_id` | 业务 UUID，API 响应、跨表 FK、日志排查都用这个值 |
| `f_name` | 工作区显示名称，前端展示和列表搜索用 |
| `f_owner_id` | 创建者的用户业务 ID（来自认证系统），决定谁有最高权限 |
| `f_description` | 工作区描述，前端展示用，默认为空字符串 |
| `f_plan` | 订阅计划（`free / pro / enterprise`），用于限流、功能开关判断 |
| `f_created_at` | 创建时间，带时区，用于列表排序 |
| `f_updated_at` | 最后修改时间，每次 update 时刷新 |
| `f_delete_time` | 软删除时间戳；`NULL` 表示活跃，非 `NULL` 表示已删除；所有查询都加 `delete_time IS NULL` 过滤 |

---

### WorkspaceMember — 工作区成员

**表的作用**：记录用户和工作区之间的多对多归属关系。每条记录表示"某个用户以某种角色加入了某个工作区"。RBAC 中间件在鉴权时查询本表，判断当前用户对目标工作区拥有哪个角色，进而决定是否允许该操作。

```python
# app/storage/entities/workspace_member.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.orm_base import ORMBase


class WorkspaceMember(ORMBase):
    __tablename__ = "t_workspace_members"

    seq_id: Mapped[int] = mapped_column("f_id", BigInteger, primary_key=True, autoincrement=True)
    # 数据库内部自增主键；仅供引擎使用，永不对外暴露

    id: Mapped[str] = mapped_column("f_member_id", String(64), unique=True, nullable=False)
    # 本条成员关系记录的业务 UUID

    workspace_id: Mapped[str] = mapped_column("f_workspace_id", String(64), nullable=False)
    # 引用 t_workspaces.f_workspace_id（业务 UUID，非内部自增主键）
    user_id: Mapped[str] = mapped_column("f_user_id", String(64), nullable=False)
    # 引用认证系统用户业务 ID
    role: Mapped[str] = mapped_column("f_role", String(32), nullable=False, default="member")
    # "owner" | "admin" | "member"
    joined_at: Mapped[datetime] = mapped_column("f_joined_at", DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("f_workspace_id", "f_user_id", name="uq_workspace_member"),
        Index("idx_workspace_members_member_id", "f_member_id"),
        Index("idx_workspace_members_workspace_id", "f_workspace_id"),
        Index("idx_workspace_members_user_id", "f_user_id"),
    )
```

**字段说明**

| 字段 | 作用 |
|------|------|
| `f_id` | 数据库内部自增 PK，仅供引擎使用 |
| `f_member_id` | 本条成员关系记录的业务 UUID，移除成员时作为操作目标 |
| `f_workspace_id` | FK → `t_workspaces.f_workspace_id`；标识归属哪个工作区 |
| `f_user_id` | FK → 认证系统用户业务 ID；标识是哪个用户 |
| `f_role` | 角色（`owner / admin / member`）；RBAC 中间件据此判断操作权限，`owner` 拥有全部权限，`member` 只读 |
| `f_joined_at` | 加入时间，成员列表按此字段排序展示 |
| `uq_workspace_member` | `(workspace_id, user_id)` 联合唯一约束，防止同一用户重复加入同一工作区 |

---

### RawFile — 原始文件

**表的作用**：记录每次文件上传的元数据，以及该文件在导入流水线中的实时状态。是整个导入流程的"状态机"——`status` 字段从 `PENDING` 逐步推进到 `DONE`，Worker 通过轮询或任务回调更新此字段。前端通过轮询本表展示导入进度。PageIndex 长文档专用的目录树结构也缓存在本表的 `f_pageindex_tree` 字段，查询时无需重复请求外部 API。

```python
# app/storage/entities/raw_file.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import BigInteger, String, Integer, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from app.storage.orm_base import ORMBase


class RawFileStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class RawFile(ORMBase):
    __tablename__ = "t_raw_files"

    seq_id: Mapped[int] = mapped_column("f_id", BigInteger, primary_key=True, autoincrement=True)
    # 数据库内部自增主键；仅供引擎使用，永不对外暴露

    id: Mapped[str] = mapped_column("f_raw_file_id", String(64), unique=True, nullable=False)
    # 业务 UUID；用于 API 响应、MinIO object key 前缀、Milvus 标量过滤字段

    workspace_id: Mapped[str] = mapped_column("f_workspace_id", String(64), nullable=False)
    # 引用 t_workspaces.f_workspace_id（业务 UUID）；租户隔离键
    user_id: Mapped[str] = mapped_column("f_user_id", String(64), nullable=False)
    # 上传者；引用认证系统用户业务 ID
    filename: Mapped[str] = mapped_column("f_filename", String(512), nullable=False)
    file_type: Mapped[str] = mapped_column("f_file_type", String(32), nullable=False)
    # constants.FILE_TYPE_*: "pdf" | "image" | "video" | "audio" | "html" | "csv" | "markdown"
    content_type: Mapped[str] = mapped_column("f_content_type", String(128), nullable=False, default="")
    # MIME 类型，如 "application/pdf"
    size_bytes: Mapped[int] = mapped_column("f_size_bytes", Integer, nullable=False)
    object_key: Mapped[str] = mapped_column("f_object_key", String(512), nullable=False)
    # MinIO object key："{workspace_id}/{raw_file_id}/{filename}"

    tags: Mapped[list] = mapped_column("f_tags", ARRAY(Text), nullable=False, default=list)
    # 主题标签，如 ["entities/royal-match", "market/puzzle"]

    status: Mapped[str] = mapped_column("f_status", String(32), nullable=False)
    # RawFileStatus: "pending" | "processing" | "done" | "failed"
    error: Mapped[Optional[str]] = mapped_column("f_error", Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column("f_chunk_count", Integer, nullable=False, default=0)

    # PageIndex 元数据（仅 PDF 且页数 >= 阈值时填充）
    use_pageindex: Mapped[bool] = mapped_column("f_use_pageindex", nullable=False, default=False)
    # True 表示该文件已向 PageIndex 注册，可走 doc-navigate 路径（同时仍走 hybrid-search 路径）
    pageindex_doc_id: Mapped[Optional[str]] = mapped_column(
        "f_pageindex_doc_id", String(255), nullable=True
    )  # VectifyAI 文档 ID；PageIndex.add() 成功后填充
    pageindex_tree: Mapped[Optional[dict]] = mapped_column("f_pageindex_tree", JSONB, nullable=True)
    # 从 PageIndex API 缓存的层级目录树；避免每次查询重复调用 get_tree()
    page_count: Mapped[Optional[int]] = mapped_column("f_page_count", Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column("f_created_at", DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("f_updated_at", DateTime(timezone=True), nullable=False)
    delete_time: Mapped[Optional[datetime]] = mapped_column(
        "f_delete_time", DateTime(timezone=True), nullable=True
    )  # 软删除时间戳；NULL 表示活跃记录

    __table_args__ = (
        Index("idx_raw_files_raw_file_id", "f_raw_file_id"),
        Index("idx_raw_files_workspace_id", "f_workspace_id"),
        Index("idx_raw_files_status", "f_status"),
        Index("idx_raw_files_delete_time", "f_delete_time"),
        Index("idx_raw_files_tags", "f_tags", postgresql_using="gin"),
    )
```

**字段说明**

| 字段 | 作用 |
|------|------|
| `f_id` | 数据库内部自增 PK，仅供引擎使用 |
| `f_raw_file_id` | 业务 UUID；在 MinIO object key、Milvus 标量过滤字段 `raw_file_id`、`t_text_chunks.f_raw_file_id` FK 中使用 |
| `f_workspace_id` | FK → `t_workspaces.f_workspace_id`；所有文件列表查询都加此过滤，实现工作区数据隔离 |
| `f_user_id` | 上传者用户 ID；用于"我的文件"过滤和操作权限审计 |
| `f_filename` | 原始文件名，前端文件列表展示用 |
| `f_file_type` | 文件类型枚举（`pdf / image / video / audio / html / csv / markdown`）；ingest_task 根据此字段分支选择解析策略 |
| `f_content_type` | HTTP MIME 类型，如 `application/pdf`；前端下载文件时设置 Content-Type 响应头使用 |
| `f_size_bytes` | 文件大小（字节）；前端展示，亦可用于配额限制 |
| `f_object_key` | MinIO 对象 key（格式 `{workspace_id}/{raw_file_id}/{filename}`）；Worker 读取原始文件时使用此 key 调用 `get_object()` |
| `f_tags` | 主题标签数组（如 `["entities/royal-match", "market/puzzle"]`）；上传时由用户指定，用于 Wiki 新鲜度检查（`find_latest_by_topic_tag`）和 Milvus 标量过滤（精准检索某个主题的分块） |
| `f_status` | 导入流水线状态机：`PENDING → PROCESSING → DONE`，或任意阶段失败变为 `FAILED`；前端据此展示进度条 |
| `f_error` | 失败时的错误信息；`FAILED` 状态时由 Worker 写入，前端展示错误详情 |
| `f_chunk_count` | 分块完成后写入的实际分块数量；前端展示，亦可用于估算检索覆盖范围 |
| `f_use_pageindex` | 是否已向 PageIndex 注册（`true` = PDF 页数 ≥ 阈值且注册成功）；表示该文件既可走 hybrid-search 路径，也可走 doc-navigate 路径 |
| `f_pageindex_doc_id` | VectifyAI API 返回的文档 ID；doc-navigate 检索时调用 `get_tree(doc_id)` 和 `get_page_content(doc_id, node_id)` 需要此值 |
| `f_pageindex_tree` | 从 PageIndex API 获取的层级目录树（JSONB）；缓存在此避免每次查询都调外部 API，加快响应速度 |
| `f_page_count` | PDF 总页数；导入时检测，与配置阈值比较决定是否走 PageIndex 路径 |
| `f_created_at` | 上传时间，文件列表默认按此降序排列 |
| `f_updated_at` | 最后状态更新时间，Worker 每次推进 status 时刷新 |
| `f_delete_time` | 软删除时间戳；删除文件时置为当前时间，同时触发 Milvus 和 ES 的异步清理任务 |

---

### TextChunk — 文本块

**表的作用**：存储从原始文件切分出的每一个文本单元（文本块、图片描述、语音转写片段），是 RAG 检索的核心数据基础。本表是文本内容和父子关系的**唯一权威来源**；Milvus 存同一块的向量（以 `f_chunk_id` 对齐），ES 存同一块的倒排索引（以 `f_chunk_id` 作为文档 `_id`）。三者必须保持一致：向量检索和全文检索返回的 ID 列表，最终都要来本表查询 `content` 字段才能组装上下文。

```python
# app/storage/entities/text_chunk.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Integer, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY
from app.storage.orm_base import ORMBase


class TextChunk(ORMBase):
    """
    文本块元数据与内容。
    稠密/稀疏向量存储在 Milvus（字段：id = f_chunk_id）。
    全文内容在 Elasticsearch 中建立倒排索引（文档 id = f_chunk_id）。
    本表是内容和父子关系的唯一权威来源。
    """
    __tablename__ = "t_text_chunks"

    seq_id: Mapped[int] = mapped_column("f_id", BigInteger, primary_key=True, autoincrement=True)
    # 数据库内部自增主键；仅供引擎使用，永不对外暴露

    id: Mapped[str] = mapped_column("f_chunk_id", String(64), unique=True, nullable=False)
    # 业务 UUID；与 Milvus 向量 ID（anns 字段）和 ES 文档 _id 保持一致

    workspace_id: Mapped[str] = mapped_column("f_workspace_id", String(64), nullable=False)
    # 引用 t_workspaces.f_workspace_id；租户隔离键
    raw_file_id: Mapped[str] = mapped_column("f_raw_file_id", String(64), nullable=False)
    # 引用 t_raw_files.f_raw_file_id（业务 UUID，非内部自增主键）
    parent_chunk_id: Mapped[Optional[str]] = mapped_column("f_parent_chunk_id", String(64), nullable=True)
    # 自引用 → t_text_chunks.f_chunk_id；顶层块为 NULL

    chunk_index: Mapped[int] = mapped_column("f_chunk_index", Integer, nullable=False)
    # 在原始文件中的顺序编号（0-based）
    chunk_type: Mapped[str] = mapped_column(
        "f_chunk_type", String(32), nullable=False, default="text"
    )
    # constants.CHUNK_TYPE_*: "text" | "image" | "parent"
    content: Mapped[str] = mapped_column("f_content", Text, nullable=False)
    # 原始文本、图片描述或语音转写内容
    token_count: Mapped[int] = mapped_column("f_token_count", Integer, nullable=False, default=0)
    # 近似 token 数，用于上下文窗口预算管理
    topic_tags: Mapped[list] = mapped_column("f_topic_tags", ARRAY(Text), nullable=False, default=list)
    # 从父 RawFile.tags 继承；用作 Milvus 标量过滤条件

    created_at: Mapped[datetime] = mapped_column("f_created_at", DateTime(timezone=True), nullable=False)
    delete_time: Mapped[Optional[datetime]] = mapped_column(
        "f_delete_time", DateTime(timezone=True), nullable=True
    )  # 软删除时间戳；NULL 表示活跃记录

    __table_args__ = (
        Index("idx_text_chunks_chunk_id", "f_chunk_id"),
        Index("idx_text_chunks_workspace_id", "f_workspace_id"),
        Index("idx_text_chunks_raw_file_id", "f_raw_file_id"),
        Index("idx_text_chunks_parent_chunk_id", "f_parent_chunk_id"),
        Index("idx_text_chunks_delete_time", "f_delete_time"),
        Index("idx_text_chunks_topic_tags", "f_topic_tags", postgresql_using="gin"),
    )
```

**字段说明**

| 字段 | 作用 |
|------|------|
| `f_id` | 数据库内部自增 PK，仅供引擎使用 |
| `f_chunk_id` | 业务 UUID；必须与 Milvus 集合中对应向量的 `id` 字段以及 ES 文档的 `_id` 完全一致，三个存储系统以此串联 |
| `f_workspace_id` | FK → `t_workspaces.f_workspace_id`；检索时 Milvus 和 ES 均以此做标量过滤，确保跨工作区数据不泄露 |
| `f_raw_file_id` | FK → `t_raw_files.f_raw_file_id`；标识本块来自哪个文件；按文件批量查询分块（embed_task、graph_task）、按文件软删除分块时使用 |
| `f_parent_chunk_id` | 自引用 FK → 同表 `f_chunk_id`；`NULL` 表示顶层块；**父子检索**（Parent-Child RAG）时：先用向量检索定位小粒度子块，再通过此字段查询更大范围的父块作为上下文 |
| `f_chunk_index` | 本块在原始文件中的顺序编号（0-based）；`find_by_raw_file_id()` 按此升序返回，保证拼接顺序正确 |
| `f_chunk_type` | 块类型（`text / image / parent`）：`text` 为普通文本块，进 Milvus text 集合；`image` 为图片描述，同时进 CLIP 向量集合；`parent` 为大窗口父块，不单独做向量化，仅供父子检索取内容 |
| `f_content` | 实际文本内容（正文、图片 caption、语音转写）；RAG 组装 context 时从此字段取值 |
| `f_token_count` | 近似 token 数；LLM 生成前做上下文预算管理（确保 top-K 块的总 token 数不超过模型 context window 限制） |
| `f_topic_tags` | 从父 `RawFile.tags` 继承；写入 Milvus 时同步存为标量字段，支持 `topic_tags IN [...]` 精准过滤，实现"只检索某个游戏相关资料"的语义隔离 |
| `f_created_at` | 分块创建时间，调试和审计使用 |
| `f_delete_time` | 软删除时间戳；删文件时批量将关联分块软删，同步触发 Milvus 和 ES 的数据清理 |

---

### QASession — 问答会话

**表的作用**：记录每一次用户问答的完整生命周期。一个"会话"对应一次从提问到 LLM 回答完毕的交互。本表服务三个场景：(1) 前端历史记录功能，展示用户过去的提问和回答；(2) 效果分析，统计不同 RAG 路径和方法的使用频率；(3) 故障排查，通过 `rag_path`、`rag_method`、`error` 字段定位异常问答。

```python
# app/storage/entities/qa_session.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import BigInteger, String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.orm_base import ORMBase


class QASessionStatus(str, Enum):
    GENERATING = "generating"
    DONE = "done"
    FAILED = "failed"


class QASession(ORMBase):
    __tablename__ = "t_qa_sessions"

    seq_id: Mapped[int] = mapped_column("f_id", BigInteger, primary_key=True, autoincrement=True)
    # 数据库内部自增主键；仅供引擎使用，永不对外暴露

    id: Mapped[str] = mapped_column("f_session_id", String(64), unique=True, nullable=False)
    # 业务 UUID；作为会话句柄返回给客户端

    workspace_id: Mapped[str] = mapped_column("f_workspace_id", String(64), nullable=False)
    # 引用 t_workspaces.f_workspace_id；租户隔离键
    user_id: Mapped[str] = mapped_column("f_user_id", String(64), nullable=False)
    # 引用认证系统用户业务 ID
    query: Mapped[str] = mapped_column("f_query", Text, nullable=False)
    rag_path: Mapped[str] = mapped_column("f_rag_path", String(32), nullable=False)
    # RAGPath: "chunk" | "entry" | "page"
    rag_method: Mapped[Optional[str]] = mapped_column("f_rag_method", String(32), nullable=True)
    # path == "chunk" 时使用的具体方法，如 "hybrid"、"graph_rag"、"speculative"
    status: Mapped[str] = mapped_column("f_status", String(32), nullable=False)
    # QASessionStatus: "generating" | "done" | "failed"
    answer: Mapped[Optional[str]] = mapped_column("f_answer", Text, nullable=True)
    # 流式输出中为 NULL；流式结束后填充完整回答
    source_chunk_ids: Mapped[Optional[list]] = mapped_column(
        "f_source_chunk_ids", ARRAY(Text), nullable=True
    )  # 本次问答使用的分块 ID 数组；供前端渲染来源引用
    error: Mapped[Optional[str]] = mapped_column("f_error", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("f_created_at", DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("f_updated_at", DateTime(timezone=True), nullable=False)
    delete_time: Mapped[Optional[datetime]] = mapped_column(
        "f_delete_time", DateTime(timezone=True), nullable=True
    )  # 软删除时间戳；NULL 表示活跃记录

    __table_args__ = (
        Index("idx_qa_sessions_session_id", "f_session_id"),
        Index("idx_qa_sessions_workspace_id", "f_workspace_id"),
        Index("idx_qa_sessions_user_id", "f_user_id"),
        Index("idx_qa_sessions_created_at", "f_created_at"),
        Index("idx_qa_sessions_delete_time", "f_delete_time"),
    )
```

**字段说明**

| 字段 | 作用 |
|------|------|
| `f_id` | 数据库内部自增 PK，仅供引擎使用 |
| `f_session_id` | 业务 UUID；SSE 流式回答开始前写入，前端用此 ID 查历史记录，也是 SSE 连接中的引用标识 |
| `f_workspace_id` | FK → `t_workspaces.f_workspace_id`；历史记录列表按工作区过滤 |
| `f_user_id` | 提问者用户 ID；支持"我的历史"过滤，区分不同用户的问答 |
| `f_query` | 用户原始问题文本；历史记录展示、搜索历史时使用 |
| `f_rag_path` | 本次问答走的检索路径（`chunk / entry / page`）；分析不同路径的使用分布和效果对比 |
| `f_rag_method` | hybrid-search 下具体使用的 RAG 方法（如 `hybrid / graph_rag / speculative`）；细粒度效果分析使用 |
| `f_status` | 会话状态：`GENERATING`（流式输出中，answer 为 NULL）→ `DONE`（流式结束，answer 已写入）或 `FAILED` |
| `f_answer` | LLM 生成的完整回答文本；流式输出结束后由 QAService 拼接写入；历史记录展示使用 |
| `f_source_chunk_ids` | 本次问答使用的来源分块 ID 数组；前端据此渲染"来源引用"面板，用户可点击跳转到原始文档片段 |
| `f_error` | 失败时的错误信息；`FAILED` 状态时写入，前端展示错误提示 |
| `f_created_at` | 问答时间；历史记录列表按此降序排列 |
| `f_updated_at` | 最后更新时间（流式结束时刷新） |
| `f_delete_time` | 软删除时间戳；用户删除历史记录时置为当前时间 |

---

### WikiPage — Wiki 词条页面

**表的作用**：存储由 LLM 编译生成的 Wiki 知识页面，每个主题（如"Royal Match"、"三消留存策略"）对应一条记录。以 `(workspace_id, topic)` 作为业务唯一键，支持对同一主题重新编译并覆盖旧内容。`status` 字段充当编译任务的进度载体，前端通过轮询此字段展示编译进度。编译完成后，`content` 字段存储带 `[[wikilinks]]` 标记的 Markdown 正文，前端直接渲染。

```python
# app/storage/entities/wiki_page.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import BigInteger, String, DateTime, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.orm_base import ORMBase


class WikiPageStatus(str, Enum):
    QUEUED = "queued"
    COMPILING = "compiling"
    PUBLISHED = "published"
    FAILED = "failed"


class WikiPage(ORMBase):
    __tablename__ = "t_wiki_pages"

    seq_id: Mapped[int] = mapped_column("f_id", BigInteger, primary_key=True, autoincrement=True)
    # 数据库内部自增主键；仅供引擎使用，永不对外暴露

    id: Mapped[str] = mapped_column("f_page_id", String(64), unique=True, nullable=False)
    # 业务 UUID；返回给客户端，用于 Wiki 链接解析

    workspace_id: Mapped[str] = mapped_column("f_workspace_id", String(64), nullable=False)
    # 引用 t_workspaces.f_workspace_id；租户隔离键
    topic: Mapped[str] = mapped_column("f_topic", String(255), nullable=False)
    # URL slug / 查询键，如 "royal-match"；工作区内必须唯一
    title: Mapped[str] = mapped_column("f_title", String(255), nullable=False)
    # Wiki 页面头部显示标题，如 "Royal Match"
    category: Mapped[Optional[str]] = mapped_column("f_category", String(64), nullable=True)
    # 可选分组："entities" | "mechanics" | "market"
    status: Mapped[str] = mapped_column("f_status", String(32), nullable=False)
    # WikiPageStatus: "queued" | "compiling" | "published" | "failed"
    content: Mapped[Optional[str]] = mapped_column("f_content", Text, nullable=True)
    # 含 [[wikilinks]] 标记的编译 Markdown；编译中或失败时为 NULL
    source_chunk_ids: Mapped[Optional[list]] = mapped_column(
        "f_source_chunk_ids", ARRAY(Text), nullable=True
    )  # 编译本页时使用的分块 ID 数组；用于追溯哪些文档构成了本页内容
    error: Mapped[Optional[str]] = mapped_column("f_error", Text, nullable=True)
    compiled_at: Mapped[Optional[datetime]] = mapped_column(
        "f_compiled_at", DateTime(timezone=True), nullable=True
    )  # 最近一次成功编译的时间戳；用于前端展示新鲜度
    created_at: Mapped[datetime] = mapped_column("f_created_at", DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("f_updated_at", DateTime(timezone=True), nullable=False)
    delete_time: Mapped[Optional[datetime]] = mapped_column(
        "f_delete_time", DateTime(timezone=True), nullable=True
    )  # 软删除时间戳；NULL 表示活跃记录

    __table_args__ = (
        UniqueConstraint("f_workspace_id", "f_topic", name="uq_wiki_page_workspace_topic"),
        Index("idx_wiki_pages_page_id", "f_page_id"),
        Index("idx_wiki_pages_workspace_id", "f_workspace_id"),
        Index("idx_wiki_pages_topic", "f_topic"),
        Index("idx_wiki_pages_category", "f_category"),
        Index("idx_wiki_pages_delete_time", "f_delete_time"),
    )
```

**字段说明**

| 字段 | 作用 |
|------|------|
| `f_id` | 数据库内部自增 PK，仅供引擎使用 |
| `f_page_id` | 业务 UUID；API 响应中作为页面句柄，Wiki 链接跳转时通过此 ID 查询页面详情 |
| `f_workspace_id` | FK → `t_workspaces.f_workspace_id`；Wiki 页面列表按工作区过滤 |
| `f_topic` | 主题标识符（URL slug，如 `royal-match`）；与 `workspace_id` 构成联合唯一键，也是 wiki-lookup 检索时的查询 key（`find_by_topic()`） |
| `f_title` | 页面显示标题（如 `Royal Match`）；前端页面头部、Wiki 列表卡片使用 |
| `f_category` | 可选分类标签（`entities / mechanics / market`）；前端 Wiki 目录按分类分组展示，也可作为过滤条件 |
| `f_status` | 编译状态机：`QUEUED`（已入队）→ `COMPILING`（Worker 正在五步编译）→ `PUBLISHED`（编译成功，content 可读）或 `FAILED`；前端轮询此字段展示进度 |
| `f_content` | 编译生成的 Markdown 正文，包含 `[[wikilinks]]` 内链标记；`PUBLISHED` 后由前端直接渲染；`NULL` 表示编译中或编译失败 |
| `f_source_chunk_ids` | 编译本页时使用的分块 ID 数组；前端可据此渲染"数据来源"面板，用户可追溯 Wiki 内容来自哪些原始文档 |
| `f_error` | 编译失败时的错误信息；`FAILED` 状态时写入，前端展示具体失败原因 |
| `f_compiled_at` | 最近一次成功编译的时间戳；前端展示"更新于 X 天前"新鲜度提示，超过阈值时提示重新编译 |
| `f_created_at` | 页面首次创建时间（首次触发编译时写入） |
| `f_updated_at` | 最后修改时间（每次重新编译覆盖后刷新） |
| `f_delete_time` | 软删除时间戳；删除 Wiki 词条时置为当前时间 |
| `uq_wiki_page_workspace_topic` | `(workspace_id, topic)` 联合唯一约束；保证同一工作区内每个主题只有一个词条，`upsert` 逻辑以此判断是新建还是覆盖 |

---

## 关于 DDL

**不需要手写 DDL，也不需要维护 `create-tables.sql` 文件。**

原因：ORM 实体类（上方的 Python 代码）是数据库结构的**唯一权威来源**。Alembic 会自动对比 ORM 元数据与数据库现状，生成精确的迁移脚本；手写 DDL 在 ORM 变更后极易出现不一致，反而成为维护负担。

### 迁移目录结构

```
backend/
  alembic/
    env.py
    versions/
      0001_initial_schema.py   ← alembic revision --autogenerate 生成
```

### alembic/env.py（关键配置）

```python
# alembic/env.py（节选）
from app.storage.orm_base import ORMBase
import app.storage.entities  # noqa: F401 — 导入所有实体模块以注册元数据

target_metadata = ORMBase.metadata
```

必须 `import app.storage.entities` 以确保所有实体类的元数据注册到 `ORMBase.metadata`，否则 autogenerate 无法感知这些表。

### 常用命令

```bash
# 首次初始化（生成 0001_initial_schema.py）
alembic revision --autogenerate -m "initial schema"

# 应用所有迁移到数据库
alembic upgrade head

# 新增或修改字段后，生成新迁移
alembic revision --autogenerate -m "add source_chunk_ids to qa_sessions"

# 查看当前版本
alembic current
```
