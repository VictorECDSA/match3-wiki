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

所有 Repository 的构造函数签名统一如下：

```python
def __init__(self, engine: Engine) -> None:
    self._engine = engine
```

---

## WorkspaceRepository

```python
# app/storage/repositories/workspace_repo.py
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import Engine, select, func
from sqlalchemy.orm import Session
from app.storage.entities.workspace import Workspace


class WorkspaceRepository:

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # 自动提交方法
    # ------------------------------------------------------------------

    def insert(self, entity: Workspace) -> Workspace:
        with Session(self._engine) as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            session.commit()
            return entity

    def find_by_id(self, workspace_id: str) -> Optional[Workspace]:
        with Session(self._engine) as session:
            stmt = (
                select(Workspace)
                .where(
                    Workspace.id == workspace_id,
                    Workspace.delete_time.is_(None),
                )
            )
            return session.execute(stmt).scalar_one_or_none()

    def find_paginated(
        self,
        page: int,
        size: int,
    ) -> tuple[list[Workspace], int]:
        offset = (page - 1) * size
        with Session(self._engine) as session:
            base = select(Workspace).where(Workspace.delete_time.is_(None))
            total = session.execute(
                select(func.count()).select_from(base.subquery())
            ).scalar_one()
            items = session.execute(
                base.order_by(Workspace.created_at.desc()).offset(offset).limit(size)
            ).scalars().all()
            return list(items), total

    def update(self, entity: Workspace) -> Workspace:
        with Session(self._engine) as session:
            merged = session.merge(entity)
            session.flush()
            session.refresh(merged)
            session.commit()
            return merged

    def delete(self, workspace_id: str) -> None:
        """软删除：将 delete_time 设为当前时间。"""
        with Session(self._engine) as session:
            stmt = (
                select(Workspace)
                .where(
                    Workspace.id == workspace_id,
                    Workspace.delete_time.is_(None),
                )
            )
            entity = session.execute(stmt).scalar_one_or_none()
            if entity:
                entity.delete_time = datetime.now(timezone.utc)
                session.commit()

    # ------------------------------------------------------------------
    # 事务作用域方法（由调用方提交）
    # ------------------------------------------------------------------

    def tx_insert(self, tx: Session, entity: Workspace) -> Workspace:
        tx.add(entity)
        tx.flush()
        tx.refresh(entity)
        return entity

    def tx_update(self, tx: Session, entity: Workspace) -> Workspace:
        merged = tx.merge(entity)
        tx.flush()
        tx.refresh(merged)
        return merged

    def tx_delete(self, tx: Session, workspace_id: str) -> None:
        stmt = (
            select(Workspace)
            .where(
                Workspace.id == workspace_id,
                Workspace.delete_time.is_(None),
            )
        )
        entity = tx.execute(stmt).scalar_one_or_none()
        if entity:
            entity.delete_time = datetime.now(timezone.utc)
            tx.flush()
```

---

## WorkspaceMemberRepository

```python
# app/storage/repositories/workspace_member_repo.py
from __future__ import annotations
from typing import Optional
from sqlalchemy import Engine, select, func
from sqlalchemy.orm import Session
from app.storage.entities.workspace_member import WorkspaceMember


class WorkspaceMemberRepository:

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # 自动提交方法
    # ------------------------------------------------------------------

    def insert(self, entity: WorkspaceMember) -> WorkspaceMember:
        with Session(self._engine) as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            session.commit()
            return entity

    def find_by_id(self, member_id: str) -> Optional[WorkspaceMember]:
        with Session(self._engine) as session:
            stmt = select(WorkspaceMember).where(WorkspaceMember.id == member_id)
            return session.execute(stmt).scalar_one_or_none()

    def find_by_user_workspace(
        self,
        user_id: str,
        workspace_id: str,
    ) -> Optional[WorkspaceMember]:
        with Session(self._engine) as session:
            stmt = select(WorkspaceMember).where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id == workspace_id,
            )
            return session.execute(stmt).scalar_one_or_none()

    def find_paginated(
        self,
        workspace_id: str,
        page: int,
        size: int,
    ) -> tuple[list[WorkspaceMember], int]:
        offset = (page - 1) * size
        with Session(self._engine) as session:
            base = select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id
            )
            total = session.execute(
                select(func.count()).select_from(base.subquery())
            ).scalar_one()
            items = session.execute(
                base.order_by(WorkspaceMember.joined_at.asc())
                .offset(offset)
                .limit(size)
            ).scalars().all()
            return list(items), total

    def update(self, entity: WorkspaceMember) -> WorkspaceMember:
        with Session(self._engine) as session:
            merged = session.merge(entity)
            session.flush()
            session.refresh(merged)
            session.commit()
            return merged

    def delete_by_user_workspace(self, user_id: str, workspace_id: str) -> None:
        """硬删除：工作区成员关系不使用软删除。"""
        with Session(self._engine) as session:
            stmt = select(WorkspaceMember).where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id == workspace_id,
            )
            entity = session.execute(stmt).scalar_one_or_none()
            if entity:
                session.delete(entity)
                session.commit()

    # ------------------------------------------------------------------
    # 事务作用域方法
    # ------------------------------------------------------------------

    def tx_insert(self, tx: Session, entity: WorkspaceMember) -> WorkspaceMember:
        tx.add(entity)
        tx.flush()
        tx.refresh(entity)
        return entity

    def tx_update(self, tx: Session, entity: WorkspaceMember) -> WorkspaceMember:
        merged = tx.merge(entity)
        tx.flush()
        tx.refresh(merged)
        return merged
```

