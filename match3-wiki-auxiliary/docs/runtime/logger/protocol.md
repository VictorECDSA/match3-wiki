# Logger Protocol

- **功能**：结构化日志记录（应用日志、调试、异常堆栈）
- **推荐实现**：Loguru 0.7.3
- **Runtime 字段**：`rt.logger: Logger`
- **⚠️ 特殊**：不由 `build_runtime()` 创建，由业务层在调用前通过 `create_logger(config)` 创建后注入

---

## 类清单

| 类 | 文件 | 类型 |
|----|------|------|
| `Logger` | `backend/runtime/protocols/logger/logger.py` | Protocol |
| `LogConfig` | `backend/runtime/protocols/logger/log_config.py` | dataclass |

---

## Logger

```python
# backend/runtime/protocols/logger/logger.py
from typing import Protocol, Any

class Logger(Protocol):
    """Structured logger protocol."""

    def debug(self, message: str, **kwargs: Any) -> None: ...
    def info(self, message: str, **kwargs: Any) -> None: ...
    def warning(self, message: str, **kwargs: Any) -> None: ...
    def error(self, message: str, **kwargs: Any) -> None: ...
    def critical(self, message: str, **kwargs: Any) -> None: ...
    def exception(self, message: str, **kwargs: Any) -> None: ...
```

方法参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `message` | `str` | 日志主体（英文，结构化上下文放 `kwargs`） |
| `**kwargs` | `Any` | 结构化字段（`user_id=123`、`latency_ms=42`）；蛇形命名；标量值 |

- `exception()` 必须在 `except` 块内调用，自动附加 traceback。
- 业务代码**不能**在日志中记录密码、Token、API Key、JWT。

---

## LogConfig

```python
# backend/runtime/protocols/logger/log_config.py
from dataclasses import dataclass

@dataclass(frozen=True)
class LogConfig:
    level: str            # DEBUG | INFO | WARNING | ERROR | CRITICAL
    format: str           # json | text
    rotation: str         # Loguru rotation spec, e.g. "1 day"
    retention: str        # Loguru retention spec, e.g. "7 days"
    log_file: str | None  # None -> stderr only
```

---

## 使用示例

```python
rt.logger.info("ingest started", raw_file_id=raw_file_id, size_bytes=size)

try:
    await external_call()
except Exception as e:
    rt.logger.exception("external call failed", endpoint=url)
    raise Match3Exception.of("external call failed").ctx(endpoint=url).as_ex(e)
```

---

## 关联文档

- [implementation.md](./implementation.md) — Loguru 适配器
- [../config.md](../config.md) — `runtime.logger.*` 配置
- [../../design/solution-final/090-error/error-design.md](../../design/solution-final/090-error/error-design.md) — 日志字段约定与结构化错误日志
