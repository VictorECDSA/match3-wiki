# Pipeline（管道批处理）

**Pipeline（管道）** 是 Redis 的批量命令优化机制：将多个命令一次性发送到服务器，服务器顺序执行后批量返回所有结果，而不是每条命令单独一次网络往返。

## 问题背景

每次 Redis 命令执行一次完整的网络往返（RTT，Round-Trip Time）。若 RTT 为 1ms，100 条独立命令耗时 100ms。Pipeline 将这 100 条命令打包为 1 次往返，理论上耗时降至接近 1ms（加上服务端处理时间）。

## 使用方式

```python
# Without pipeline: 3 round trips
await redis.set("key1", "val1")
await redis.set("key2", "val2")
await redis.set("key3", "val3")

# With pipeline: 1 round trip for all 3 commands
async with redis.pipeline(transaction=False) as pipe:
    pipe.set("key1", "val1")
    pipe.set("key2", "val2")
    pipe.set("key3", "val3")
    results = await pipe.execute()   # [True, True, True]
```

## Pipeline vs 事务（MULTI/EXEC）

```python
# pipeline(transaction=False) — batch send only, no atomicity guarantee
# Other clients can interleave commands between pipeline commands on server side

# pipeline(transaction=True) — wraps in MULTI/EXEC, atomic
async with redis.pipeline(transaction=True) as pipe:
    pipe.incr("counter")
    pipe.expire("counter", 3600)
    results = await pipe.execute()   # atomic: either both execute or neither
```

| 特性 | Pipeline（非事务） | MULTI/EXEC 事务 |
|------|--------------------|-----------------|
| 原子性 | ✗ | ✓ |
| 批量网络优化 | ✓ | ✓ |
| 可回滚 | ✗ | ✗（Redis 事务不支持回滚） |
| 适用场景 | 批量写入缓存 | 需要原子性的计数器操作 |

## 典型应用

批量写入嵌入向量的缓存标记、批量更新多个 chunk 的状态标志等场景，使用非事务 Pipeline 显著提升吞吐量。
