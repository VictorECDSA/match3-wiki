# 事务（Transaction）与保存点（Savepoint）

**事务（Transaction）** 是数据库保证多个操作原子性的机制：事务内的所有操作要么全部提交（Commit），要么全部回滚（Rollback），中间状态不会暴露给其他并发访问者。**保存点（Savepoint）** 是事务内部的检查点，允许部分回滚而不放弃整个事务。

## SQLAlchemy 中的事务模式

### 自动提交（autocommit）

单次 `INSERT`/`UPDATE` 操作默认在独立事务中自动提交，无需显式管理：

```python
# Repository.insert() uses auto-commit
async def insert(self, entity: RawFile) -> RawFile:
    async with self._session_factory() as session:
        session.add(entity)
        await session.commit()
        await session.refresh(entity)
        return entity
```

### 显式事务（tx 模式）

多个操作需原子性时，使用显式事务（`tx_insert`、`tx_update` 等方法）：

```python
# Repository.tx_insert() — caller manages the transaction
async def tx_insert(self, session: AsyncSession, entity: RawFile) -> RawFile:
    session.add(entity)
    await session.flush()   # send to DB but don't commit yet
    return entity

# Usage in service layer
async with session_factory() as session:
    async with session.begin():           # begin transaction
        file = await raw_file_repo.tx_insert(session, raw_file)
        chunk = await chunk_repo.tx_insert(session, text_chunk)
    # auto-commit when exiting "begin()" block without error
    # auto-rollback on exception
```

## 保存点（Savepoint）

保存点允许在事务内设置检查点，出错时回滚到保存点而不放弃整个事务：

```python
async with session.begin():
    await session.execute(insert_main_record)

    savepoint = await session.begin_nested()   # create savepoint
    try:
        await session.execute(insert_optional_record)
        await savepoint.commit()
    except Exception:
        await savepoint.rollback()   # roll back only to savepoint
        # main_record is still intact, transaction continues
```

## 本项目的事务约定

- `Repository.insert()` — 自动提交，单独操作用
- `Repository.tx_insert(session, entity)` — 不提交，供调用方在外部事务中使用
- 服务层需要多个仓库操作原子性时，用 `session.begin()` 上下文管理器统一管理
