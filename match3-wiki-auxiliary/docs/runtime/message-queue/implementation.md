# 消息队列实现方案

> **实现**: Redis v8.6.2 (Celery Broker/Backend)  
> **Python 客户端**: redis-py v5.3.0  
> **Protocol**: `MessageQueue` (见 [protocol.md](./protocol.md))

## 📚 相关文档

- **Protocol 定义**: [protocol.md](./protocol.md) - 抽象接口定义
- **Redis 技术文档**: [versions/redis-v8.6.2.md](./versions/redis-v8.6.2.md) - Redis API 详细说明

---

## Runtime 集成

### Redis 连接配置

```python
# app/runtime.py
from redis import Redis

def build_runtime(config: Config, env: Env, logger: Logger) -> Match3Runtime:
    """构建 Runtime 实例"""
    
    redis_client = Redis.from_url(
        env.REDIS_BROKER_URL,
        max_connections=config.runtime.message_queue.implementations.redis.max_connections,
        socket_timeout=config.runtime.message_queue.implementations.redis.socket_timeout,
        decode_responses=True,
    )
    
    logger.info("Redis broker client initialized")
    
    return Match3Runtime(
        redis=redis_client,
        # ... 其他组件
    )
```

### Celery 应用配置

```python
# app/workers/celery_app.py
from celery import Celery
from app.config.config import Config
from app.config.env import Env

config = Config.load_from_yaml("config.yaml")
env = Env()

celery_app = Celery(
    "match3_wiki_tasks",
    broker=env.CELERY_BROKER_URL,
    backend=env.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=config.celery.task_time_limit,
    task_soft_time_limit=config.celery.task_soft_time_limit,
    worker_prefetch_multiplier=config.celery.worker_prefetch_multiplier,
    worker_max_tasks_per_child=1000,
)
```

## 配置说明

### 环境变量配置 (`.env`)

```bash
# 消息队列
REDIS_BROKER_URL=redis://localhost:6379/1
REDIS_RESULT_URL=redis://localhost:6379/2
```

### 配置文件 (`config.yaml`)

```yaml
redis:
  max_connections: 50
  socket_timeout: 5
  socket_connect_timeout: 5

celery:
  task_time_limit: 3600          # 任务硬超时（秒）
  task_soft_time_limit: 3000     # 任务软超时（秒）
  worker_concurrency: 4          # Worker 并发数
  worker_prefetch_multiplier: 2  # 预取任务倍数
```

## 配置类

```python
# app/config/config.py

class RedisConfig:
    """Redis 配置"""
    
    def __init__(self, data: dict):
        self.max_connections = self._require(data, "max_connections")
        self.socket_timeout = self._require(data, "socket_timeout")
        self.socket_connect_timeout = self._require(data, "socket_connect_timeout")

class CeleryConfig:
    """Celery 配置"""
    
    def __init__(self, data: dict):
        self.task_time_limit = self._require(data, "task_time_limit")
        self.task_soft_time_limit = self._require(data, "task_soft_time_limit")
        self.worker_concurrency = self._require(data, "worker_concurrency")
        self.worker_prefetch_multiplier = self._require(data, "worker_prefetch_multiplier")
```

---

**创建时间**：2026-04-23  
**版本**：2.0
