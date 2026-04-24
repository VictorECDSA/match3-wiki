# Logger 实现 — Loguru 0.7.3

## 文件布局

```
backend/runtime_impl/implements/logger/
├── logger.py                       # create_logger(config) -> Logger
└── impl_loguru/
    └── loguru_logger.py            # LoguruLogger
```

---

## 工厂函数

```python
# backend/runtime_impl/implements/logger/logger.py
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.config import Config
from backend.runtime.protocols.logger.logger import Logger
from backend.runtime.protocols.logger.log_config import LogConfig
from backend.runtime_impl.implements.logger.impl_loguru.loguru_logger import LoguruLogger

def create_logger(config: Config) -> Logger:
    cfg = config.runtime.logger
    log_config = LogConfig(
        level=cfg.level,
        format=cfg.format,
        rotation=cfg.rotation,
        retention=cfg.retention,
        log_file=cfg.log_file,
    )
    try:
        return LoguruLogger(log_config)
    except Exception as e:
        raise Match3Exception.of("failed to initialize logger") \
            .ctx(level=cfg.level, log_file=cfg.log_file).as_ex(e)
```

---

## 适配器

```python
# backend/runtime_impl/implements/logger/impl_loguru/loguru_logger.py
import sys
from loguru import logger as _loguru
from backend.runtime.protocols.logger.log_config import LogConfig

_JSON_FORMAT = (
    '{{"time":"{time:YYYY-MM-DD HH:mm:ss.SSS}",'
    '"level":"{level}","file":"{file}","line":{line},'
    '"message":{message!r}}}'
)

_TEXT_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}:{function}:{line}</cyan> | "
    "<level>{message}</level>"
)

class LoguruLogger:
    """Loguru-backed implementation of Logger protocol."""

    def __init__(self, config: LogConfig):
        self._logger = _loguru
        self._configure(config)

    def _configure(self, config: LogConfig) -> None:
        self._logger.remove()
        fmt = _JSON_FORMAT if config.format == "json" else _TEXT_FORMAT

        self._logger.add(
            sys.stderr,
            format=fmt,
            level=config.level,
            colorize=(config.format == "text"),
            enqueue=True,
        )
        if config.log_file:
            self._logger.add(
                config.log_file,
                format=fmt,
                level=config.level,
                rotation=config.rotation,
                retention=config.retention,
                compression="zip",
                enqueue=True,
            )

    def debug(self, message: str, **kwargs): self._logger.bind(**kwargs).debug(message)
    def info(self, message: str, **kwargs): self._logger.bind(**kwargs).info(message)
    def warning(self, message: str, **kwargs): self._logger.bind(**kwargs).warning(message)
    def error(self, message: str, **kwargs): self._logger.bind(**kwargs).error(message)
    def critical(self, message: str, **kwargs): self._logger.bind(**kwargs).critical(message)
    def exception(self, message: str, **kwargs): self._logger.bind(**kwargs).exception(message)
```

- 使用 `bind(**kwargs)` 把结构化字段附加到当前记录；`json` 格式时所有字段会写入 `extra`。
- `enqueue=True` 让写入在独立线程内异步完成，不阻塞业务协程。

---

## 配置与环境

- `config.yaml` 中的 `runtime.logger.*` 字段定义见 [`../config.md`](../config.md)。
- Logger 不读取 `.env`。

---

## 报错

Logger 一般不在运行期抛错；初始化失败在工厂函数中兜底，其它 `exception()` 用法已在 Protocol 文档示例中。
