# Logger Implementation

Logger implementation using **Loguru** library.

---

## 🛠️ 实现技术栈

- **Protocol**: `Logger` (anim-core)
- **库**: [Loguru](https://github.com/Delgan/loguru)
- **配置**: config.yaml + LogConfig
- **格式**: JSON / Text
- **输出**: Console + File (with rotation)

---

## 📦 适配器实现

### LoguruLogger

```python
# app/runtime/dependencies/logger/loguru/loguru_logger.py
from loguru import logger as loguru_logger
from anim_core.runtime.dependencies.logger.logger import Logger, LogConfig

class LoguruLogger:
    """Loguru-based logger implementation
    
    Note: LoguruLogger satisfies Logger Protocol through structural subtyping.
    No need to explicitly inherit from Logger (Protocol).
    """
    
    def __init__(self, config: LogConfig):
        self._logger = loguru_logger
        self._config = config
        self._configure()
    
    def _configure(self) -> None:
        """Configure loguru logger based on config"""
        # Remove default handler
        self._logger.remove()
        
        # Determine format
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
        else:  # text format
            log_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
        
        # Add console handler
        self._logger.add(
            sys.stderr,
            format=log_format,
            level=self._config.level,
            colorize=(self._config.format == "text")
        )
        
        # Add file handler if specified
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

## Runtime 集成

### 构建函数

```python
# app/runtime/dependencies/logger/logger_factory.py
from anim_core.runtime.dependencies.logger.logger import Logger, LogConfig
from app.runtime.dependencies.logger.loguru.loguru_logger import LoguruLogger

def create_logger(config: Config) -> Logger:
    """Create logger instance from application config"""
    log_config = LogConfig(
        level=config.runtime.logger.level,
        format=config.runtime.logger.format,
        rotation=config.runtime.logger.rotation,
        retention=config.runtime.logger.retention,
        log_file="logs/match3-wiki.log"
    )
    return LoguruLogger(log_config)
```

### build_runtime 中的使用

```python
# app/runtime.py
def build_runtime(config: Config, env: Env) -> Match3Runtime:
    """构建 Runtime 实例"""
    
    # Step 1: 创建 logger
    logger = create_logger(config)
    
    logger.info("Building runtime...")
    
    # Step 2: 初始化各个客户端 (使用 config + env + logger)
    cache = build_cache_client(config, env, logger)
    queue = build_queue_client(config, env, logger)
    # ...
    
    logger.info("Runtime built successfully")
    
    return Match3Runtime(
        config=config,
        env=env,
        logger=logger,
        cache=cache,
        queue=queue,
        # ...
    )
```

---

## 配置示例

### Config (config.yaml)

```yaml
runtime:
  logger:
    level: INFO
    format: json  # json or text
    rotation: 1 day
    retention: 7 days
```

---

## 日志格式示例

### JSON 格式

```json
{"time": "2024-01-15 10:23:45.123", "level": "INFO", "message": "Processing document 123", "file": "processor.py", "line": 45}
```

### Text 格式

```
2024-01-15 10:23:45.123 | INFO     | processor:process:45 | Processing document 123
```

---

## 依赖安装

```bash
pip install loguru
```

---

## 注意事项

1. **日志文件自动轮转**: 使用 rotation 配置自动轮转日志文件
2. **自动压缩**: 旧日志文件自动压缩为 .zip
3. **保留策略**: 使用 retention 配置自动删除过期日志
4. **异常追踪**: `exception()` 方法自动记录 traceback
