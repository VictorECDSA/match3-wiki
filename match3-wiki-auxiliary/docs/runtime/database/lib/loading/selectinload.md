# selectinload（子查询预加载）

**selectinload** 是 SQLAlchemy 中最常用的关系预加载策略之一，用于解决 [N+1 查询问题](../N+1.md)。它通过发出一条额外的 `SELECT ... WHERE primary_key IN (...)` 查询，一次性加载所有父记录的关联子记录，再在 Python 层完成对象关联。

## 工作原理

```
Query 1: SELECT * FROM t_raw_files LIMIT 20
→ get IDs: [id1, id2, ..., id20]

Query 2: SELECT * FROM t_text_chunks WHERE raw_file_id IN (id1, id2, ..., id20)
→ distribute chunks to corresponding RawFile objects in Python
```

总计 2 次查询，而非 N+1。

## 使用方式

```python
from sqlalchemy.orm import selectinload
from sqlalchemy import select

result = await session.execute(
    select(RawFile)
    .options(selectinload(RawFile.chunks))
    .where(RawFile.workspace_id == workspace_id)
)
files = result.scalars().all()

# No additional queries triggered here
for file in files:
    print(f"{file.id}: {len(file.chunks)} chunks")
```

## 嵌套预加载

多层关系可以链式嵌套：

```python
.options(
    selectinload(RawFile.chunks).selectinload(TextChunk.qa_records)
)
```

## 与 joinedload 的对比

| 特性 | selectinload | joinedload |
|------|-------------|------------|
| 查询数量 | 2 次（主查询 + IN 子查询） | 1 次（JOIN） |
| 适合场景 | 一对多（一个文件多个块） | 多对一（一个块归属一个文件） |
| 结果集膨胀 | 无 | 有（JOIN 产生笛卡尔积行重复） |
| 分页兼容性 | ✓ | 需注意（JOIN 影响 LIMIT 行为） |

**一般规则**：一对多关系用 selectinload，多对一（加载单个关联对象）用 joinedload。
