# Database Implementation — PostgreSQL + SQLAlchemy

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
        pool_size=config.runtime.database.implementations.postgresql.pool_size,
        max_overflow=config.runtime.database.implementations.postgresql.max_overflow,
        pool_timeout=config.runtime.database.implementations.postgresql.pool_timeout,
        pool_recycle=config.runtime.database.implementations.postgresql.pool_recycle,
        pool_pre_ping=True,  # 自动检测失效连接
    )
    
    logger.info(f"PostgreSQL engine initialized (pool_size: {config.runtime.database.implementations.postgresql.pool_size})")

    return Match3Runtime(
        # ...
        db=db_engine,
        # ...
    )
```

### Session Management

```python
# app/database/session.py
from sqlalchemy.orm import Session
from app.runtime import Match3Runtime


def get_db_session(rt: Match3Runtime) -> Session:
    """Get database session.
    
    Usage in services and tasks:
    with get_db_session(rt) as session:
        # Perform database operations
        session.commit()
    """
    return Session(rt.db)
```

## ORM Model Definition

### Base Model

```python
# app/database/models/base.py
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TimestampMixin:
    """Timestamp mixin class."""
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class WorkspaceMixin:
    """Workspace isolation mixin class."""
    workspace_id = Column(Integer, nullable=False, index=True)
```

### RawFile Model

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

### Chunk Model

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
    
    # Relationships
    raw_file = relationship("RawFile", backref="chunks")
```

### WikiPage Model

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
        # Unique constraint: slug unique within workspace
        UniqueConstraint("workspace_id", "slug", name="uq_wiki_workspace_slug"),
    )
```

### QASession and QATurn Models

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
    
    # Relationships
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
    
    # Relationships
    session = relationship("QASession", back_populates="turns")
```

## Usage Examples

### Create Record

```python
from app.database.models.raw_file import RawFile, RawFileStatus
from app.database.session import get_db_session

def create_raw_file(rt: Match3Runtime, filename: str, workspace_id: int) -> int:
    """Create RawFile record."""
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

### Query Record

```python
def get_pending_files(rt: Match3Runtime, workspace_id: int) -> list[RawFile]:
    """Query pending files."""
    with get_db_session(rt) as session:
        return session.query(RawFile).filter(
            RawFile.workspace_id == workspace_id,
            RawFile.status == RawFileStatus.PENDING,
        ).all()
```

### Update Record

```python
def update_file_status(
    rt: Match3Runtime,
    file_id: int,
    status: RawFileStatus,
    error_message: str | None = None,
):
    """Update file status."""
    with get_db_session(rt) as session:
        raw_file = session.query(RawFile).filter(RawFile.id == file_id).first()
        if raw_file:
            raw_file.status = status
            if error_message:
                raw_file.error_message = error_message
            session.commit()
```

### Join Query

```python
def get_file_with_chunks(rt: Match3Runtime, file_id: int) -> RawFile:
    """Query file with all its chunks."""
    with get_db_session(rt) as session:
        return session.query(RawFile).filter(
            RawFile.id == file_id
        ).options(
            joinedload(RawFile.chunks)
        ).first()
```

## Database Migration (Alembic)

### Initialize Alembic

```bash
alembic init alembic
```

### Configure Alembic

```python
# alembic/env.py
from app.database.models.base import Base
from app.database.models.raw_file import RawFile
from app.database.models.chunk import Chunk
from app.database.models.wiki_page import WikiPage
from app.database.models.qa import QASession, QATurn

target_metadata = Base.metadata
```

### Create Migration

```bash
# Auto-generate migration script
alembic revision --autogenerate -m "Create raw_files table"

# Manually create migration script
alembic revision -m "Add index to chunks"
```

### Execute Migration

```bash
# Upgrade to latest version
alembic upgrade head

# Downgrade one version
alembic downgrade -1

# View migration history
alembic history
```

## Configuration Parameters

### Config (config.yaml)

```yaml
runtime:
  database:
    provider: postgresql
    implementations:
      postgresql:
        pool_size: 10          # Connection pool size
        max_overflow: 20       # Max overflow connections
        pool_timeout: 30       # Connection timeout (seconds)
        pool_recycle: 3600     # Connection recycle time (seconds)
```

### Env (.env)

```bash
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DB=match3
POSTGRESQL_USER=match3_user
POSTGRESQL_PASSWORD=your_secure_password
```

## Performance Optimization

### 1. Bulk Insert

```python
def bulk_insert_chunks(rt: Match3Runtime, chunks_data: list[dict]):
    """Bulk insert chunks."""
    with get_db_session(rt) as session:
        session.bulk_insert_mappings(Chunk, chunks_data)
        session.commit()
```

### 2. Query Optimization

- Use `joinedload` to preload related objects
- Use `selectinload` to optimize one-to-many relationships
- Add necessary indexes

```python
# Add index
__table_args__ = (
    Index("idx_chunks_workspace_file", "workspace_id", "raw_file_id"),
)
```

### 3. Connection Pool Management

- Set reasonable `pool_size` and `max_overflow`
- Use `pool_pre_ping=True` to auto-detect stale connections
- Regularly recycle connections (`pool_recycle`)

## Related Documentation

- **[protocol.md](./protocol.md)** — Database Protocol definition
- **[../../design/solution-final/050-data-model/](../../design/solution-final/050-data-model/)** — Detailed data model design