---

## RawFileRepository

```python
# app/storage/repositories/raw_file_repo.py
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import Engine, select, func
from sqlalchemy.orm import Session
from app.storage.entities.raw_file import RawFile


class RawFileRepository:

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # 自动提交方法
    # ------------------------------------------------------------------

    def insert(self, entity: RawFile) -> RawFile:
        with Session(self._engine) as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            session.commit()
            return entity

    def find_by_id(self, file_id: str) -> Optional[RawFile]:
        with Session(self._engine) as session:
            stmt = select(RawFile).where(
                RawFile.id == file_id,
                RawFile.delete_time.is_(None),
            )
            return session.execute(stmt).scalar_one_or_none()

    def find_paginated(
        self,
        workspace_id: str,
        page: int,
        size: int,
        status: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> tuple[list[RawFile], int]:
        """
        分页查询工作区内的原始文件。

        Args:
            workspace_id: 按工作区过滤。
            status: 可选状态过滤（pending/processing/done/failed）。
            tag: 可选标签过滤——匹配数组中任意元素（使用 PostgreSQL @> 操作符）。
        """
        offset = (page - 1) * size
        with Session(self._engine) as session:
            base = select(RawFile).where(
                RawFile.workspace_id == workspace_id,
                RawFile.delete_time.is_(None),
            )
            if status:
                base = base.where(RawFile.status == status)
            if tag:
                # PostgreSQL 数组包含：f_tags @> ARRAY['tag']
                from sqlalchemy import cast, ARRAY, Text
                base = base.where(RawFile.tags.contains(cast([tag], ARRAY(Text))))
            total = session.execute(
                select(func.count()).select_from(base.subquery())
            ).scalar_one()
            items = session.execute(
                base.order_by(RawFile.created_at.desc()).offset(offset).limit(size)
            ).scalars().all()
            return list(items), total

    def find_latest_by_topic_tag(
        self,
        topic: str,
        workspace_id: str,
    ) -> Optional[RawFile]:
        """返回带有该主题标签的最新上传文件（用于 Wiki 新鲜度检查）。"""
        from sqlalchemy import cast, ARRAY, Text
        with Session(self._engine) as session:
            stmt = (
                select(RawFile)
                .where(
                    RawFile.workspace_id == workspace_id,
                    RawFile.delete_time.is_(None),
                    RawFile.tags.contains(cast([topic], ARRAY(Text))),
                )
                .order_by(RawFile.created_at.desc())
                .limit(1)
            )
            return session.execute(stmt).scalar_one_or_none()

    def update(self, entity: RawFile) -> RawFile:
        with Session(self._engine) as session:
            entity.updated_at = datetime.now(timezone.utc)
            merged = session.merge(entity)
            session.flush()
            session.refresh(merged)
            session.commit()
            return merged

    def delete(self, file_id: str) -> None:
        """软删除。"""
        with Session(self._engine) as session:
            stmt = select(RawFile).where(
                RawFile.id == file_id,
                RawFile.delete_time.is_(None),
            )
            entity = session.execute(stmt).scalar_one_or_none()
            if entity:
                entity.delete_time = datetime.now(timezone.utc)
                session.commit()

    # ------------------------------------------------------------------
    # 事务作用域方法
    # ------------------------------------------------------------------

    def tx_insert(self, tx: Session, entity: RawFile) -> RawFile:
        tx.add(entity)
        tx.flush()
        tx.refresh(entity)
        return entity

    def tx_update(self, tx: Session, entity: RawFile) -> RawFile:
        entity.updated_at = datetime.now(timezone.utc)
        merged = tx.merge(entity)
        tx.flush()
        tx.refresh(merged)
        return merged

    def tx_delete(self, tx: Session, file_id: str) -> None:
        stmt = select(RawFile).where(
            RawFile.id == file_id,
            RawFile.delete_time.is_(None),
        )
        entity = tx.execute(stmt).scalar_one_or_none()
        if entity:
            entity.delete_time = datetime.now(timezone.utc)
            tx.flush()
```

