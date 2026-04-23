# MessageQueue Protocol

> **功能**: Celery Broker/Result Backend、任务队列  
> **推荐实现**: Redis v8.4.2 (2026-04-19)  
> **Runtime 接口**: `rt.queue: MessageQueue` (Protocol)

## 📚 相关文档

- **上级文档**: [runtime.md](../runtime.md) - Runtime 系统总览和 Protocol 设计理念
- **实现方案**: [implementation.md](./implementation.md) - Redis 适配器实现和配置说明
- **版本技术文档**: [versions/](./versions/) - 具体实现库的详细 API 文档
  - [Redis v8.6.2](./versions/redis-v8.6.2.md) - 推荐实现 (与 cache-store 共用)

---

## Protocol 定义

### 接口说明

`MessageQueue` 提供消息队列能力,用于:
- **Celery Broker**: Celery 任务分发
- **Result Backend**: Celery 任务结果存储
- **任务队列**: 异步任务排队处理
- **事件总线**: 应用内异步通信

### 代码定义

```python
from typing import Protocol

class MessageQueue(Protocol):
    """消息队列抽象接口 (用于 Celery Broker)
    
    不依赖任何消息队列库 (redis-py、rabbitmq等),仅使用 Python 标准库类型。
    """
    
    async def lpush(self, key: str, *values: str) -> int:
        """从左侧推入列表
        
        Args:
            key: 队列键
            values: 要推入的消息列表
            
        Returns:
            推入后的列表长度
        """
        ...
    
    async def rpush(self, key: str, *values: str) -> int:
        """从右侧推入列表
        
        Args:
            key: 队列键
            values: 要推入的消息列表
            
        Returns:
            推入后的列表长度
        """
        ...
    
    async def lpop(self, key: str) -> str | None:
        """从左侧弹出
        
        Args:
            key: 队列键
            
        Returns:
            弹出的消息,队列为空则返回 None
        """
        ...
    
    async def rpop(self, key: str) -> str | None:
        """从右侧弹出
        
        Args:
            key: 队列键
            
        Returns:
            弹出的消息,队列为空则返回 None
        """
        ...
    
    async def brpop(self, keys: list[str], timeout: int = 0) -> tuple[str, str] | None:
        """阻塞式从右侧弹出
        
        Args:
            keys: 键列表 (按优先级顺序)
            timeout: 超时时间 (秒),0 表示永不超时
            
        Returns:
            (key, value) 元组,超时则返回 None
        """
        ...
    
    async def close(self) -> None:
        """关闭连接"""
        ...
```

---

## 使用示例

### 业务代码 (任务队列)

```python
import json
from runtime import Runtime

async def enqueue_task(rt: Runtime, task_name: str, args: list, kwargs: dict) -> None:
    """将任务加入队列"""
    
    task_data = json.dumps({
        "task": task_name,
        "args": args,
        "kwargs": kwargs,
        "timestamp": time.time(),
    })
    
    # 推入任务队列
    await rt.queue.rpush("celery", task_data)


async def dequeue_task(rt: Runtime) -> dict | None:
    """从队列中取出任务 (阻塞模式)"""
    
    result = await rt.queue.brpop(["celery"], timeout=5)
    if result:
        _, task_data = result
        return json.loads(task_data)
    return None
```

### Celery 集成

Celery 需要 Redis 作为 Broker 和 Result Backend:

```python
# Celery 配置中使用 Redis URL
CELERY_BROKER_URL = "redis://localhost:6379/1"
CELERY_RESULT_BACKEND = "redis://localhost:6379/2"
```

Runtime 的 `queue` 成员主要用于自定义消息队列逻辑,不直接用于 Celery 配置。

### 单元测试

```python
from unittest.mock import AsyncMock
from runtime import Runtime

async def test_enqueue_task():
    # Mock 队列
    mock_queue = AsyncMock()
    mock_queue.rpush.return_value = 1
    
    # 创建测试 Runtime
    rt = Runtime(
        cache=AsyncMock(),
        queue=mock_queue,
        vector_db=AsyncMock(),
        graph_db=AsyncMock(),
        db=AsyncMock(),
        search=AsyncMock(),
        storage=AsyncMock(),
    )
    
    # 测试
    await enqueue_task(rt, "process_video", ["/tmp/video.mp4"], {})
    
    # 验证
    mock_queue.rpush.assert_called_once()
    args = mock_queue.rpush.call_args[0]
    assert args[0] == "celery"
    assert "process_video" in args[1]
```

---

## 设计说明

### 与 CacheStore 的区别

**CacheStore 和 MessageQueue 是独立的抽象**:
- `rt.cache` 用于缓存、会话、计数器 (单值操作)
- `rt.queue` 用于消息队列、任务队列 (列表操作)

虽然底层实现可能都是 Redis,但它们提供不同的接口和语义。

### 队列顺序

Redis List 的不同操作组合产生不同的队列模式:
- **FIFO 队列**: `rpush` + `lpop` 或 `lpush` + `rpop`
- **LIFO 栈**: `rpush` + `rpop` 或 `lpush` + `lpop`

Celery 默认使用 FIFO 模式。

### 阻塞 vs 非阻塞

- **非阻塞**: `lpop()` / `rpop()` — 立即返回,队列为空则返回 `None`
- **阻塞**: `brpop()` — 等待直到有消息或超时

阻塞模式更适合长轮询的 Worker。

### 持久化

Redis 的 List 数据会受到持久化策略影响:
- **RDB**: 定期快照
- **AOF**: 每个写操作记录日志

确保 Redis 配置了合适的持久化策略,避免消息丢失。

---

## 扩展性

### 切换到 RabbitMQ

```python
import aio_pika

class RabbitMQAdapter:
    """RabbitMQ 适配器 (实现 MessageQueue Protocol)"""
    
    def __init__(self, connection: aio_pika.Connection, queue_name: str):
        self._connection = connection
        self._queue_name = queue_name
    
    async def rpush(self, key: str, *values: str) -> int:
        """推送消息到队列"""
        channel = await self._connection.channel()
        queue = await channel.declare_queue(self._queue_name, durable=True)
        
        for value in values:
            await channel.default_exchange.publish(
                aio_pika.Message(body=value.encode()),
                routing_key=self._queue_name,
            )
        
        return await queue.get_queue_size()
    
    async def brpop(self, keys: list[str], timeout: int = 0) -> tuple[str, str] | None:
        """从队列消费消息"""
        channel = await self._connection.channel()
        queue = await channel.declare_queue(self._queue_name, durable=True)
        
        try:
            message = await asyncio.wait_for(
                queue.get(timeout=timeout if timeout > 0 else None),
                timeout=timeout if timeout > 0 else None,
            )
            await message.ack()
            return (self._queue_name, message.body.decode())
        except asyncio.TimeoutError:
            return None
    
    # ... 其他方法类似
```

**无需修改 Runtime 或业务代码！**

---

**创建时间**: 2026-04-23  
**最后更新**: 2026-04-23  
**版本**: 2.0
