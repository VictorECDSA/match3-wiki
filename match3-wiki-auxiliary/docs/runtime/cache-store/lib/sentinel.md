# Sentinel（哨兵高可用）

**Redis Sentinel（哨兵）** 是 Redis 官方提供的高可用（HA，High Availability）解决方案。由多个 Sentinel 进程组成的哨兵集群持续监控 Redis 主从节点，在主节点宕机时自动触发故障转移（Failover），将某个从节点提升为新主节点，并通知客户端连接新主节点。

## 架构组成

```
┌─────────────┐         ┌─────────────┐
│  Sentinel 1 │         │  Sentinel 2 │
└──────┬──────┘         └──────┬──────┘
       │  monitor              │  monitor
       ▼                       ▼
┌─────────────────────────────────────┐
│  Redis Master (主)   ←→   Replica   │
└─────────────────────────────────────┘
```

## 工作流程

1. 所有 Sentinel 持续向主节点发送 `PING`
2. 某个 Sentinel 判断主节点无响应（主观下线，SDOWN）
3. 超过半数 Sentinel 确认（客观下线，ODOWN）
4. Sentinel 集群选举 Leader，由 Leader 执行故障转移
5. 选出新主节点，其他从节点切换复制目标
6. Sentinel 通知客户端新的主节点地址

## Python 客户端连接

```python
from redis.asyncio import Sentinel

sentinel = Sentinel(
    [("sentinel-1", 26379), ("sentinel-2", 26379), ("sentinel-3", 26379)],
    socket_timeout=0.5,
)

# Get master connection (auto-discovers current master)
master = sentinel.master_for("mymaster", socket_timeout=0.5)
await master.set("key", "value")

# Get replica connection for read-only operations
replica = sentinel.slave_for("mymaster", socket_timeout=0.5)
await replica.get("key")
```

## 本项目的部署模式

本项目单节点开发部署不配置 Sentinel。协议层（`CacheStore` Protocol）对业务代码完全透明，若生产环境需要高可用，只需在 `build_runtime()` 中替换为 Sentinel 连接，业务代码零改动。