---

## TextChunkRepository

```python
# app/storage/repositories/text_chunk_repo.py
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import Engine, select, func
from sqlalchemy.orm import Session
from app.storage.entities.text_chunk import TextChunk


class TextChunkRepository:

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # 自动提交方法
    # ------------------------------------------------------------------

    def insert(self, entity: TextChunk) -> TextChunk:
        with Session(self._engine) as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            session.commit()
            return entity

    def bulk_insert(self, entities: list[TextChunk]) -> list[TextChunk]:
        """在单个事务中批量插入文本块（用于导入流程）。"""
        if not entities:
            return []
        with Session(self._engine) as session:
            session.add_all(entities)
            session.flush()
            for e in entities:
                session.refresh(e)
            session.commit()
            return entities

    def find_by_id(self, chunk_id: str) -> Optional[TextChunk]:
        with Session(self._engine) as session:
            stmt = select(TextChunk).where(
                TextChunk.id == chunk_id,
                TextChunk.delete_time.is_(None),
            )
            return session.execute(stmt).scalar_one_or_none()

    def find_by_ids(self, chunk_ids: list[str]) -> list[TextChunk]:
        """按 ID 列表批量查询——用于 RAG 检索阶段补全 Milvus 命中结果。"""
        if not chunk_ids:
            return []
        with Session(self._engine) as session:
            stmt = select(TextChunk).where(
                TextChunk.id.in_(chunk_ids),
                TextChunk.delete_time.is_(None),
            )
            return list(session.execute(stmt).scalars().all())

    def find_by_raw_file_id(self, raw_file_id: str) -> list[TextChunk]:
        """按 chunk_index 顺序返回文件的所有文本块。"""
        with Session(self._engine) as session:
            stmt = (
                select(TextChunk)
                .where(
                    TextChunk.raw_file_id == raw_file_id,
                    TextChunk.delete_time.is_(None),
                )
                .order_by(TextChunk.chunk_index.asc())
            )
            return list(session.execute(stmt).scalars().all())

    def find_parent_chunks(
        self,
        child_chunk_ids: list[str],
    ) -> list[TextChunk]:
        """
        返回给定子块 ID 对应的父块。
        用于父子检索：先通过向量检索找到子块，再获取更大的父级上下文。
        """
        if not child_chunk_ids:
            return []
        with Session(self._engine) as session:
            # 先从子块中取出 parent_chunk_id
            child_stmt = select(TextChunk.parent_chunk_id).where(
                TextChunk.id.in_(child_chunk_ids),
                TextChunk.parent_chunk_id.isnot(None),
                TextChunk.delete_time.is_(None),
            )
            parent_ids = [
                row[0]
                for row in session.execute(child_stmt).all()
                if row[0] is not None
            ]
            if not parent_ids:
                return []
            parent_stmt = select(TextChunk).where(
                TextChunk.id.in_(parent_ids),
                TextChunk.delete_time.is_(None),
            )
            return list(session.execute(parent_stmt).scalars().all())

    def count_by_raw_file_id(self, raw_file_id: str) -> int:
        with Session(self._engine) as session:
            stmt = select(func.count(TextChunk.id)).where(
                TextChunk.raw_file_id == raw_file_id,
                TextChunk.delete_time.is_(None),
            )
            return session.execute(stmt).scalar_one()

    def delete_by_raw_file_id(self, raw_file_id: str) -> int:
        """软删除文件的所有文本块，返回删除数量。"""
        now = datetime.now(timezone.utc)
        with Session(self._engine) as session:
            stmt = select(TextChunk).where(
                TextChunk.raw_file_id == raw_file_id,
                TextChunk.delete_time.is_(None),
            )
            entities = session.execute(stmt).scalars().all()
            for e in entities:
                e.delete_time = now
            session.commit()
            return len(entities)

    # ------------------------------------------------------------------
    # 事务作用域方法
    # ------------------------------------------------------------------

    def tx_bulk_insert(self, tx: Session, entities: list[TextChunk]) -> list[TextChunk]:
        if not entities:
            return []
        tx.add_all(entities)
        tx.flush()
        for e in entities:
            tx.refresh(e)
        return entities

    def tx_delete_by_raw_file_id(self, tx: Session, raw_file_id: str) -> int:
        now = datetime.now(timezone.utc)
        stmt = select(TextChunk).where(
            TextChunk.raw_file_id == raw_file_id,
            TextChunk.delete_time.is_(None),
        )
        entities = tx.execute(stmt).scalars().all()
        for e in entities:
            e.delete_time = now
        tx.flush()
        return len(entities)
```

