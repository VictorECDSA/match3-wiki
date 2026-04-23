# SQLAlchemy v2.0.48

**Version**: 2.0.48  
**Release Date**: 2026-04  
**Category**: ORM & SQL Toolkit  
**License**: MIT

---

## API Interface Overview

### 1. Engine & Connection

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

def create_engine(
    url: str,                       # Database URL (e.g., "postgresql://user:pass@host/db")
    echo: bool = False,             # Log all SQL statements
    pool_size: int = 5,             # Connection pool size
    max_overflow: int = 10,         # Max connections beyond pool_size
    pool_timeout: float = 30.0,     # Timeout waiting for connection
    pool_recycle: int = 3600,       # Recycle connections after N seconds
    pool_pre_ping: bool = False,    # Test connection before using
    connect_args: dict | None = None # Database-specific connection args
) -> Engine:
    """Create synchronous database engine"""

def create_async_engine(
    url: str,                       # Async database URL (e.g., "postgresql+asyncpg://...")
    **kwargs                        # Same as create_engine
) -> AsyncEngine:
    """Create asynchronous database engine"""
```

### 2. Session Management

```python
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Synchronous session
SessionLocal = sessionmaker(
    bind=engine,                    # Engine instance
    autocommit: bool = False,       # Auto-commit transactions
    autoflush: bool = True,         # Auto-flush before queries
    expire_on_commit: bool = True   # Expire objects after commit
)

# Asynchronous session
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=True,
    expire_on_commit=True
)
```

### 3. ORM Model Definition

```python
from sqlalchemy import Column, Integer, String, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, relationship, mapped_column, Mapped

class Base(DeclarativeBase):
    """Base class for all ORM models"""
    pass

class User(Base):
    """User model"""
    __tablename__ = "users"
    
    # Columns
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), index=True)
    
    # Relationships
    posts: Mapped[list["Post"]] = relationship(back_populates="author")
    
    # Indexes
    __table_args__ = (
        Index("ix_user_email", "email"),
    )
```

### 4. Query API (2.0 Style)

```python
from sqlalchemy import select, insert, update, delete

# SELECT query
stmt = select(User).where(User.id == 1)
result = session.execute(stmt)
user = result.scalar_one()

# INSERT
stmt = insert(User).values(username="alice", email="alice@example.com")
session.execute(stmt)

# UPDATE
stmt = update(User).where(User.id == 1).values(email="new@example.com")
session.execute(stmt)

# DELETE
stmt = delete(User).where(User.id == 1)
session.execute(stmt)
```

### 5. Async Query API

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user(session: AsyncSession, user_id: int) -> User:
    """Async query example"""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one()
```

### 6. Relationships

```python
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    posts: Mapped[list["Post"]] = relationship(
        back_populates="author",    # Bidirectional relationship
        cascade="all, delete-orphan" # Delete posts when user deleted
    )

class Post(Base):
    __tablename__ = "posts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="posts")
```

### 7. Transactions

```python
# Explicit transaction
async with session.begin():
    user = User(username="alice")
    session.add(user)
    # Auto-commit on exit

# Manual commit
session.add(user)
await session.commit()

# Rollback
try:
    session.add(user)
    await session.commit()
except Exception:
    await session.rollback()
    raise
```

### 8. Pagination & Filtering

```python
from sqlalchemy import select, func

# Pagination
stmt = select(User).offset(10).limit(20)  # Skip 10, take 20

# Filtering
stmt = select(User).where(User.age >= 18, User.active == True)

# Ordering
stmt = select(User).order_by(User.created_at.desc())

# Count
stmt = select(func.count()).select_from(User)
count = session.execute(stmt).scalar()
```

### 9. Eager Loading (Avoid N+1)

```python
from sqlalchemy.orm import selectinload, joinedload

# SELECT IN loading (separate query)
stmt = select(User).options(selectinload(User.posts))

# Joined loading (single query with JOIN)
stmt = select(User).options(joinedload(User.posts))

result = session.execute(stmt)
users = result.scalars().all()
# users[0].posts is already loaded (no additional query)
```

