# Logger Protocol

> **功能**: 结构化日志记录  
> **推荐实现**: Loguru v0.7.3 (2025-03-15)  
> **Runtime 接口**: `rt.logger: Logger` (Protocol)

## 📚 相关文档

- **上级文档**: [runtime.md](../runtime.md) - Runtime 系统总览和 Protocol 设计理念
- **实现方案**: [implementation.md](./implementation.md) - Loguru 适配器实现和配置说明
- **版本技术文档**: [versions/](./versions/) - 具体实现库的详细 API 文档

---

## Protocol 定义

### 接口说明

`Logger` 提供统一日志记录能力,用于:
- **应用日志**: 记录应用运行状态和关键事件
- **调试信息**: 记录调试级别的详细信息
- **异常跟踪**: 记录异常堆栈信息
- **结构化日志**: 支持结构化字段的日志记录

### 代码定义

```python
from typing import Protocol, Any

class Logger(Protocol):
    """日志记录器抽象接口
    
    不依赖任何日志库 (loguru、logging等),仅使用 Python 标准库类型。
    """
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """记录调试信息
        
        Args:
            message: 日志消息
            **kwargs: 结构化字段 (可选)
        """
        ...
    
    def info(self, message: str, **kwargs: Any) -> None:
        """记录一般信息
        
        Args:
            message: 日志消息
            **kwargs: 结构化字段 (可选)
        """
        ...
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """记录警告信息
        
        Args:
            message: 日志消息
            **kwargs: 结构化字段 (可选)
        """
        ...
    
    def error(self, message: str, **kwargs: Any) -> None:
        """记录错误信息
        
        Args:
            message: 日志消息
            **kwargs: 结构化字段 (可选)
        """
        ...
    
    def critical(self, message: str, **kwargs: Any) -> None:
        """记录严重错误信息
        
        Args:
            message: 日志消息
            **kwargs: 结构化字段 (可选)
        """
        ...
    
    def exception(self, message: str, **kwargs: Any) -> None:
        """记录异常信息 (带堆栈跟踪)
        
        Args:
            message: 日志消息
            **kwargs: 结构化字段 (可选)
        """
        ...
```

---

## 使用示例

### 业务代码 (基本日志)

```python
from runtime import Runtime

def process_document(rt: Runtime, doc_id: int) -> None:
    """处理文档 (使用统一的日志接口)"""
    
    rt.logger.info(f"Processing document {doc_id}")
    
    try:
        # 处理逻辑
        rt.logger.debug(f"Document {doc_id} processed successfully")
    except Exception as e:
        rt.logger.error(f"Failed to process document {doc_id}: {e}")
        rt.logger.exception("Exception details")
        raise
```

### 业务代码 (结构化日志)

```python
def ingest_page(rt: Runtime, page_url: str, workspace_id: int) -> None:
    """摄取页面 (使用结构化日志)"""
    
    rt.logger.info(
        "Ingesting page",
        page_url=page_url,
        workspace_id=workspace_id,
        timestamp=time.time(),
    )
```

### 单元测试

```python
from unittest.mock import MagicMock
from runtime import Runtime

def test_process_document():
    """测试文档处理 (Mock 日志)"""
    
    # Mock 日志记录器
    mock_logger = MagicMock()
    
    # 创建测试 Runtime
    rt = Runtime(
        logger=mock_logger,
        cache=MagicMock(),
        queue=MagicMock(),
        vector_db=MagicMock(),
        graph_db=MagicMock(),
        db=MagicMock(),
        search=MagicMock(),
        storage=MagicMock(),
    )
    
    # 测试
    process_document(rt, doc_id=123)
    
    # 验证日志调用
    mock_logger.info.assert_called_with("Processing document 123")
```

---

## 设计说明

### 日志级别

推荐的日志级别使用场景:

| 级别 | 用途 | 示例 |
|------|------|------|
| `debug` | 调试信息 | 变量值、函数调用 |
| `info` | 一般信息 | 业务流程节点 |
| `warning` | 警告信息 | 非致命问题、降级行为 |
| `error` | 错误信息 | 可恢复的错误 |
| `critical` | 严重错误 | 系统崩溃、不可恢复 |
| `exception` | 异常信息 | 捕获异常的堆栈 |

### 结构化日志

推荐使用 kwargs 传递结构化字段:

```python
# ✅ 好的做法 (结构化)
rt.logger.info(
    "User login",
    user_id=123,
    ip="192.168.1.1",
    timestamp=time.time(),
)

# ❌ 避免的做法 (字符串拼接)
rt.logger.info(f"User {user_id} login from {ip} at {timestamp}")
```

**优势**:
- 易于查询和过滤
- 支持日志聚合和分析
- 便于结构化存储 (如 JSON 格式)

### 异步日志

Loguru 默认支持异步写入,不会阻塞业务逻辑。

如果需要显式异步接口:

```python
class Logger(Protocol):
    async def info(self, message: str, **kwargs: Any) -> None: ...
```

但这会增加业务代码的复杂度,通常不必要。

### 敏感信息保护

**注意**: 不要在日志中记录敏感信息 (密码、Token、API Key 等)

```python
# ❌ 危险: 记录密码
rt.logger.info(f"User login with password: {password}")

# ✅ 安全: 只记录非敏感信息
rt.logger.info("User login", user_id=user_id)
```

---

## 扩展性

### 切换到标准库 logging

```python
import logging

class StdLoggingAdapter:
    """标准库 logging 适配器 (实现 Logger Protocol)"""
    
    def __init__(self, logger: logging.Logger):
        self._logger = logger
    
    def info(self, message: str, **kwargs: Any) -> None:
        extra = {"structured": kwargs} if kwargs else {}
        self._logger.info(message, extra=extra)
    
    def error(self, message: str, **kwargs: Any) -> None:
        extra = {"structured": kwargs} if kwargs else {}
        self._logger.error(message, extra=extra)
    
    # ... 其他方法类似
```

**无需修改 Runtime 或业务代码！**

### 支持日志上下文

如果需要支持日志上下文 (如请求 ID):

```python
from typing import Protocol, runtime_checkable, ContextManager

@runtime_checkable
class ContextualLogger(Protocol):
    """支持上下文的日志记录器 (可选)"""
    
    def bind(self, **kwargs: Any) -> ContextManager["Logger"]:
        """绑定上下文字段
        
        Returns:
            绑定了上下文的日志记录器
        """
        ...
```

使用时:

```python
with rt.logger.bind(request_id=request_id) as logger:
    logger.info("Processing request")  # 自动包含 request_id
```

---

**创建时间**: 2026-04-23  
**最后更新**: 2026-04-23  
**版本**: 2.0
