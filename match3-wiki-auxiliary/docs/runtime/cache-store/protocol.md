# CacheStore Protocol

> **功能**: 会话缓存、计数器、限流、分布式锁  
> **推荐实现**: Redis v8.6.2 (2026-03-24)  
> **Runtime 接口**: `rt.cache: CacheStore` (Protocol)

## 📚 相关文档

- **上级文档**: [runtime.md](../runtime.md) - Runtime 系统总览和 Protocol 设计理念
- **实现方案**: [implementation.md](./implementation.md) - Redis 适配器实现和配置说明
- **版本技术文档**: [versions/](./versions/) - 具体实现库的详细 API 文档
  - [Redis v8.6.2](./versions/redis-v8.6.2.md) - 推荐实现

---

## Protocol 定义

### 接口说明

`CacheStore` 提供键值存储能力,用于:
- **会话缓存**: 用户会话数据临时存储
- **计数器**: 原子递增/递减操作
- **限流**: 基于令牌桶/滑动窗口的速率限制
- **分布式锁**: (需要额外实现 `DistributedLock` Protocol)

### 代码定义

```python
from typing import Protocol

class CacheStore(Protocol):
    """缓存存储抽象接口
    
    不依赖任何缓存库 (redis-py、memcached等),仅使用 Python 标准库类型。
    """
    
    async def get(self, key: str) -> str | None:
        """获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值,不存在则返回 None
        """
        ...
    
    async def set(
        self,
        key: str,
        value: str | int | float,
        ex: int | None = None,
    ) -> bool:
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ex: 过期时间 (秒),None 表示永不过期
            
        Returns:
            是否设置成功
        """
        ...
    
    async def delete(self, *keys: str) -> int:
        """删除缓存键
        
        Args:
            keys: 要删除的键列表
            
        Returns:
            实际删除的键数量
        """
        ...
    
    async def exists(self, *keys: str) -> int:
        """检查键是否存在
        
        Args:
            keys: 要检查的键列表
            
        Returns:
            存在的键数量
        """
        ...
    
    async def expire(self, key: str, seconds: int) -> bool:
        """设置键的过期时间
        
        Args:
            key: 缓存键
            seconds: 过期秒数
            
        Returns:
            是否设置成功
        """
        ...
    
    async def ttl(self, key: str) -> int:
        """获取键的剩余生存时间
        
        Args:
            key: 缓存键
            
        Returns:
            剩余秒数,-1 表示永不过期,-2 表示键不存在
        """
        ...
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """原子递增
        
        Args:
            key: 缓存键
            amount: 递增量
            
        Returns:
            递增后的值
        """
        ...
    
    async def close(self) -> None:
        """关闭连接,释放资源"""
        ...
```

---

## 使用示例

### 业务代码 (缓存模式)

```python
import json
from runtime import Runtime

async def get_user_profile(rt: Runtime, user_id: int) -> dict | None:
    """获取用户信息 (带缓存)
    
    业务代码不知道底层是 Redis 还是其他缓存系统。
    """
    cache_key = f"user:{user_id}"
    
    # 尝试从缓存读取
    cached = await rt.cache.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 从数据库读取
    profile = await fetch_from_database(user_id)
    
    # 写入缓存 (1小时过期)
    await rt.cache.set(
        cache_key,
        json.dumps(profile),
        ex=3600,
    )
    
    return profile
```

### 业务代码 (限流模式)

```python
from runtime import Runtime

async def check_rate_limit(
    rt: Runtime,
    user_id: int,
    max_requests: int = 100,
    window_seconds: int = 60,
) -> bool:
    """检查用户是否超出速率限制"""
    key = f"rate_limit:{user_id}"
    
    # 原子递增
    count = await rt.cache.incr(key)
    
    # 第一次访问,设置过期时间
    if count == 1:
        await rt.cache.expire(key, window_seconds)
    
    return count <= max_requests
```

### 单元测试

```python
from unittest.mock import AsyncMock
from runtime import Runtime

async def test_get_user_profile():
    """测试用户信息获取 (使用 Mock 缓存)"""
    # Mock 缓存
    mock_cache = AsyncMock()
    mock_cache.get.return_value = '{"name": "Alice", "age": 30}'
    
    # 创建测试 Runtime
    rt = Runtime(
        cache=mock_cache,
        queue=AsyncMock(),
        vector_db=AsyncMock(),
        graph_db=AsyncMock(),
        db=AsyncMock(),
        search=AsyncMock(),
        storage=AsyncMock(),
    )
    
    # 测试
    profile = await get_user_profile(rt, user_id=123)
    
    assert profile == {"name": "Alice", "age": 30}
    mock_cache.get.assert_called_once_with("user:123")
```