### 10. Runtime Integration (Match3 Project)

```python
from typing import Protocol
from sqlalchemy.ext.asyncio import AsyncSession

class IDatabase(Protocol):
    """Database interface for dependency injection"""
    
    async def acquire(self) -> AsyncSession:
        """Acquire database session"""
        ...
    
    async def close(self) -> None:
        """Close database connection"""
        ...
```

---

## Detailed Interface Usage

### 1. Engine & Connection Setup

#### Synchronous Engine (PostgreSQL)

```python
from sqlalchemy import create_engine

# PostgreSQL (using psycopg2)
engine = create_engine(
    "postgresql://user:password@localhost:5432/mydb",
    echo=False,                     # Don't log SQL (set True for debug)
    pool_size=10,                   # Keep 10 connections in pool
    max_overflow=20,                # Allow up to 30 total connections
    pool_timeout=30.0,              # Wait 30s for available connection
    pool_recycle=3600,              # Recycle connections after 1 hour
    pool_pre_ping=True,             # Test connection before use
    connect_args={
        "connect_timeout": 10       # Connection timeout
    }
)
```

#### Asynchronous Engine (PostgreSQL + asyncpg)

```python
from sqlalchemy.ext.asyncio import create_async_engine

# Async PostgreSQL (using asyncpg)
async_engine = create_async_engine(
    "postgresql+asyncpg://user:password@localhost:5432/mydb",
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True
)
```

#### Test Connection

```python
# Sync engine
with engine.connect() as conn:
    result = conn.execute(text("SELECT 1"))
    print(result.scalar())  # 1

# Async engine
async with async_engine.connect() as conn:
    result = await conn.execute(text("SELECT 1"))
    print(result.scalar())  # 1
```

---

### 2. ORM Model Definition (2.0 Style)

#### Basic Model

```python
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

class Base(DeclarativeBase):
    """Base class for all models"""
    pass

class User(Base):
    """User model with type hints"""
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # String columns
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100), index=True)
    
    # Optional column (nullable)
    bio: Mapped[str | None] = mapped_column(String(500), default=None)
    
    # Integer with default
    age: Mapped[int] = mapped_column(default=0)
    
    # Boolean
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Datetime
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow       # Auto-update on modification
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
```

#### Relationships (One-to-Many)

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50))
    
    # One-to-many: User has many Posts
    posts: Mapped[list["Post"]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan"   # Delete posts when user deleted
    )

class Post(Base):
    __tablename__ = "posts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str]
    
    # Foreign key
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # Many-to-one: Post belongs to User
    author: Mapped["User"] = relationship(back_populates="posts")
```

#### Many-to-Many Relationships

```python
from sqlalchemy import Table

# Association table
user_role_association = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    
    # Many-to-many: User has many Roles
    roles: Mapped[list["Role"]] = relationship(
        secondary=user_role_association,
        back_populates="users"
    )

class Role(Base):
    __tablename__ = "roles"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    
    # Many-to-many: Role has many Users
    users: Mapped[list["User"]] = relationship(
        secondary=user_role_association,
        back_populates="roles"
    )
```

#### Indexes & Constraints

```python
from sqlalchemy import Index, UniqueConstraint, CheckConstraint

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(100))
    age: Mapped[int]
    
    # Table-level constraints
    __table_args__ = (
        # Composite index
        Index("ix_user_username_email", "username", "email"),
        
        # Unique constraint
        UniqueConstraint("email", name="uq_user_email"),
        
        # Check constraint
        CheckConstraint("age >= 0", name="ck_user_age_positive"),
    )
```

---

### 3. Session Management

#### Synchronous Session

```python
from sqlalchemy.orm import sessionmaker

# Create session factory
SessionLocal = sessionmaker(bind=engine)

