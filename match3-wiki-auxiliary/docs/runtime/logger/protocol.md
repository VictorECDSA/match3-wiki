# Logger Protocol

Logger provides abstract logging interface for application-wide logging.

---

## 📋 Protocol 定义

```python
# anim-core/anim_core/runtime/dependencies/logger/logger.py
from typing import Protocol, Any

class Logger(Protocol):
    """Logger Protocol interface"""
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message"""
        ...
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message"""
        ...
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message"""
        ...
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message"""
        ...
    
    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message"""
        ...
    
    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback"""
        ...
```

---

## 🎯 核心能力

| 方法        | 功能                   |
|-----------|----------------------|
| `debug`   | 记录调试信息              |
| `info`    | 记录一般信息              |
| `warning` | 记录警告信息              |
| `error`   | 记录错误信息              |
| `critical` | 记录严重错误信息            |
| `exception` | 记录异常信息（带 traceback） |

---

## 📦 Config 结构

```python
class LogConfig:
    """Logger configuration"""
    
    def __init__(
        self,
        level: str = "INFO",
        format: str = "json",
        rotation: str = "1 day",
        retention: str = "7 days",
        log_file: Optional[str] = None
    ):
        self.level = level
        self.format = format
        self.rotation = rotation
        self.retention = retention
        self.log_file = log_file
```

---

## 🔧 使用示例

### 1. 从 Runtime 获取 Logger

```python
def process_document(rt: Match3Runtime, doc_id: int):
    """Process document with logging"""
    rt.logger.info(f"Processing document {doc_id}")
    
    try:
        # ... processing logic
        rt.logger.debug(f"Document {doc_id} processed successfully")
    except Exception as e:
        rt.logger.error(f"Failed to process document {doc_id}: {e}")
        rt.logger.exception("Exception details")
```

### 2. 记录结构化日志

```python
def ingest_page(rt: Match3Runtime, page_url: str):
    """Ingest page with structured logging"""
    rt.logger.info(
        "Ingesting page",
        page_url=page_url,
        workspace_id=123,
    )
```

---

## 🏗️ 设计原则

1. **Protocol 接口**: Logger 是 Protocol，不依赖具体实现（与其他 Runtime 组件一致）
2. **简单易用**: 提供标准日志级别方法
3. **可测试**: 可以用 Mock 替换进行单元测试
4. **统一入口**: 所有组件通过 `rt.logger` 访问日志
5. **零依赖**: Logger Protocol 不依赖任何第三方日志库

---

## 📝 注意事项

1. **不要直接创建 Logger**: Logger 应该通过 `build_runtime()` 构建
2. **统一日志格式**: 使用 config.yaml 配置统一的日志格式
3. **避免敏感信息**: 不要在日志中记录密码、token 等敏感信息
4. **使用结构化日志**: 优先使用 kwargs 记录结构化信息