---

## QARepository

```python
# app/storage/repositories/qa_session_repo.py
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import Engine, select, func
from sqlalchemy.orm import Session
from app.storage.entities.qa_session import QASession


class QARepository:

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # 自动提交方法
    # ------------------------------------------------------------------

    def insert(self, entity: QASession) -> QASession:
        with Session(self._engine) as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            session.commit()
            return entity

    def find_by_id(self, session_id: str) -> Optional[QASession]:
        with Session(self._engine) as session:
            stmt = select(QASession).where(
                QASession.id == session_id,
                QASession.delete_time.is_(None),
            )
            return session.execute(stmt).scalar_one_or_none()

    def find_paginated(
        self,
        workspace_id: str,
        user_id: Optional[str],
        page: int,
        size: int,
    ) -> tuple[list[QASession], int]:
        offset = (page - 1) * size
        with Session(self._engine) as session:
            base = select(QASession).where(
                QASession.workspace_id == workspace_id,
                QASession.delete_time.is_(None),
            )
            if user_id:
                base = base.where(QASession.user_id == user_id)
            total = session.execute(
                select(func.count()).select_from(base.subquery())
            ).scalar_one()
            items = session.execute(
                base.order_by(QASession.created_at.desc()).offset(offset).limit(size)
            ).scalars().all()
            return list(items), total

    def update(self, entity: QASession) -> QASession:
        with Session(self._engine) as session:
            entity.updated_at = datetime.now(timezone.utc)
            merged = session.merge(entity)
            session.flush()
            session.refresh(merged)
            session.commit()
            return merged

    # ------------------------------------------------------------------
    # 事务作用域方法
    # ------------------------------------------------------------------

    def tx_insert(self, tx: Session, entity: QASession) -> QASession:
        tx.add(entity)
        tx.flush()
        tx.refresh(entity)
        return entity

    def tx_update(self, tx: Session, entity: QASession) -> QASession:
        entity.updated_at = datetime.now(timezone.utc)
        merged = tx.merge(entity)
        tx.flush()
        tx.refresh(merged)
        return merged
```

---

## WikiPageRepository

