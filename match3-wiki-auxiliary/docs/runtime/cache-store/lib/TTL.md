# TTL（生存时间）

**TTL（Time to Live，生存时间）** 是 Redis 键的过期机制：为一个键设置存活秒数，到期后 Redis 自动删除该键，无需业务代码手动清理。

## 基本用法

```python
# Set key with TTL (in seconds)
await redis.set("session:user-123", session_data, ex=3600)   # expire in 1 hour

# Set TTL on an existing key
await redis.expire("cache:query-result", 300)   # expire in 5 minutes

# Check remaining TTL
ttl = await redis.ttl("session:user-123")
# Returns: remaining seconds, -1 (no TTL), or -2 (key doesn't exist)
```

## 精度

Redis TTL 最小粒度为秒（`EXPIRE`）。需要毫秒精度时使用 `PEXPIRE`（毫秒）或 `SET key value PX milliseconds`。

## 常见使用场景

| 场景 | 典型 TTL |
|------|----------|
| 用户会话（Session） | 1–24 小时 |
| API 响应缓存 | 5–60 分钟 |
| 短信验证码 | 5–10 分钟 |
| 分布式锁 | 操作预估时长 × 2（防止死锁） |

## TTL 与驱逐策略的关系

TTL 是主动过期（到期精确删除），而[驱逐策略](./eviction.md)（LRU/LFU）是内存不足时的被动淘汰。两者相互补充：给缓存键设置合理 TTL，可以显著减少内存压力，降低被驱逐的概率。

## 惰性删除 vs 定期扫描

Redis 采用两种删除策略结合：

- **惰性删除（Lazy Expiration）**：访问键时检查是否过期，过期则删除并返回 nil
- **定期扫描（Active Expiration）**：后台每隔一段时间随机抽样部分键，删除已过期的

两者结合保证过期键最终被清理，但不保证精确到期即删除。
