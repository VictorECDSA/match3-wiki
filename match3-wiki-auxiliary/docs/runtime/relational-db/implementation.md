# Relational Database Implementation — PostgreSQL + SQLAlchemy

## 概述

Match3 使用 **PostgreSQL** 作为关系型数据库，通过 **SQLAlchemy 2.0** ORM 进行数据访问。

## 适配器实现

### SQLAlchemy Engine

```python
# app/runtime.py (build_runtime 部分)
from sqlalchemy import create_engine

def build_runtime(config: Config, env: Env, logger: Logger) -> Match3Runtime:
    """构建 Runtime 实例"""
    
    postgres_url = (
        f"postgresql+psycopg2://{env.POSTGRESQL_USER}:{env.POSTGRESQL_PASSWORD}"
        f"@{env.POSTGRESQL_HOST}:{env.POSTGRESQL_PORT}/{env.POSTGRESQL_DB}"
    )

    db_engine = create_engine(
        postgres_url,
        pool_size=config.database.pool_size,
        max_overflow=config.database.max_overflow,
        pool_timeout=config.database.pool_timeout,
        pool_recycle=config.database.pool_recycle,
        pool_pre_ping=True,  # 自动检测失效连接
    )
    
    logger.info(f"PostgreSQL engine initialized (pool_size: {config.database.pool_size})")

    return Match3Runtime(
        # ...
        db_engine=db_engine,
        # ...
    )
```

### Session 管理

```python
# app/database/session.py
from sqlalchemy.orm import Session
from app.runtime import Match3Runtime


def get_db_session(rt: Match3Runtime) -> Session:
    """获取数据库会话。
    
    在服务和任务中使用：
    with get_db_session(rt) as session:
        # 执行数据库操作
        session.commit()
    """
    return Session(rt.db_engine)
```

## ORM 模型定义

### Base 模型

```python
# app/database/models/base.py
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TimestampMixin:
    """时间戳混入类。"""
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class WorkspaceMixin:
    """工作空间隔离混入类。"""
    workspace_id = Column(Integer, nullable=False, index=True)
```

### RawFile 模型

```python
# app/database/models/raw_file.py
from sqlalchemy import Column, Integer, String, Enum
from app.database.models.base import Base, TimestampMixin, WorkspaceMixin
import enum


class RawFileStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RawFile(Base, TimestampMixin, WorkspaceMixin):
    __tablename__ = "raw_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_key = Column(String(500), nullable=False)  # MinIO object key
    status = Column(Enum(RawFileStatus), nullable=False, default=RawFileStatus.PENDING)
    error_message = Column(String(1000), nullable=True)
```

### Chunk 模型

```python
# app/database/models/chunk.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database.models.base import Base, TimestampMixin, WorkspaceMixin


class Chunk(Base, TimestampMixin, WorkspaceMixin):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_file_id = Column(Integer, ForeignKey("raw_files.id"), nullable=False)
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    start_pos = Column(Integer, nullable=True)
    end_pos = Column(Integer, nullable=True)
    
    # 关系
    raw_file = relationship("RawFile", backref="chunks")
```

### WikiPage 模型

```python
# app/database/models/wiki_page.py
from sqlalchemy import Column, Integer, String, Text, Enum
from app.database.models.base import Base, TimestampMixin, WorkspaceMixin
import enum


class WikiPageStatus(enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class WikiPage(Base, TimestampMixin, WorkspaceMixin):
    __tablename__ = "wiki_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(200), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content_md = Column(Text, nullable=False)
    storage_key = Column(String(500), nullable=True)  # MinIO .md file key
    status = Column(Enum(WikiPageStatus), nullable=False, default=WikiPageStatus.DRAFT)
    
    __table_args__ = (
        # 唯一约束：同一个工作空间内 slug 唯一
        UniqueConstraint("workspace_id", "slug", name="uq_wiki_workspace_slug"),
    )
```

### QASession 和 QATurn 模型

```python
# app/database/models/qa.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database.models.base import Base, TimestampMixin, WorkspaceMixin


class QASession(Base, TimestampMixin, WorkspaceMixin):
    __tablename__ = "qa_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String(500), nullable=True)
    
    # 关系
    turns = relationship("QATurn", back_populates="session", order_by="QATurn.turn_index")


class QATurn(Base, TimestampMixin):
    __tablename__ = "qa_turns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("qa_sessions.id"), nullable=False)
    turn_index = Column(Integer, nullable=False)
    user_query = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    rag_path = Column(String(50), nullable=True)  # "chunk" | "entry" | "page"
    retrieval_count = Column(Integer, nullable=True)
    
    # 关系
    session = relationship("QASession", back_populates="turns")
```