# Use session
with SessionLocal() as session:
    user = session.get(User, 1)
    print(user.username)
    # Session auto-closed on exit
```

#### Asynchronous Session

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False         # Don't expire objects after commit
)

# Use async session
async with AsyncSessionLocal() as session:
    result = await session.execute(select(User).where(User.id == 1))
    user = result.scalar_one()
    print(user.username)
```

#### Dependency Injection (FastAPI)

```python
from fastapi import Depends

async def get_db() -> AsyncSession:
    """Dependency to inject database session"""
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Route with injected session"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    return user
```

---

### 4. CRUD Operations (2.0 Style)

#### Create (INSERT)

```python
from sqlalchemy import insert

# Method 1: ORM object
async with AsyncSessionLocal() as session:
    user = User(username="alice", email="alice@example.com", age=30)
    session.add(user)
    await session.commit()
    await session.refresh(user)    # Load generated ID
    print(user.id)

# Method 2: INSERT statement
async with AsyncSessionLocal() as session:
    stmt = insert(User).values(
        username="bob",
        email="bob@example.com",
        age=25
    )
    await session.execute(stmt)
    await session.commit()
```

#### Read (SELECT)

```python
from sqlalchemy import select

# Get by primary key
async with AsyncSessionLocal() as session:
    user = await session.get(User, 1)  # Efficient PK lookup
    print(user.username)

# Query with WHERE
async with AsyncSessionLocal() as session:
    stmt = select(User).where(User.username == "alice")
    result = await session.execute(stmt)
    user = result.scalar_one()      # Exactly one result
    # Or: result.scalar_one_or_none()  # None if not found

# Get all
async with AsyncSessionLocal() as session:
    stmt = select(User).where(User.age >= 18)
    result = await session.execute(stmt)
    users = result.scalars().all()  # List of User objects
```

#### Update (UPDATE)

```python
from sqlalchemy import update

# Method 1: ORM object
async with AsyncSessionLocal() as session:
    user = await session.get(User, 1)
    user.email = "newemail@example.com"
    await session.commit()

# Method 2: UPDATE statement (more efficient)
async with AsyncSessionLocal() as session:
    stmt = update(User).where(User.id == 1).values(email="newemail@example.com")
    await session.execute(stmt)
    await session.commit()

# Bulk update
async with AsyncSessionLocal() as session:
    stmt = update(User).where(User.age < 18).values(is_active=False)
    await session.execute(stmt)
    await session.commit()
```

#### Delete (DELETE)

```python
from sqlalchemy import delete

# Method 1: ORM object
async with AsyncSessionLocal() as session:
    user = await session.get(User, 1)
    await session.delete(user)
    await session.commit()

# Method 2: DELETE statement
async with AsyncSessionLocal() as session:
    stmt = delete(User).where(User.id == 1)
    await session.execute(stmt)
    await session.commit()
```

---

### 5. Advanced Queries

#### Filtering

```python
from sqlalchemy import and_, or_, not_

# AND condition
stmt = select(User).where(and_(User.age >= 18, User.is_active == True))

# OR condition
stmt = select(User).where(or_(User.username == "alice", User.username == "bob"))

# NOT condition
stmt = select(User).where(not_(User.is_active))

# IN clause
stmt = select(User).where(User.id.in_([1, 2, 3]))

# LIKE
stmt = select(User).where(User.username.like("a%"))  # Starts with 'a'

# IS NULL
stmt = select(User).where(User.bio.is_(None))
```

#### Ordering & Limiting

```python
# ORDER BY
stmt = select(User).order_by(User.created_at.desc())

# Multiple order columns
stmt = select(User).order_by(User.age.desc(), User.username.asc())

# LIMIT & OFFSET
stmt = select(User).offset(10).limit(20)  # Pagination
```

#### Aggregation

