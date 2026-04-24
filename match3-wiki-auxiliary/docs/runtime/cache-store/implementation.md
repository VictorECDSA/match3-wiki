# 缓存存储实现方案

> **实现**: Redis v8.6.2  
> **Python 客户端**: redis-py v5.3.0 (异步支持)  
> **Protocol**: `CacheStore` (见 [protocol.md](./protocol.md))

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
        env.REDIS_CACHE_URL,
        max_connections=config.runtime.cache_store.implementations.redis.max_connections,
        socket_timeout=config.runtime.cache_store.implementations.redis.socket_timeout,
        decode_responses=True,
    )
    
    logger.info("Redis cache client initialized")
    
    return Match3Runtime(
        cache=redis_client,
        # ... 其他组件
    )
```

## 配置说明

### 环境变量配置 (`.env`)

```bash
# 缓存
REDIS_CACHE_URL=redis://localhost:6379/0
```

### 配置文件 (`config.yaml`)

```yaml
runtime:
  cache_store:
    provider: redis
    implementations:
      redis:
        max_connections: 50
        socket_timeout: 5
```

---

**创建时间**：2026-04-23  
**版本**：2.0
