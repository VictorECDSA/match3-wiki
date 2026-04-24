# ACID 事务

**ACID** 是关系数据库和部分 NoSQL（包括 Neo4j）保证事务可靠性的四个核心属性的缩写：**原子性（Atomicity）**、**一致性（Consistency）**、**隔离性（Isolation）**、**持久性（Durability）**。

## 四个属性

### 原子性（Atomicity）

事务内的所有操作要么全部成功，要么全部回滚，不存在"部分提交"。

```cypher
// Both nodes and the relationship must succeed or all roll back
BEGIN
MERGE (a:Entity {name: "game"})
MERGE (b:Entity {name: "player"})
CREATE (a)-[:HAS]->(b)
COMMIT
```

### 一致性（Consistency）

事务执行前后，数据库都处于满足所有约束（唯一性、存在性等）的合法状态。

### 隔离性（Isolation）

并发事务互不干扰。Neo4j 默认使用**读已提交（Read Committed）**隔离级别：一个事务只能看到已提交的数据，避免脏读，但可能出现不可重复读。

### 持久性（Durability）

事务提交后，数据持久化到磁盘。即使服务器崩溃，提交的数据也不会丢失。Neo4j 通过预写日志（WAL，Write-Ahead Log）实现持久性。

## Neo4j 中的事务使用

```python
# execute_write: wraps the work function in a write transaction with auto-retry
def _write_entity(tx, name: str, entity_type: str):
    tx.run(
        "MERGE (e:Entity {name: $name}) SET e.type = $type",
        name=name, type=entity_type,
    )

with driver.session() as session:
    session.execute_write(_write_entity, name="match3", entity_type="game_genre")
```

`execute_write` 在出现短暂错误（如死锁）时自动重试，业务代码无需手动处理。
