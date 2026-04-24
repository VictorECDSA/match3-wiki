# 驱逐策略（Eviction Policy）

当 Redis 内存使用量达到 `maxmemory` 上限时，需要决定删除哪些键来腾出空间。**驱逐策略（Eviction Policy）** 定义了这一选择规则。

## 主要驱逐策略

| 策略 | 全称 | 行为 |
|------|------|------|
| `noeviction` | 不驱逐 | 内存满时拒绝写入，返回错误（默认值） |
| `allkeys-lru` | All Keys LRU | 从**所有键**中删除**最近最少使用（LRU）** 的键 |
| `volatile-lru` | Volatile LRU | 只从**设有 TTL 的键**中删除最近最少使用的键 |
| `allkeys-lfu` | All Keys LFU | 从所有键中删除**最不频繁使用（LFU）** 的键 |
| `volatile-lfu` | Volatile LFU | 只从设有 TTL 的键中删除最不频繁使用的键 |
| `allkeys-random` | All Keys Random | 随机删除任意键 |
| `volatile-ttl` | Volatile TTL | 优先删除剩余 TTL 最短的键 |

## LRU vs LFU

**LRU（Least Recently Used，最近最少使用）**：按最后访问时间淘汰，长时间未被访问的键优先删除。适合缓存场景，最近访问的数据"热度"高。

**LFU（Least Frequently Used，最不频繁使用）**：按访问频率淘汰，总访问次数最少的键优先删除。适合有明显冷热分布的场景（如少数热点数据被频繁访问）。

## 本项目配置

缓存场景使用 `allkeys-lru`，确保内存满时自动淘汰最冷数据，不影响写入：

```yaml
# redis.conf or docker-compose environment
maxmemory: 512mb
maxmemory-policy: allkeys-lru
```

## Redis 的近似 LRU

Redis 不维护完整的 LRU 链表（代价太高），而是每次驱逐时随机采样若干键，选出其中最久未使用的删除——"近似 LRU"。采样数由 `maxmemory-samples`（默认 5）控制，值越大越精准但 CPU 消耗越高。