```python
from sqlalchemy import func

# COUNT
stmt = select(func.count()).select_from(User)
count = await session.scalar(stmt)

# MAX, MIN, AVG, SUM
stmt = select(func.max(User.age))
max_age = await session.scalar(stmt)

# GROUP BY
stmt = select(
    User.age,
    func.count(User.id).label("count")
).group_by(User.age)

result = await session.execute(stmt)
for age, count in result:
    print(f"Age {age}: {count} users")
```

#### Joins

```python
# INNER JOIN
stmt = select(User, Post).join(Post, User.id == Post.user_id)

# LEFT OUTER JOIN
stmt = select(User).outerjoin(Post, User.id == Post.user_id)

# Join with WHERE
stmt = select(User).join(Post).where(Post.title.like("%python%"))
```

---

### 6. Eager Loading (Avoid N+1 Problem)

#### Lazy Loading (Default, causes N+1)

```python
# BAD: N+1 queries
users = await session.scalars(select(User))
for user in users:
    print(user.posts)  # Each iteration triggers a new query!
```

#### SELECT IN Loading

```python
from sqlalchemy.orm import selectinload

# GOOD: 2 queries (1 for users, 1 for all posts)
stmt = select(User).options(selectinload(User.posts))
result = await session.execute(stmt)
users = result.scalars().all()

for user in users:
    print(user.posts)  # No additional query
```

#### Joined Loading

```python
from sqlalchemy.orm import joinedload

# GOOD: 1 query with JOIN
stmt = select(User).options(joinedload(User.posts))
result = await session.execute(stmt)
users = result.unique().scalars().all()  # unique() needed for joined loading

for user in users:
    print(user.posts)  # No additional query
```

#### Nested Eager Loading

```python
# Load user -> posts -> comments (3 levels)
stmt = select(User).options(
    selectinload(User.posts).selectinload(Post.comments)
)
```

---

### 7. Transactions

#### Auto-Commit with Context Manager

```python
async with AsyncSessionLocal() as session:
    async with session.begin():
        user = User(username="alice")
        session.add(user)
        # Auto-commit on successful exit
        # Auto-rollback on exception
```

#### Manual Commit & Rollback

```python
async with AsyncSessionLocal() as session:
    try:
        user = User(username="alice")
        session.add(user)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise
```

#### Savepoints (Nested Transactions)

```python
async with session.begin():
    user1 = User(username="alice")
    session.add(user1)
    
    async with session.begin_nested():  # Savepoint
        user2 = User(username="bob")
        session.add(user2)
        # Can rollback to this savepoint
```

---

### 8. Raw SQL

```python
from sqlalchemy import text

# Execute raw SQL
async with AsyncSessionLocal() as session:
    result = await session.execute(
        text("SELECT * FROM users WHERE age > :age"),
        {"age": 18}
    )
    rows = result.fetchall()
    
    for row in rows:
        print(row.username, row.email)
```

---

### 9. Runtime Integration (Match3 Project)

#### Database Interface

```python
from typing import Protocol
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

class IDatabase(Protocol):
    """Database interface for dependency injection"""
    
    async def session(self) -> AsyncSession:
        """Get database session"""
        ...
    
    async def close(self) -> None:
        """Close database engine"""
        ...

class AsyncPGDatabase:
    """PostgreSQL async implementation"""
    
    def __init__(self, engine: AsyncEngine):
        self._engine = engine
        self._sessionmaker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def session(self) -> AsyncSession:
        """Get new session"""
        return self._sessionmaker()
    
    async def close(self) -> None:
        """Close engine"""
        await self._engine.dispose()
```

#### Injecting into Runtime

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Match3Runtime:
    """Runtime dependency container"""
    
    db: IDatabase  # Database interface
    # ... other dependencies

async def build_runtime(config: Config) -> Match3Runtime:
    """Build runtime with all dependencies"""
    
    # Create async engine
    engine = create_async_engine(
        config.database.url,
        pool_size=config.database.pool_size,
        max_overflow=config.database.max_overflow
    )
    
    # Create database instance
    db = AsyncPGDatabase(engine)
    
    return Match3Runtime(db=db)
