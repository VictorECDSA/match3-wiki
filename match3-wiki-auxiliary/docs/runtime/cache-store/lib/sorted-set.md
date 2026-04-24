# 有序集合（Sorted Set）

**有序集合（Sorted Set，ZSet）** 是 Redis 的核心数据结构之一，每个元素关联一个浮点分数（Score），集合内所有元素按分数从小到大自动排序。与普通集合（Set）不同，Sorted Set 既保证元素唯一性，又支持高效按分数范围查询。

## 核心命令

```python
# Add elements with scores
await redis.zadd("leaderboard:workspace-123", {"user-a": 100.0, "user-b": 85.5})

# Get top N by score (descending)
top_users = await redis.zrevrange("leaderboard:workspace-123", 0, 9, withscores=True)
# [("user-a", 100.0), ("user-b", 85.5), ...]

# Get rank of an element (0-indexed, ascending)
rank = await redis.zrank("leaderboard:workspace-123", "user-b")

# Get elements within a score range
members = await redis.zrangebyscore("leaderboard:workspace-123", 80, 100)

# Increment score
await redis.zincrby("leaderboard:workspace-123", 10.0, "user-b")

# Remove element
await redis.zrem("leaderboard:workspace-123", "user-a")
```

## 内部实现

Sorted Set 内部使用两个数据结构：

- **跳表（Skip List）**：按分数有序存储，支持 O(log N) 的范围查询
- **哈希表（Hash Table）**：按成员名称索引，支持 O(1) 的分数查找

两者保持同步，提供兼顾查找和范围遍历的高效实现。

## 常见应用场景

| 场景 | Score 含义 |
|------|-----------|
| 排行榜 | 分数、积分 |
| 延迟任务队列 | 执行时间戳（Unix timestamp） |
| 限流滑动窗口 | 请求时间戳 |
| 热词统计 | 词频计数 |

## 延迟任务队列模式

Sorted Set 可以模拟优先级队列：将任务 ID 以执行时间为 Score 写入，定期用 `zrangebyscore` 取出到期任务：

```python
# Schedule a task
await redis.zadd("delayed_tasks", {task_id: execute_at_timestamp})

# Poll due tasks
now = time.time()
due_tasks = await redis.zrangebyscore("delayed_tasks", 0, now)
```
