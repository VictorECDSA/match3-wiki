# 缓存存储实现方案 — Redis

## 概述

使用 **Redis v8.6.2** 实现 `CacheStore` Protocol，通过 **redis-py v5.3.0** 异步客户端提供高性能缓存服务。

---

## 工厂函数

```python
# backend/runtime_impl/implements/cache_store/cache_store.py
from redis.asyncio import Redis
from backend.config import Config, Env
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.cache_store import CacheStore
from .impl_redis.redis_adapter import RedisAdapter

def create_cache_store(config: Config, env: Env, logger: Logger) -> CacheStore:
    """创建 CacheStore 实例
    
    Args:
        config: 配置对象
        env: 环境变量
        logger: 日志记录器
    
    Returns:
        实现了 CacheStore Protocol 的 RedisAdapter 实例
    
    Raises:
        ValueError: provider 不支持时抛出
    """
    provider = config.runtime.cache_store.provider
    
    if provider == "redis":
        redis_client = Redis.from_url(
            env.REDIS_CACHE_URL,
            max_connections=config.runtime.cache_store.implementations.redis.max_connections,
            socket_timeout=config.runtime.cache_store.implementations.redis.socket_timeout,
            decode_responses=True,
        )
        
        logger.info("Redis cache client initialized")
        return RedisAdapter(redis_client)
    else:
        raise ValueError(f"Unsupported cache_store provider: {provider}")
```

---

## 适配器实现

```python
# backend/runtime_impl/implements/cache_store/impl_redis/redis_adapter.py
from redis.asyncio import Redis
from backend.runtime.protocols.cache_store import CacheStore

class RedisAdapter:
    """Redis 适配器，实现 CacheStore Protocol"""
    
    def __init__(self, client: Redis):
        self._client = client
    
    async def get(self, key: str) -> str | None:
        """获取缓存值"""
        result = await self._client.get(key)
        return result.decode() if result else None
    
    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """设置缓存值，可选过期时间（秒）"""
        return await self._client.set(key, value, ex=ex)
    
    async def delete(self, key: str) -> bool:
        """删除缓存键"""
        return await self._client.delete(key) > 0
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return await self._client.exists(key) > 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """设置键的过期时间"""
        return await self._client.expire(key, seconds)
    
    async def incr(self, key: str) -> int:
        """递增计数器"""
        return await self._client.incr(key)
    
    async def decr(self, key: str) -> int:
        """递减计数器"""
        return await self._client.decr(key)
```

---

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  cache_store:
    provider: redis
    implementations:
      redis:
        max_connections: 50    # 最大连接数
        socket_timeout: 5      # Socket 超时（秒）
```

### Env (.env)

```bash
REDIS_CACHE_URL=redis://localhost:6379/0
```

---

## 相关文档

- **[protocol.md](./protocol.md)** — CacheStore Protocol 定义
- **[versions/redis-v8.6.2.md](./versions/redis-v8.6.2.md)** — Redis API 详细说明