---

## 设计说明

### 抽象粒度

✅ **好的抽象**: `get(key: str) -> str | None` (通用)  
❌ **过度抽象**: `get(key: redis.Key) -> redis.Value` (依赖具体库)

### 同步 vs 异步

推荐使用异步版本:

```python
class CacheStore(Protocol):
    async def get(self, key: str) -> str | None: ...  # ✅ 异步
```

**理由**:
- FastAPI 是异步框架
- 避免阻塞事件循环
- 更高的并发性能

### 数据类型支持

当前 Protocol 只暴露最常用的操作 (String 类型)。

如需支持更多数据类型 (Hash、List、Set),可以:

**方案 1: 扩展 Protocol**

```python
class CacheStore(Protocol):
    # String 操作
    async def get(self, key: str) -> str | None: ...
    
    # Hash 操作
    async def hget(self, key: str, field: str) -> str | None: ...
    async def hset(self, key: str, field: str, value: str) -> bool: ...
    
    # List 操作 (注意: 与 MessageQueue 分离)
    async def lpush(self, key: str, *values: str) -> int: ...
```

**方案 2: 分离 Protocol**

```python
class StringOperations(Protocol): ...
class HashOperations(Protocol): ...
class ListOperations(Protocol): ...

class CacheStore(StringOperations, HashOperations, ListOperations, Protocol):
    pass
```

### 序列化

Protocol 接口使用 `str` 类型,序列化由业务层负责:

```python
# 业务层序列化
await rt.cache.set("key", json.dumps(data))

# 业务层反序列化
data = json.loads(await rt.cache.get("key"))
```

**理由**:
- 保持接口简单
- 业务层可以选择序列化方式 (JSON/MessagePack/Pickle)

### 与 MessageQueue 的关系

**CacheStore 和 MessageQueue 是独立的抽象**:

- `rt.cache`: 键值存储 (单值操作)
  - `get()` / `set()` / `delete()` / `incr()`
  - 用途: 缓存、会话、计数器、限流

- `rt.queue`: 消息队列 (列表操作)
  - `lpush()` / `rpop()` / `brpop()`
  - 用途: 任务队列、Celery Broker、异步通信

虽然底层实现可能都是 Redis,但它们提供不同的能力,职责分离 (SRP)。

---

## 扩展性

### 切换到其他缓存系统

可以切换到 Memcached、Valkey、KeyDB,只需实现 `CacheStore` Protocol:

```python
from aiomcache import Client

class MemcachedAdapter:
    """Memcached 适配器 (实现 CacheStore Protocol)"""
    
    def __init__(self, client: Client):
        self._client = client
    
    async def get(self, key: str) -> str | None:
        result = await self._client.get(key.encode())
        return result.decode() if result else None
    
    async def set(
        self,
        key: str,
        value: str | int | float,
        ex: int | None = None,
    ) -> bool:
        exptime = ex if ex is not None else 0
        return await self._client.set(
            key.encode(),
            str(value).encode(),
            exptime=exptime,
        )
    
    # ... 其他方法类似
```

**无需修改 Runtime 或业务代码！**

### 支持发布/订阅

如果需要支持 Pub/Sub,可以定义扩展 Protocol:

```python
from typing import Protocol, AsyncIterator, runtime_checkable

@runtime_checkable
class PubSubMessaging(Protocol):
    """发布/订阅接口 (可选能力)"""
    
    async def publish(self, channel: str, message: str) -> int:
        """发布消息
        
        Returns:
            收到消息的订阅者数量
        """
        ...
    
    async def subscribe(self, *channels: str) -> AsyncIterator[tuple[str, str]]:
        """订阅频道
        
        Yields:
            (channel, message) 元组
        """
        ...
```

使用时检查是否支持:

```python
from typing import runtime_checkable

if isinstance(rt.cache, PubSubMessaging):
    await rt.cache.publish("notifications", "New message!")
else:
    # 降级到其他通知方式
    pass
```

---

**创建时间**: 2026-04-23  
**最后更新**: 2026-04-23  
**版本**: 3.0
