# Bolt 协议

**Bolt** 是 Neo4j 专为图数据库设计的二进制客户端-服务器通信协议，默认端口 7687。相比 HTTP/REST，Bolt 传输效率更高、延迟更低，是所有官方 Neo4j 驱动（Python、Java、JavaScript 等）的底层通信协议。

## 主要特性

- **二进制编码**：使用 PackStream 序列化格式，比 JSON 更紧凑
- **双向流式**：支持服务器流式推送结果，无需等待完整结果集再返回
- **连接池**：驱动内置连接池，多次查询复用同一 TCP 连接，避免握手开销
- **认证**：支持用户名/密码认证，传输层可配置 TLS 加密

## URI 格式

```python
# Standard Bolt connection (no encryption)
uri = "bolt://localhost:7687"

# Bolt with TLS (required in production)
uri = "bolt+s://neo4j.example.com:7687"

# Neo4j cluster with routing (bolt+routing)
uri = "neo4j://localhost:7687"
```

## Python 驱动中的连接配置

```python
from neo4j import AsyncGraphDatabase

driver = AsyncGraphDatabase.driver(
    uri="bolt://localhost:7687",
    auth=("neo4j", password),
    max_connection_pool_size=50,
    connection_timeout=5.0,   # seconds to wait for connection
)
```

连接池由驱动自动管理，`async with driver.session() as session` 从池中取连接，用完后归还，不需要手动关闭单个连接。

## 与 HTTP API 的对比

| 特性 | Bolt | HTTP API |
|------|------|----------|
| 性能 | 高（二进制，流式） | 低（文本，请求-响应） |
| 连接复用 | ✓ 连接池 | 需手动管理 |
| 官方驱动支持 | ✓ | ✓ |
| 适用场景 | 业务代码 | 调试、外部工具 |

本项目通过 Neo4j Python 异步驱动（`neo4j` 包）使用 Bolt 协议，业务代码感知不到协议细节。
