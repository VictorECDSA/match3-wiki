# MessageQueue 实现 — Redis 8.6.2

## 文件布局

```
backend/runtime_impl/implements/message_queue/
├── message_queue.py                # create_message_queue(config, env, logger) -> MessageQueue
└── impl_redis/
    └── redis_message_queue.py      # RedisMessageQueue
```

依赖：`redis-py` 5.3.0+（`redis.asyncio.Redis`）。

---

## 工厂函数

```python
# backend/runtime_impl/implements/message_queue/message_queue.py
from redis.asyncio import Redis
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.config import Config, Env
from backend.runtime.protocols.logger.logger import Logger
from backend.runtime.protocols.message_queue.message_queue import MessageQueue
from backend.runtime_impl.implements.message_queue.impl_redis.redis_message_queue import RedisMessageQueue

def create_message_queue(config: Config, env: Env, logger: Logger) -> MessageQueue:
    provider = config.runtime.message_queue.provider

    if provider != "redis":
        raise Match3Exception.of_code(
            codes.CONFIG_MISSING_REQUIRED,
            "unsupported message_queue provider",
        ).ctx(provider=provider)

    impl = config.runtime.message_queue.implementations.redis
    try:
        client = Redis.from_url(
            env.REDIS_BROKER_URL,
            max_connections=impl.max_connections,
            socket_timeout=impl.socket_timeout,
            decode_responses=True,
        )
    except Exception as e:
        raise Match3Exception.of_code(codes.REDIS_ERROR, "failed to init redis queue") \
            .ctx(url=env.REDIS_BROKER_URL).as_ex(e)

    logger.info("redis message queue initialized", max_connections=impl.max_connections)
    return RedisMessageQueue(client)
```

---

## 适配器

```python
# backend/runtime_impl/implements/message_queue/impl_redis/redis_message_queue.py
from redis.asyncio import Redis
from app.common.exceptions import Match3Exception
from app.common.constants import codes

class RedisMessageQueue:
    """Redis implementation of MessageQueue protocol."""

    def __init__(self, client: Redis):
        self._client = client

    async def lpush(self, key: str, *values: str) -> int:
        try:
            return await self._client.lpush(key, *values)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis lpush failed") \
                .ctx(key=key, value_count=len(values)).as_ex(e)

    async def rpush(self, key: str, *values: str) -> int:
        try:
            return await self._client.rpush(key, *values)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis rpush failed") \
                .ctx(key=key, value_count=len(values)).as_ex(e)

    async def lpop(self, key: str) -> str | None:
        try:
            return await self._client.lpop(key)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis lpop failed") \
                .ctx(key=key).as_ex(e)

    async def rpop(self, key: str) -> str | None:
        try:
            return await self._client.rpop(key)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis rpop failed") \
                .ctx(key=key).as_ex(e)

    async def brpop(self, keys: list[str], timeout: int = 0) -> tuple[str, str] | None:
        try:
            return await self._client.brpop(keys, timeout=timeout)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis brpop failed") \
                .ctx(key_count=len(keys), timeout=timeout).as_ex(e)

    async def blpop(self, keys: list[str], timeout: int = 0) -> tuple[str, str] | None:
        try:
            return await self._client.blpop(keys, timeout=timeout)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis blpop failed") \
                .ctx(key_count=len(keys), timeout=timeout).as_ex(e)

    async def llen(self, key: str) -> int:
        try:
            return await self._client.llen(key)
        except Exception as e:
            raise Match3Exception.of_code(codes.REDIS_ERROR, "redis llen failed") \
                .ctx(key=key).as_ex(e)

    async def close(self) -> None:
        await self._client.aclose()
```

---

## Celery 集成

Celery 直接从 `.env` 读取 broker / backend URL，**不经过本 Protocol**：

```python
# backend/app/workers/celery_app.py
from celery import Celery
import os

celery_app = Celery(
    "match3",
    broker=os.environ["REDIS_BROKER_URL"],
    backend=os.environ["REDIS_RESULT_URL"],
)
```

本 Protocol 仅用于应用层自定义队列（如跨服务通知、业务事件总线）。

---

## 配置与环境

- `config.yaml`：`runtime.message_queue.*`
- `.env`：`REDIS_BROKER_URL`、`REDIS_RESULT_URL`

详见 [`../config.md`](../config.md)。
