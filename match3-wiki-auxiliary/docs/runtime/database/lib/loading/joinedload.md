# joinedload（JOIN 预加载）

**joinedload** 是 SQLAlchemy 中另一种关系预加载策略，通过在主查询中添加 `LEFT OUTER JOIN` 将关联对象一并取回，只需 1 次数据库往返。

## 工作原理

```sql
-- joinedload generates a single SQL with JOIN
SELECT t_raw_files.*, t_workspaces.*
FROM t_raw_files
LEFT OUTER JOIN t_workspaces ON t_raw_files.workspace_id = t_workspaces.id
WHERE t_raw_files.id = 'file-123'
```

SQLAlchemy 从 JOIN 后的扁平结果集中重建对象树。

## 使用方式

```python
from sqlalchemy.orm import joinedload
from sqlalchemy import select

result = await session.execute(
    select(RawFile)
    .options(joinedload(RawFile.workspace))   # many-to-one: file → workspace
    .where(RawFile.id == file_id)
)
file = result.scalars().first()
print(file.workspace.name)   # no extra query
```

## 注意事项

### 结果集膨胀（Cartesian Product）

当关联关系为一对多时，JOIN 会产生笛卡尔积：1 个文件有 100 个块，JOIN 后返回 100 行，每行都重复文件字段。SQLAlchemy 会自动去重，但传输数据量增大。

```python
# WARNING: joinedload on one-to-many causes result set bloat
# Use selectinload instead for one-to-many
.options(joinedload(RawFile.chunks))   # 100 chunks → 100 duplicate file rows in SQL result
```

### 分页问题

在有分页（`LIMIT`/`OFFSET`）的查询中使用 joinedload 一对多关系时，`LIMIT` 作用在 JOIN 后的行数上，导致分页结果不准确。应改用 selectinload。

## 与 selectinload 的选择总结

- **多对一（N 个子记录 → 1 个父记录）**：用 joinedload，1 次查询，无膨胀
- **一对多（1 个父记录 → N 个子记录）**：用 [selectinload](./selectinload.md)，2 次查询，无膨胀

详见 [N+1.md](../N+1.md)。