```

#### Usage in Repository

```python
class UserRepository:
    """User repository with SQLAlchemy"""
    
    def __init__(self, runtime: Match3Runtime):
        self._db = runtime.db
    
    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID"""
        async with self._db.session() as session:
            return await session.get(User, user_id)
    
    async def get_by_username(self, username: str) -> User | None:
        """Get user by username"""
        async with self._db.session() as session:
            stmt = select(User).where(User.username == username)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def create(self, username: str, email: str) -> User:
        """Create new user"""
        async with self._db.session() as session:
            user = User(username=username, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
    
    async def list_users(self, skip: int = 0, limit: int = 10) -> list[User]:
        """List users with pagination"""
        async with self._db.session() as session:
            stmt = select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
            result = await session.execute(stmt)
            return result.scalars().all()
```

---

## Why SQLAlchemy v2.0.48?

### Key Features in v2.0

1. **Type Safety**
   - Full type hints support
   - IDE autocomplete for ORM models
   - Pydantic integration

2. **Modern API**
   - New `select()` construct (replaces `Query`)
   - `mapped_column()` with type hints
   - Async/await first-class support

3. **Performance**
   - Optimized query compilation
   - Better connection pooling
   - Lazy loading improvements

4. **Breaking Changes from 1.x**
   - Must use `select()` instead of `Query`
   - Must use `mapped_column()` for typed columns
   - Session handling changes

### When to Use SQLAlchemy

✅ **Use SQLAlchemy when**:
- Need ORM for complex models
- Want database abstraction (switch PostgreSQL/MySQL easily)
- Need migration support (Alembic)
- Complex queries with joins, aggregations
- Type safety with Pydantic models

❌ **Don't use SQLAlchemy when**:
- Simple CRUD operations (use raw SQL)
- Extremely high performance required (use asyncpg directly)
- Database-specific features (use native driver)

---

## Integration with Match3 Architecture

```
┌─────────────────────────────────────────────────┐
│                  FastAPI Layer                  │
│               (Route Handlers)                  │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│            UserRepository                       │
│  - get_by_id()                                  │
│  - create()                                     │
│  - list_users()                                 │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│         Match3Runtime.db                        │
│       (IDatabase Protocol)                      │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│         SQLAlchemy AsyncSession                 │
│     (ORM + Connection Pool)                     │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│          PostgreSQL Database                    │
│        (v16.13, Primary Data Store)             │
└─────────────────────────────────────────────────┘
```

---

## Configuration Example

```python
from pydantic import BaseModel

class DatabaseConfig(BaseModel):
    """Database configuration"""
    
    # Connection
    host: str = "localhost"
    port: int = 5432
    database: str = "match3"
    username: str = "postgres"
    password: str
    
    # Pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: float = 30.0
    pool_recycle: int = 3600
    
    # ORM settings
    echo: bool = False  # Log SQL in dev
    expire_on_commit: bool = False
    
    @property
    def url(self) -> str:
        """Build database URL"""
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
```

---

## Best Practices

1. **Use Async Sessions**
   - Always use `AsyncSession` in async apps (FastAPI)
   - Don't mix sync and async sessions

2. **Eager Load Relationships**
   - Use `selectinload()` or `joinedload()` to avoid N+1
   - Plan your query loading strategy upfront

3. **Use Type Hints**
   - Use `Mapped[]` with `mapped_column()`
   - Enable IDE autocomplete and type checking

4. **Session Management**
   - Use context managers (`async with session`)
   - Don't share sessions across requests

5. **Transaction Handling**
   - Wrap multiple operations in `session.begin()`
   - Always rollback on exceptions

6. **Connection Pooling**
   - Set appropriate `pool_size` and `max_overflow`
   - Enable `pool_pre_ping` for reliability