```python
# app/storage/repositories/wiki_page_repo.py
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import Engine, select, func
from sqlalchemy.orm import Session
from app.storage.entities.wiki_page import WikiPage


class WikiPageRepository:

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # 自动提交方法
    # ------------------------------------------------------------------

    def insert(self, entity: WikiPage) -> WikiPage:
        with Session(self._engine) as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            session.commit()
            return entity

    def find_by_id(self, page_id: str) -> Optional[WikiPage]:
        with Session(self._engine) as session:
            stmt = select(WikiPage).where(
                WikiPage.id == page_id,
                WikiPage.delete_time.is_(None),
            )
            return session.execute(stmt).scalar_one_or_none()

    def find_by_topic(self, topic: str, workspace_id: str) -> Optional[WikiPage]:
        with Session(self._engine) as session:
            stmt = select(WikiPage).where(
                WikiPage.topic == topic,
                WikiPage.workspace_id == workspace_id,
                WikiPage.delete_time.is_(None),
            )
            return session.execute(stmt).scalar_one_or_none()

    def find_paginated(
        self,
        workspace_id: str,
        category: Optional[str],
        page: int,
        size: int,
    ) -> tuple[list[WikiPage], int]:
        offset = (page - 1) * size
        with Session(self._engine) as session:
            base = select(WikiPage).where(
                WikiPage.workspace_id == workspace_id,
                WikiPage.delete_time.is_(None),
            )
            if category:
                base = base.where(WikiPage.category == category)
            total = session.execute(
                select(func.count()).select_from(base.subquery())
            ).scalar_one()
            items = session.execute(
                base.order_by(WikiPage.topic.asc()).offset(offset).limit(size)
            ).scalars().all()
            return list(items), total

    def update(self, entity: WikiPage) -> WikiPage:
        with Session(self._engine) as session:
            entity.updated_at = datetime.now(timezone.utc)
            merged = session.merge(entity)
            session.flush()
            session.refresh(merged)
            session.commit()
            return merged

    def upsert(self, entity: WikiPage) -> WikiPage:
        """
        按 (workspace_id, topic) 插入或更新。
        若已存在同主题页面，则覆盖其可变字段
        （title、category、status、content、error、compiled_at、updated_at）。
        由编译 Celery 任务调用。
        """
        with Session(self._engine) as session:
            stmt = select(WikiPage).where(
                WikiPage.topic == entity.topic,
                WikiPage.workspace_id == entity.workspace_id,
                WikiPage.delete_time.is_(None),
            )
            existing = session.execute(stmt).scalar_one_or_none()
            if existing:
                existing.title = entity.title
                existing.category = entity.category
                existing.status = entity.status
                existing.content = entity.content
                existing.error = entity.error
                existing.compiled_at = entity.compiled_at
                existing.updated_at = datetime.now(timezone.utc)
                session.flush()
                session.refresh(existing)
                session.commit()
                return existing
            else:
                session.add(entity)
                session.flush()
                session.refresh(entity)
                session.commit()
                return entity

    def delete(self, page_id: str) -> None:
        """软删除。"""
        with Session(self._engine) as session:
            stmt = select(WikiPage).where(
                WikiPage.id == page_id,
                WikiPage.delete_time.is_(None),
            )
            entity = session.execute(stmt).scalar_one_or_none()
            if entity:
                entity.delete_time = datetime.now(timezone.utc)
                session.commit()

    # ------------------------------------------------------------------
    # 事务作用域方法
    # ------------------------------------------------------------------

    def tx_insert(self, tx: Session, entity: WikiPage) -> WikiPage:
        tx.add(entity)
        tx.flush()
        tx.refresh(entity)
        return entity

    def tx_update(self, tx: Session, entity: WikiPage) -> WikiPage:
        entity.updated_at = datetime.now(timezone.utc)
        merged = tx.merge(entity)
        tx.flush()
        tx.refresh(merged)
        return merged

    def tx_upsert(self, tx: Session, entity: WikiPage) -> WikiPage:
        stmt = select(WikiPage).where(
            WikiPage.topic == entity.topic,
            WikiPage.workspace_id == entity.workspace_id,
            WikiPage.delete_time.is_(None),
        )
        existing = tx.execute(stmt).scalar_one_or_none()
        if existing:
            existing.title = entity.title
            existing.category = entity.category
            existing.status = entity.status
            existing.content = entity.content
            existing.error = entity.error
            existing.compiled_at = entity.compiled_at
            existing.updated_at = datetime.now(timezone.utc)
            tx.flush()
            tx.refresh(existing)
            return existing
        else:
            tx.add(entity)
            tx.flush()
            tx.refresh(entity)
            return entity
```

---

## 多操作事务示例

当 Service 需要跨多个 Repository 保证原子性时，打开一个 Session 并传给每个 `tx_` 方法：

```python
from sqlalchemy.orm import Session

with Session(self._rt.db_engine) as tx:
    with tx.begin():           # 发生异常时自动回滚
        raw_file = raw_file_repo.tx_insert(tx, raw_file)
        chunks = chunk_repo.tx_bulk_insert(tx, chunks)
        raw_file.chunk_count = len(chunks)
        raw_file_repo.tx_update(tx, raw_file)
    # tx.begin() 上下文管理器在此处提交
```

`session.begin()` 返回一个上下文管理器，正常退出时提交，发生任何异常时回滚，
因此在多 Repository 场景下 Service 无需手动调用 `commit()`。
