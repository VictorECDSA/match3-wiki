# 消息队列实现方案 — Redis

## 概述

使用 **Redis v8.6.2** 实现 `MessageQueue` Protocol（Celery Broker/Backend），通过 **redis-py v5.3.0** 提供异步任务队列服务。

---

## 工厂函数

```python
# backend/runtime_impl/implements/message_queue/message_queue.py
from redis.asyncio import Redis
from backend.config import Config, Env
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.message_queue import MessageQueue
from .impl_redis.redis_adapter import RedisMessageQueue

def create_message_queue(config: Config, env: Env, logger: Logger) -> MessageQueue:
    """创建 MessageQueue 实例
    
    Args:
        config: 配置对象
        env: 环境变量
        logger: 日志记录器
    
    Returns:
        实现了 MessageQueue Protocol 的 RedisMessageQueue 实例
    
    Raises:
        ValueError: provider 不支持时抛出
    """
    provider = config.runtime.message_queue.provider
    
    if provider == "redis":
        redis_client = Redis.from_url(
            env.REDIS_BROKER_URL,
            max_connections=config.runtime.message_queue.implementations.redis.max_connections,
            socket_timeout=config.runtime.message_queue.implementations.redis.socket_timeout,
            decode_responses=True,
        )
        
        logger.info("Redis message queue client initialized")
        return RedisMessageQueue(redis_client)
    else:
        raise ValueError(f"Unsupported message_queue provider: {provider}")
```

---

## 适配器实现

```python
# backend/runtime_impl/implements/message_queue/impl_redis/redis_adapter.py
from redis.asyncio import Redis
from backend.runtime.protocols.message_queue import MessageQueue

class RedisMessageQueue:
    """Redis 适配器，实现 MessageQueue Protocol"""
    
    def __init__(self, client: Redis):
        self._client = client
    
    async def enqueue(self, queue_name: str, message: str) -> bool:
        """将消息加入队列"""
        return await self._client.rpush(queue_name, message) > 0
    
    async def dequeue(self, queue_name: str, timeout: int = 0) -> str | None:
        """从队列取出消息（阻塞）"""
        result = await self._client.blpop(queue_name, timeout=timeout)
        return result[1].decode() if result else None
    
    async def length(self, queue_name: str) -> int:
        """获取队列长度"""
        return await self._client.llen(queue_name)
```

---

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  message_queue:
    provider: redis
    implementations:
      redis:
        max_connections: 50    # 最大连接数
        socket_timeout: 5      # Socket 超时（秒）

celery:
  task_time_limit: 3600          # 任务硬超时（秒）
  task_soft_time_limit: 3000     # 任务软超时（秒）
  worker_concurrency: 4          # Worker 并发数
  worker_prefetch_multiplier: 2  # 预取任务倍数
```

### Env (.env)

```bash
REDIS_BROKER_URL=redis://localhost:6379/1
REDIS_RESULT_URL=redis://localhost:6379/2
```

---

## 相关文档

- **[protocol.md](./protocol.md)** — MessageQueue Protocol 定义
- **[versions/redis-v8.6.2.md](./versions/redis-v8.6.2.md)** — Redis API 详细说明
