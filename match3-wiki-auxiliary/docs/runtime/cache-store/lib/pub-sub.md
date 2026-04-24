# Pub/Sub（发布订阅）

**Pub/Sub（Publish/Subscribe，发布/订阅）** 是 Redis 提供的消息传递模式：发布者（Publisher）向频道（Channel）发送消息，所有订阅该频道的订阅者（Subscriber）都会实时收到，发布者与订阅者完全解耦，互不知晓对方身份。

## 工作模式

```
Publisher                Channel              Subscriber(s)
    |                      |                       |
    |--- PUBLISH msg -----> |                       |
    |                      |--- push msg ---------> | (Subscriber A)
    |                      |--- push msg ---------> | (Subscriber B)
```

## 基本命令

```python
# Subscriber side: subscribe to a channel (blocking)
async def listen_to_channel():
    async with redis.pubsub() as pubsub:
        await pubsub.subscribe("events:ingest-done")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                print(f"Received: {data}")

# Publisher side: publish a message
await redis.publish("events:ingest-done", json.dumps({"raw_file_id": "..."}))
```

## 模式订阅（Pattern Subscribe）

使用通配符一次订阅多个频道：

```python
await pubsub.psubscribe("events:*")   # subscribe to all channels starting with "events:"
```

## Pub/Sub 的局限性

| 局限 | 说明 |
|------|------|
| 无持久化 | 消息只传给当前在线的订阅者，离线期间的消息丢失 |
| 无确认机制 | 发布者不知道消息是否被处理 |
| 无重试 | 消费失败无法重新投递 |

## 与 Celery 任务队列的对比

本项目的异步任务（导入、嵌入、图谱抽取）使用 Celery + Redis List 队列（见 [message-queue](../../message-queue/)），而非 Pub/Sub。原因：Celery 队列有持久化、重试、任务状态追踪，更可靠；Pub/Sub 适合实时通知（如前端 WebSocket 事件推送），不适合关键业务流程。
