# CacheStore Protocol

- **功能**：键值缓存、计数器、限流、TTL 控制
- **推荐实现**：Redis 8.6.2（客户端 redis-py 5.3.0）
- **Runtime 字段**：`rt.cache: CacheStore`
- **错误码**：失败时抛 `Match3Exception.of_code(codes.REDIS_ERROR, ...)` (500002)

---

## 类清单

| 类 | 文件 | 类型 |
|----|------|------|
| `CacheStore` | `backend/runtime/protocols/cache_store/cache_store.py` | Protocol |

---

## CacheStore

```python
# backend/runtime/protocols/cache_store/cache_store.py
from typing import Protocol

class CacheStore(Protocol):
    """Key-value cache protocol (async)."""

    async def get(self, key: str) -> str | None: ...
    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
    ) -> bool: ...
    async def delete(self, *keys: str) -> int: ...
    async def exists(self, *keys: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> bool: ...
    async def ttl(self, key: str) -> int: ...
    async def incr(self, key: str, amount: int = 1) -> int: ...
    async def decr(self, key: str, amount: int = 1) -> int: ...
    async def close(self) -> None: ...
```

### 方法签名

| 方法 | 参数 | 返回 |
|------|------|------|
| `get` | `key: str` | `str \| None`，缺失返回 `None` |
| `set` | `key: str`, `value: str`, `ex: int \| None = None`（TTL 秒数） | `bool`，成功为 `True` |
| `delete` | `*keys: str` | `int`，实际删除的键数 |
| `exists` | `*keys: str` | `int`，存在的键数 |
| `expire` | `key: str`, `seconds: int` | `bool` |
| `ttl` | `key: str` | `int`，`-1` 永不过期，`-2` 键不存在 |
| `incr` / `decr` | `key: str`, `amount: int = 1` | `int`，操作后的值 |
| `close` | — | `None`，应用关闭时调用 |

### 使用约束

- **值类型固定为 `str`**。JSON / MessagePack 等序列化由业务层负责（`json.dumps` / `json.loads`）。
- **与 `MessageQueue` 严格分离**：列表操作（`lpush` / `brpop` 等）属于 `MessageQueue`，不得混入 `CacheStore`。
- TTL 语义以秒为单位；需要毫秒精度请在 Protocol 外单独扩展。

---

## 使用示例

```python
# 缓存读写
cached = await rt.cache.get(f"user:{user_id}")
if cached:
    return json.loads(cached)
await rt.cache.set(f"user:{user_id}", json.dumps(profile), ex=3600)

# 滑动窗口限流
count = await rt.cache.incr(f"rate:{user_id}")
if count == 1:
    await rt.cache.expire(f"rate:{user_id}", 60)
if count > 100:
    raise Match3Exception.of_code(codes.RATE_LIMITED, "rate limit exceeded") \
        .ctx(user_id=user_id, window_sec=60)
```

---

## 关联文档

- [implementation.md](./implementation.md) — Redis 适配器
- [versions/redis-v8.6.2.md](./versions/redis-v8.6.2.md) — redis-py 5.3 接口速查
- [../message-queue/protocol.md](../message-queue/protocol.md) — 与 MessageQueue 的职责边界
- [../config.md](../config.md) — `runtime.cache_store.*` 配置
