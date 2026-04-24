# CacheStore 实现 — Redis 8.6.2

## 文件布局

```
backend/runtime_impl/implements/cache_store/
├── cache_store.py                  # create_cache_store(config, env, logger) -> CacheStore
└── impl_redis/
    └── redis_cache_store.py        # RedisCacheStore
```

依赖：`redis-py` 5.3.0+（`redis.asyncio.Redis`）。

---

## 工厂函数

```python
# backend/runtime_impl/implements/cache_store/cache_store.py
from redis.asyncio import Redis
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.config import Config, Env
from backend.runtime.protocols.logger.logger import Logger
from backend.runtime.protocols.cache_store.cache_store import CacheStore
from backend.runtime_impl.implements.cache_store.impl_redis.redis_cache_store import RedisCacheStore

def create_cache_store(config: Config, env: Env, logger: Logger) -> CacheStore:
    provider = config.runtime.cache_store.provider

    if provider != "redis":
        raise Match3Exception.of_code(
            codes.CONFIG_MISSING_REQUIRED,
            "unsupported cache_store provider",
        ).ctx(provider=provider)

    impl = config.runtime.cache_store.implementations.redis
    try:
        client = Redis.from_url(
            env.REDIS_CACHE_URL,
            max_connections=impl.max_connections,
            socket_timeout=impl.socket_timeout,
            decode_responses=impl.decode_responses,
        )
    except Exception as e:
        raise Match3Exception.of_code(codes.REDIS_ERROR, "failed to init redis cache") \
            .ctx(url=env.REDIS_CACHE_URL).as_ex(e)

    logger.info("redis cache initialized", max_connections=impl.max_connections)
    return RedisCacheStore(client)
```

---

## 适配器

```python
# backend/runtime_impl/implements/cache_store/impl_redis/redis_cache_store.py
from redis.asyncio import Redis
from app.common.exceptions import Match3Exception
from app.common.constants import codes

class RedisCacheStore:
    """Redis implementation of CacheStore protocol."""

    def __init__(self, client: Redis):
        self._client = client

    async def get(self, key: str) -> str | None:
        try:
            return await self._client.get(key)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis get failed") \
                .ctx(key=key).as_ex(e)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        try:
            return bool(await self._client.set(key, value, ex=ex))
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis set failed") \
                .ctx(key=key, ex=ex).as_ex(e)

    async def delete(self, *keys: str) -> int:
        try:
            return await self._client.delete(*keys)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis delete failed") \
                .ctx(key_count=len(keys)).as_ex(e)

    async def exists(self, *keys: str) -> int:
        try:
            return await self._client.exists(*keys)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis exists failed") \
                .ctx(key_count=len(keys)).as_ex(e)

    async def expire(self, key: str, seconds: int) -> bool:
        try:
            return bool(await self._client.expire(key, seconds))
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis expire failed") \
                .ctx(key=key, seconds=seconds).as_ex(e)

    async def ttl(self, key: str) -> int:
        try:
            return await self._client.ttl(key)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis ttl failed") \
                .ctx(key=key).as_ex(e)

    async def incr(self, key: str, amount: int = 1) -> int:
        try:
            return await self._client.incrby(key, amount)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis incr failed") \
                .ctx(key=key, amount=amount).as_ex(e)

    async def decr(self, key: str, amount: int = 1) -> int:
        try:
            return await self._client.decrby(key, amount)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis decr failed") \
                .ctx(key=key, amount=amount).as_ex(e)

    async def close(self) -> None:
        await self._client.aclose()
```

---

## 配置与环境

- `config.yaml`：`runtime.cache_store.*`
- `.env`：`REDIS_CACHE_URL`

详见 [`../config.md`](../config.md)。
