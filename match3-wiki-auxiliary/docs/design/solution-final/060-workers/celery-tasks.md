# Celery Workers — 总览

## 队列布局

| 队列 | Worker 文件 | 并发 | 描述 |
|------|------------|------|------|
| `ingest` | [ingestion/ingest-task.md](ingestion/ingest-task.md) | 4 | 文件解析、分块、写入 PostgreSQL |
| `embed` | [ingestion/embed-task.md](ingestion/embed-task.md) | 4 | 嵌入生成、Milvus upsert、ES 索引 |
| `graph` | [ingestion/graph-task.md](ingestion/graph-task.md) | 2 | Neo4j 实体提取与图写入 |
| `compile` | [wiki/compile-task.md](wiki/compile-task.md) | 2 | Wiki 页面编译（LLM 密集型） |
| `rag` | [qa/rag-task.md](qa/rag-task.md) | 4 | 异步多智能体 RAG（Celery chord） |

每个队列有专属 Worker 进程，LLM 密集型的编译任务永远不会阻塞高吞吐量的导入任务。

---

## 导入流水线链式关系

```
ingest_file(raw_file_id)
    └─→ embed_chunks(raw_file_id)
            └─→ extract_graph(raw_file_id)
```

`ingest_task` 成功后通过 `chain(...).delay()` 串联后续两步。三个任务共享同一个 `raw_file_id`，各自负责不同存储系统的写入：

| 任务 | 写入目标 | 完成后状态 |
|------|---------|-----------|
| `ingest_file` | PostgreSQL `t_text_chunks` | `DONE` |
| `embed_chunks` | Milvus + Elasticsearch | `DONE` |
| `extract_graph` | Neo4j | `DONE` |

---

## Celery App 配置

```python
# app/workers/celery_app.py
# Broker/backend URL 来自 .env（敏感配置），在导入时通过 Env 读取。
# 非敏感的任务配置（重试次数、超时时间）来自 config.yaml，通过 get_runtime() 读取。
from __future__ import annotations
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

from app.common.constants import constants  # noqa: E402 — must follow load_dotenv()

celery_app = Celery(
    "match3",
    broker=os.environ["CELERY_BROKER_URL"],        # redis://…/1
    backend=os.environ["CELERY_RESULT_BACKEND"],   # redis://…/2
    include=[
        "app.workers.tasks.ingest_task",
        "app.workers.tasks.embed_task",
        "app.workers.tasks.graph_task",
        "app.workers.tasks.compile_task",
        "app.workers.tasks.rag_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,          # Worker 崩溃时任务重回队列
    worker_prefetch_multiplier=1, # 每个 Worker 槽同时只处理一个任务
    task_routes={
        "app.workers.tasks.ingest_task.*": {"queue": constants.QUEUE_INGEST},
        "app.workers.tasks.embed_task.*":  {"queue": constants.QUEUE_EMBED},
        "app.workers.tasks.graph_task.*":  {"queue": constants.QUEUE_GRAPH},
        "app.workers.tasks.compile_task.*":{"queue": constants.QUEUE_COMPILE},
        "app.workers.tasks.rag_task.*":    {"queue": constants.QUEUE_RAG},
    },
    task_default_retry_delay=10,
    task_max_retries=3,
)
```

---

## Worker 进程中的 Runtime

Worker 进程是独立 OS 进程，`Match3Runtime` 无法序列化进 Redis 队列。每个 Worker 进程在启动时重建一次自己的 Runtime：

```python
# app/workers/worker_runtime.py
from __future__ import annotations
from app.runtime import Match3Runtime, build_runtime
from app.config.config import Config
from app.config.env import Env

_runtime: Match3Runtime | None = None


def get_runtime() -> Match3Runtime:
    global _runtime
    if _runtime is None:
        config = Config.load_from_yaml()
        env = Env()
        _runtime = build_runtime(config, env)
    return _runtime
```

模块级单例在此处安全，因为每个 Celery Worker 进程只导入一次模块。

---

## 全局重试策略

| 任务 | max_retries | 重试间隔 | 硬超时 |
|------|-------------|---------|--------|
| `ingest_file` | 3 | 10 s | — |
| `embed_chunks` | 3 | 30 s | — |
| `extract_graph` | 2 | 15 s | — |
| `compile_topic` | 2 | 30 s | 300 s |
| `domain_agent_task` | 2 | 10 s | 60 s |
| `multi_agent_verify_task` | 1 | 10 s | 120 s |

`task_acks_late=True` 全局生效：Worker 崩溃时任务重回队列，不丢失。

---

## 一致性与孤儿状态处理

`t_raw_files.f_status` 是流水线的唯一真值来源。各存储操作幂等（Milvus `upsert`、ES `index by _id`、Neo4j `MERGE`、PG `ON CONFLICT DO UPDATE`），重试不会产生重复数据。

**孤儿检测**：如果 Worker 在 ACK 后、完成写入前崩溃，文件会停在中间状态（`PROCESSING`）且不会自动推进。建议部署一个周期性协调任务（每 5 分钟）：

```sql
-- 查找滞留在中间状态超过 15 分钟的文件
SELECT f_raw_file_id, f_status, f_updated_at
FROM t_raw_files
WHERE f_status IN ('PROCESSING')
  AND f_updated_at < NOW() - INTERVAL '15 minutes';
-- 对查询到的每行重新入队对应的 Celery 任务
```

---

## Worker 启动命令

```bash
# ingest + embed Worker（高吞吐量）
celery -A app.workers.celery_app worker \
  --queues=ingest,embed \
  --concurrency=4 \
  --loglevel=info \
  --hostname=worker-ingest@%h

# graph Worker（IO 密集型，较低并发即可）
celery -A app.workers.celery_app worker \
  --queues=graph \
  --concurrency=2 \
  --loglevel=info \
  --hostname=worker-graph@%h

# compile Worker（LLM 密集型，有时间限制）
celery -A app.workers.celery_app worker \
  --queues=compile \
  --concurrency=2 \
  --loglevel=info \
  --hostname=worker-compile@%h

# rag Worker
celery -A app.workers.celery_app worker \
  --queues=rag \
  --concurrency=4 \
  --loglevel=info \
  --hostname=worker-rag@%h
```
