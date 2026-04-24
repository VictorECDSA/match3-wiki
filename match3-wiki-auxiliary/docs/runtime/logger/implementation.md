# Logger Implementation — Loguru

## 概述

使用 **Loguru** 实现 `Logger` Protocol，提供结构化日志记录能力。

**⚠️ 特殊说明**: Logger 不由 Runtime 管理，应在调用 `build_runtime()` **之前**由业务层创建，然后作为参数传入。

---

## 工厂函数

```python
# backend/runtime_impl/implements/logger/logger.py
from backend.config import Config
from backend.runtime.protocols.logger import Logger, LogConfig
from .impl_loguru.loguru_logger import LoguruLogger

def create_logger(config: Config) -> Logger:
    """创建 Logger 实例 (由业务层调用，不在 build_runtime 中)
    
    Args:
        config: 配置对象
    
    Returns:
        实现了 Logger Protocol 的 LoguruLogger 实例
    """
    log_config = LogConfig(
        level=config.runtime.logger.level,
        format=config.runtime.logger.format,
        rotation=config.runtime.logger.rotation,
        retention=config.runtime.logger.retention,
        log_file="logs/match3-wiki.log"
    )
    return LoguruLogger(log_config)
```

---

## 适配器实现

```python
# backend/runtime_impl/implements/logger/impl_loguru/loguru_logger.py
import sys
from loguru import logger as loguru_logger
from backend.runtime.protocols.logger import Logger, LogConfig

class LoguruLogger:
    """Loguru 适配器，实现 Logger Protocol"""
    
    def __init__(self, config: LogConfig):
        self._logger = loguru_logger
        self._config = config
        self._configure()
    
    def _configure(self) -> None:
        """根据配置初始化 loguru"""
        # 移除默认 handler
        self._logger.remove()
        
        # 确定格式
        if self._config.format == "json":
            log_format = (
                "{"
                '"time": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
                '"level": "{level}", '
                '"message": "{message}", '
                '"file": "{file}", '
                '"line": {line}'
                "}"
            )
        else:  # text 格式
            log_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
        
        # 添加控制台 handler
        self._logger.add(
            sys.stderr,
            format=log_format,
            level=self._config.level,
            colorize=(self._config.format == "text")
        )
        
        # 添加文件 handler
        if self._config.log_file:
            self._logger.add(
                self._config.log_file,
                format=log_format,
                level=self._config.level,
                rotation=self._config.rotation,
                retention=self._config.retention,
                compression="zip"
            )
    
    def debug(self, message: str, **kwargs):
        self._logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._logger.critical(message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        self._logger.exception(message, **kwargs)
```

---

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  logger:
    level: INFO              # 日志级别: DEBUG/INFO/WARNING/ERROR
    format: json             # 格式: json/text
    rotation: 1 day          # 轮转周期
    retention: 7 days        # 保留时长
```

### 日志格式示例

**JSON 格式**:
```json
{"time": "2024-01-15 10:23:45.123", "level": "INFO", "message": "Processing document 123", "file": "processor.py", "line": 45}
```

**Text 格式**:
```
2024-01-15 10:23:45.123 | INFO     | processor:process:45 | Processing document 123
```

---

## 相关文档

- **[protocol.md](./protocol.md)** — Logger Protocol 定义
