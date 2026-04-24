# Celery 任务队列基础概念

message-queue 组件使用 Redis 作为 Celery 的消息代理（Broker），将异步任务的工作项存储为 Redis List，由 Celery Worker 消费执行。本目录中的 Redis 专项概念（TTL、Pipeline、Pub/Sub 等）与缓存层共用同一个 Redis 实例，但使用不同的键前缀和 Database 编号隔离。

## 相关概念索引

以下 Redis 核心概念对消息队列场景同样适用，详见 cache-store 的对应文档：

| 概念 | 说明 | 文档 |
|------|------|------|
| TTL | 任务结果的自动过期清理 | [../../cache-store/lib/TTL.md](../../cache-store/lib/TTL.md) |
| Pipeline | Celery 批量确认时的命令批处理 | [../../cache-store/lib/pipeline.md](../../cache-store/lib/pipeline.md) |
| Pub/Sub | 任务状态实时推送（可选扩展） | [../../cache-store/lib/pub-sub.md](../../cache-store/lib/pub-sub.md) |

## Celery 特有的消息队列概念

### 队列（Queue）

Celery 通过 Redis List 实现队列，每个队列对应一个 Redis Key（如 `celery:ingest`、`celery:embed`）。Worker 启动时绑定到特定队列：

```python
# Worker listening on ingest and embed queues
celery -A app worker -Q ingest,embed --concurrency=4
```

### 任务路由（Task Routing）

```python
# In Celery config: route each task type to its dedicated queue
task_routes = {
    "workers.ingestion.ingest_task": {"queue": "ingest"},
    "workers.ingestion.embed_task":  {"queue": "embed"},
    "workers.ingestion.graph_task":  {"queue": "graph"},
    "workers.wiki.compile_task":     {"queue": "compile"},
}
```

### 结果后端（Result Backend）

Celery 将任务执行结果（成功 / 失败 / 返回值）序列化后写入 Redis，键为 `celery-task-meta-{task_id}`，默认 TTL 为 86400 秒（1 天）：

```python
result = ingest_task.delay(raw_file_id)
task_id = result.id           # used to poll status
status = result.status        # PENDING | STARTED | SUCCESS | FAILURE | RETRY
```

### 重试策略（Retry Policy）

```python
@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,   # seconds between retries
    autoretry_for=(Exception,),
)
def ingest_task(self, raw_file_id: str):
    ...
```

详细配置见 [../../design/solution-final/060-workers/celery-tasks.md](../../design/solution-final/060-workers/celery-tasks.md)。
