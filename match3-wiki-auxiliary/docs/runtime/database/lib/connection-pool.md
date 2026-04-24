# 连接池（Connection Pool）

**连接池（Connection Pool）** 是数据库客户端维护的一组预建数据库连接的集合。每次执行数据库操作时从池中取一个空闲连接，操作完成后归还，而不是每次都新建和销毁 TCP 连接，从而消除重复握手的开销。

## 为什么需要连接池

建立一条 PostgreSQL 连接需要：TCP 三次握手 + PostgreSQL 认证协议 + 连接初始化，耗时约 10–50ms。若每次查询都新建连接，一次 HTTP 请求（含数次数据库操作）可能额外增加数百毫秒延迟。

## SQLAlchemy 连接池参数

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    url=database_url,
    pool_size=10,          # number of persistent connections in the pool
    max_overflow=20,       # extra connections allowed when pool is full (temporary)
    pool_timeout=30,       # seconds to wait for a connection before raising error
    pool_pre_ping=True,    # execute "SELECT 1" before using a connection (detect stale connections)
    pool_recycle=3600,     # recycle connections after 1 hour (avoid server-side timeout)
)
```

## 关键参数说明

| 参数 | 含义 | 推荐值 |
|------|------|--------|
| `pool_size` | 池中常驻连接数 | CPU 核心数 × 2，本项目取 10 |
| `max_overflow` | 峰值时允许额外创建的连接数 | `pool_size` × 2 |
| `pool_timeout` | 等待超时（秒），超时则抛 `TimeoutError` | 30 |
| `pool_pre_ping` | 使用前健康检查，自动回收失效连接 | `True`（必须开启） |
| `pool_recycle` | 连接最大存活时间（秒），防止服务端超时断连 | 3600 |

## 异步场景的特殊说明

SQLAlchemy 异步引擎（`AsyncEngine`）的连接池是基于协程的：一个协程持有连接时，其他协程可以并发运行，不会阻塞线程。但每个并发数据库操作仍需占用一个连接槽，`pool_size + max_overflow` 决定最大并发数据库操作数。

若并发操作超出连接池上限，多余的请求会等待最长 `pool_timeout` 秒，超时后抛出异常，需在配置中根据实际并发量调整。
