# MessageQueue Protocol

- **功能**：Celery Broker / Result Backend、自定义任务队列、异步事件总线
- **推荐实现**：Redis 8.6.2（客户端 redis-py 5.3.0，与 CacheStore 共用版本）
- **Runtime 字段**：`rt.queue: MessageQueue`
- **错误码**：失败时抛 `Match3Exception.of_code(codes.REDIS_ERROR, ...)` (500002)

---

## 类清单

| 类 | 文件 | 类型 |
|----|------|------|
| `MessageQueue` | `backend/runtime/protocols/message_queue/message_queue.py` | Protocol |

---

## MessageQueue

```python
# backend/runtime/protocols/message_queue/message_queue.py
from typing import Protocol

class MessageQueue(Protocol):
    """FIFO list-based message queue protocol (async)."""

    async def lpush(self, key: str, *values: str) -> int: ...
    async def rpush(self, key: str, *values: str) -> int: ...
    async def lpop(self, key: str) -> str | None: ...
    async def rpop(self, key: str) -> str | None: ...
    async def brpop(
        self,
        keys: list[str],
        timeout: int = 0,
    ) -> tuple[str, str] | None: ...
    async def blpop(
        self,
        keys: list[str],
        timeout: int = 0,
    ) -> tuple[str, str] | None: ...
    async def llen(self, key: str) -> int: ...
    async def close(self) -> None: ...
```

### 方法签名

| 方法 | 参数 | 返回 |
|------|------|------|
| `lpush` / `rpush` | `key: str`, `*values: str` | `int`，操作后队列长度 |
| `lpop` / `rpop` | `key: str` | `str \| None`，队列空返回 `None` |
| `brpop` / `blpop` | `keys: list[str]`, `timeout: int = 0` | `(queue_key, value) \| None`，`timeout=0` 永久阻塞 |
| `llen` | `key: str` | `int`，队列当前长度 |
| `close` | — | `None` |

### 使用约束

- **FIFO 约定**：生产者用 `rpush`，消费者用 `blpop` / `lpop`。
- **值类型固定为 `str`**：消息内容由业务层自行序列化（Celery 使用 JSON 或 pickle）。
- **Celery 直连**：Celery 的 broker / backend URL 直接从 `env.REDIS_BROKER_URL` / `env.REDIS_RESULT_URL` 读取，不经过本 Protocol。本 Protocol 仅用于应用层自定义队列。
- **与 `CacheStore` 严格分离**：字符串的 `get` / `set` / `incr` 属于 `CacheStore`。

---

## 使用示例

```python
# 生产者
task_payload = json.dumps({"task_id": task_id, "args": args})
await rt.queue.rpush("match3:jobs:ingest", task_payload)

# 消费者（阻塞 5 秒）
result = await rt.queue.brpop(["match3:jobs:ingest"], timeout=5)
if result:
    _, payload = result
    job = json.loads(payload)
```

---

## 关联文档

- [implementation.md](./implementation.md) — Redis 适配器
- [versions/redis-v8.6.2.md](./versions/redis-v8.6.2.md) — redis-py 5.3 接口速查
- [../cache-store/protocol.md](../cache-store/protocol.md) — 与 CacheStore 的职责边界
- [../config.md](../config.md) — `runtime.message_queue.*` 配置