## 使用示例

### 创建记录

```python
from app.database.models.raw_file import RawFile, RawFileStatus
from app.database.session import get_db_session

def create_raw_file(rt: Match3Runtime, filename: str, workspace_id: int) -> int:
    """创建 RawFile 记录。"""
    with get_db_session(rt) as session:
        raw_file = RawFile(
            filename=filename,
            mime_type="application/pdf",
            size_bytes=1024000,
            storage_key=f"uploads/{filename}",
            status=RawFileStatus.PENDING,
            workspace_id=workspace_id,
        )
        session.add(raw_file)
        session.commit()
        session.refresh(raw_file)
        return raw_file.id
```

### 查询记录

```python
def get_pending_files(rt: Match3Runtime, workspace_id: int) -> list[RawFile]:
    """查询待处理的文件。"""
    with get_db_session(rt) as session:
        return session.query(RawFile).filter(
            RawFile.workspace_id == workspace_id,
            RawFile.status == RawFileStatus.PENDING,
        ).all()
```

### 更新记录

```python
def update_file_status(
    rt: Match3Runtime,
    file_id: int,
    status: RawFileStatus,
    error_message: str | None = None,
):
    """更新文件状态。"""
    with get_db_session(rt) as session:
        raw_file = session.query(RawFile).filter(RawFile.id == file_id).first()
        if raw_file:
            raw_file.status = status
            if error_message:
                raw_file.error_message = error_message
            session.commit()
```

### 关联查询

```python
def get_file_with_chunks(rt: Match3Runtime, file_id: int) -> RawFile:
    """查询文件及其所有块。"""
    with get_db_session(rt) as session:
        return session.query(RawFile).filter(
            RawFile.id == file_id
        ).options(
            joinedload(RawFile.chunks)
        ).first()
```

## 数据库迁移 (Alembic)

### 初始化 Alembic

```bash
alembic init alembic
```

### 配置 Alembic

```python
# alembic/env.py
from app.database.models.base import Base
from app.database.models.raw_file import RawFile
from app.database.models.chunk import Chunk
from app.database.models.wiki_page import WikiPage
from app.database.models.qa import QASession, QATurn

target_metadata = Base.metadata
```

### 创建迁移

```bash
# 自动生成迁移脚本
alembic revision --autogenerate -m "Create raw_files table"

# 手动创建迁移脚本
alembic revision -m "Add index to chunks"
```

### 执行迁移

```bash
# 升级到最新版本
alembic upgrade head

# 降级一个版本
alembic downgrade -1

# 查看迁移历史
alembic history
```

## 配置参数

### Config (config.yaml)

```yaml
database:
  pool_size: 10          # 连接池大小
  max_overflow: 20       # 最大溢出连接数
  pool_timeout: 30       # 连接超时（秒）
  pool_recycle: 3600     # 连接回收时间（秒）
```

### Env (.env)

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=match3
POSTGRES_USER=match3_user
POSTGRES_PASSWORD=your_secure_password
```

## 性能优化

### 1. 批量插入

```python
def bulk_insert_chunks(rt: Match3Runtime, chunks_data: list[dict]):
    """批量插入 chunks。"""
    with get_db_session(rt) as session:
        session.bulk_insert_mappings(Chunk, chunks_data)
        session.commit()
```

### 2. 查询优化

- 使用 `joinedload` 预加载关联对象
- 使用 `selectinload` 优化一对多关系
- 添加必要的索引

```python
# 添加索引
__table_args__ = (
    Index("idx_chunks_workspace_file", "workspace_id", "raw_file_id"),
)
```

### 3. 连接池管理

- 设置合理的 `pool_size` 和 `max_overflow`
- 使用 `pool_pre_ping=True` 自动检测失效连接
- 定期回收连接（`pool_recycle`）

## 相关文档

- **[protocol.md](./protocol.md)** — RelationalDB Protocol 定义
- **[../../design/solution-final/050-data-model/](../../design/solution-final/050-data-model/)** — 数据模型详细设计
