# 系统架构概述

## 分层架构

平台按五个水平层次组织。每一层仅与其正下方的层通信（唯一例外：Worker 层也直接与智能层交互）。

```
┌──────────────────────────────────────────────────────────────────────┐
│ LAYER 1 — CLIENT                                                     │
│   Next.js 14 (App Router, RSC)                                       │
│   Pages: /wiki, /qa, /raw, /admin, /compile                          │
│   Components: WikiEditor, QAChat (SSE), IngestDropzone, GraphViewer  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ HTTP REST + SSE
┌────────────────────────────▼─────────────────────────────────────────┐
│ LAYER 2 — API (FastAPI)                                               │
│   Routers: /ingest  /wiki  /qa  /admin  /health                      │
│   Middleware: JWTAuthMiddleware → RBACMiddleware → RateLimitMiddleware│
│   Request shape: ApiReq[T]  →  handler  →  ApiResp[T]                │
└──────────────────┬──────────────────────────┬────────────────────────┘
                   │ direct call               │ enqueue
┌──────────────────▼──────────┐   ┌───────────▼────────────────────────┐
│ LAYER 3 — SERVICE           │   │ LAYER 3b — WORKERS (Celery)        │
│   IngestService             │   │   Queue: ingest     → ingest_task  │
│   WikiCompileService        │   │   Queue: embed      → embed_task   │
│   QAService                 │   │   Queue: graph      → graph_task   │
│   AdminService              │   │   Queue: compile    → compile_task │
│   RAGRouter                 │   │   Queue: rag        → rag_task     │
│   EmbedService              │   │   Broker: Redis                    │
│                             │   │   Result backend: Redis            │
└──────────────────┬──────────┘   └───────────┬────────────────────────┘
                   │                           │
┌──────────────────▼───────────────────────────▼────────────────────────┐
│ LAYER 4 — STORAGE                                                      │
│  PostgreSQL     Milvus         Elasticsearch    Neo4j     Redis MinIO  │
│  (core data)   (vectors)       (BM25)           (graph)  (cache)(files)│
└────────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│ LAYER 5 — INTELLIGENCE                                                │
│   LLM: OpenAI GPT-4o / Anthropic Claude (configurable per task)      │
│   Embedder: text-embedding-3-small (1536-dim)                        │
│   Image embedder: CLIP ViT-L/14 (768-dim)                            │
│   Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2                     │
│   Vision: GPT-4V / Claude Vision (image → text description)          │
│   ASR: Whisper large-v3 (audio → transcript)                         │
│   PageIndex: VectifyAI API (long-doc tree navigation)                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 配置分层：Config + Env

系统配置严格分为两层，参照 anim-facade 模式：

- **`config.yaml`** → `Config` 对象：非敏感配置（连接池大小、模型名称、功能开关、日志级别、Worker 并发数）
- **`.env`** → `Env` 对象：敏感凭证（数据库密码、API Key、JWT Secret）

两者均在应用启动时（`app/cli/api.py`）构建，注入 `Match3Runtime`，其他所有模块通过 `rt.config.xxx` 和 `rt.env.XXX` 访问，**不得**在业务代码中调用 `os.getenv()` 或引用全局实例。

```python
# app/config/config.py
# Purpose: non-sensitive configuration, loaded from config.yaml
# Connection pool sizes, model names, feature flags, concurrency, log level
# Credentials and connection strings go in .env
import os
import yaml
from app.common.exceptions import Match3Exception
from app.common.constants import codes


class Config:
    """Application configuration loaded from config.yaml.

    Hierarchy mirrors config.yaml structure.
    All required fields have no defaults — missing fields cause startup failure.
    Access via: rt.config.database.pool_size, rt.config.llm.default_model
    """

    def __init__(self, data: dict):
        self.app      = AppConfig(data["app"])
        self.server   = ServerConfig(data["server"])
        self.database = DatabaseConfig(data["database"])
        self.redis    = RedisConfig(data["redis"])
        self.milvus   = MilvusConfig(data["milvus"])
        self.es       = ElasticsearchConfig(data["elasticsearch"])
        self.neo4j    = Neo4jConfig(data["neo4j"])
        self.minio    = MinioConfig(data["minio"])
        self.llm      = LLMConfig(data["llm"])
        self.embed    = EmbedConfig(data["embed"])
        self.rerank   = RerankConfig(data["rerank"])
        self.celery   = CeleryConfig(data["celery"])
        self.log      = LogConfig(data["log"])

    @classmethod
    def load_from_yaml(cls, path: str = "config.yaml") -> "Config":
        if not os.path.exists(path):
            raise Match3Exception.of_code(
                codes.CONFIG_FILE_NOT_FOUND, "invalid config file not found"
            ).ctx(path=path)
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(data)


# All sub-config classes follow the same _require() validation pattern.
# Key subclasses shown here; others (AppConfig, ServerConfig, etc.) follow the same structure.

class DatabaseConfig:
    def __init__(self, data: dict):
        self.pool_size    = self._require(data, "pool_size")
        self.max_overflow = self._require(data, "max_overflow")
        self.pool_timeout = self._require(data, "pool_timeout")
        self.pool_recycle = self._require(data, "pool_recycle")

    def _require(self, data, key):
        if key not in data or data[key] is None:
            raise Match3Exception.of_code(
                codes.CONFIG_MISSING_REQUIRED, f"invalid database.{key} is required"
            ).ctx(key=key)
        return data[key]


class LLMConfig:
    """llm.default_provider, llm.default_model, llm.providers[{name, models[{name, temperature, max_tokens}]}]"""

    def __init__(self, data: dict):
        self.default_provider = self._require(data, "default_provider")
        self.default_model    = self._require(data, "default_model")
        self.providers        = {p["name"]: p for p in self._require(data, "providers")}

    def _require(self, data, key):
        if key not in data or data[key] is None:
            raise Match3Exception.of_code(
                codes.CONFIG_MISSING_REQUIRED, f"invalid llm.{key} is required"
            ).ctx(key=key)
        return data[key]


class EmbedConfig:
    """embed.model (text-embedding-3-small), embed.clip_model (ViT-L/14), embed.dimension, embed.batch_size"""

    def __init__(self, data: dict):
        self.model      = self._require(data, "model")
        self.dimension  = self._require(data, "dimension")
        self.clip_model = self._require(data, "clip_model")
        self.batch_size = self._require(data, "batch_size")

    def _require(self, data, key):
        if key not in data or data[key] is None:
            raise Match3Exception.of_code(
                codes.CONFIG_MISSING_REQUIRED, f"invalid embed.{key} is required"
            ).ctx(key=key)
        return data[key]


class MinioConfig:
    """minio.endpoint (host:port, no scheme prefix), minio.bucket, minio.secure"""

    def __init__(self, data: dict):
        self.endpoint = self._require(data, "endpoint")
        self.bucket   = self._require(data, "bucket")
        self.secure   = self._require(data, "secure")

    def _require(self, data, key):
        if key not in data or data[key] is None:
            raise Match3Exception.of_code(
                codes.CONFIG_MISSING_REQUIRED, f"invalid minio.{key} is required"
            ).ctx(key=key)
        return data[key]


class RerankConfig:
    def __init__(self, data: dict):
        self.model = self._require(data, "model")   # "cross-encoder/ms-marco-MiniLM-L-6-v2"
        self.top_k = self._require(data, "top_k")   # 20

    def _require(self, data, key):
        if key not in data or data[key] is None:
            raise Match3Exception.of_code(
                codes.CONFIG_MISSING_REQUIRED, f"invalid rerank.{key} is required"
            ).ctx(key=key)
        return data[key]


# Do NOT create a global instance here!
# Config must only be instantiated in app/cli/api.py and injected into the runtime.
# All other modules access configuration via rt.config
```

```python
# app/config/env.py
# Purpose: sensitive credentials loaded from .env
# All fields are required, no defaults allowed
# Flat structure — keys match .env names exactly (UPPER_SNAKE_CASE)
import os
from dotenv import load_dotenv
load_dotenv()


class Env:
    """Environment variables loaded from .env. Flat structure, no nesting.

    All required values are validated at startup — missing keys cause exit.
    Access via: rt.env.POSTGRES_PASSWORD, rt.env.OPENAI_API_KEY
    """

    def __init__(self):
        # PostgreSQL
        self.POSTGRES_HOST     = self._require("POSTGRES_HOST")
        self.POSTGRES_PORT     = self._require("POSTGRES_PORT")
        self.POSTGRES_DB       = self._require("POSTGRES_DB")
        self.POSTGRES_USER     = self._require("POSTGRES_USER")
        self.POSTGRES_PASSWORD = self._require("POSTGRES_PASSWORD")
        # Vector and search storage
        self.MILVUS_URI        = self._require("MILVUS_URI")
        self.ES_URL            = self._require("ES_URL")
        self.NEO4J_URI         = self._require("NEO4J_URI")
        self.NEO4J_USER        = self._require("NEO4J_USER")
        self.NEO4J_PASSWORD    = self._require("NEO4J_PASSWORD")
        # Cache and queue
        self.REDIS_URL             = self._require("REDIS_URL")
        self.CELERY_BROKER_URL     = self._require("CELERY_BROKER_URL")
        self.CELERY_RESULT_BACKEND = self._require("CELERY_RESULT_BACKEND")
        # Object storage
        self.MINIO_ACCESS_KEY  = self._require("MINIO_ACCESS_KEY")
        self.MINIO_SECRET_KEY  = self._require("MINIO_SECRET_KEY")
        # LLM / AI
        self.OPENAI_API_KEY    = self._require("OPENAI_API_KEY")
        self.ANTHROPIC_API_KEY = self._require("ANTHROPIC_API_KEY")
        self.PAGEINDEX_API_KEY = self._require("PAGEINDEX_API_KEY")
        # Authentication
        self.JWT_SECRET   = self._require_secret("JWT_SECRET")
        self.CORS_ORIGINS = self._parse_cors_origins("CORS_ORIGINS")

    def _require(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise EnvironmentError(f"{key} is required in .env file.")
        return value

    def _require_secret(self, key: str) -> str:
        value = self._require(key)
        if len(value) < 32:
            raise EnvironmentError(
                f"{key} must be >= 32 chars. "
                f"Generate: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return value

    def _parse_cors_origins(self, key: str) -> list[str]:
        value = self._require(key)
        return [o.strip() for o in value.split(",") if o.strip()]


# Do NOT create a global instance here!
# Env must only be instantiated in app/cli/api.py and injected into the runtime.
# All other modules access environment variables via rt.env
```

---

## Match3Runtime — 冻结依赖容器

`Match3Runtime` 是 `@dataclass(frozen=True)`，所有基础设施依赖均通过 `typing.Protocol` 接口注入，运行时不可变。设计细节见 [`../../runtime/runtime.md`](../../runtime/runtime.md)。

| 字段 | Protocol | 推荐实现 |
|------|----------|---------|
| `config` | `Config` | — |
| `env` | `Env` | — |
| `logger` | `Logger` | Loguru 0.7.3 |
| `cache` | `CacheStore` | Redis 8.6.2 |
| `queue` | `MessageQueue` | Redis 8.6.2 |
| `vector_db` | `VectorDatabase` | Milvus 2.6.14 |
| `graph_db` | `GraphDatabase` | Neo4j 2026.03.1 |
| `db` | `DatabaseEngine` | PostgreSQL 18 + SQLAlchemy 2.0.48 |
| `search` | `FullTextSearch` | Elasticsearch 9.3.3 |
| `storage` | `ObjectStorage` | MinIO RELEASE.2025-10-15 |

LLM、Embedder、Reranker、PageIndex 等智能层接口**不在** `Match3Runtime` 中——它们属于独立的智能层，由各 Service/Task 按需注入。

业务层只依赖 Protocol 抽象，测试时用 `MagicMock()` 直接替换字段，无需 `@patch` 任何全局符号。

---

## 异常处理规范

本系统所有异常均使用 `Match3Exception` 模式（与 `AnimException` 完全相同）：

```python
# app/common/exceptions.py
from __future__ import annotations
from typing import Optional


class Match3Exception(Exception):
    """Exception class with chained cause propagation and context key-value pairs.

    Factory methods:
      Match3Exception.of(message)              — code=0, preserves code from cause chain
      Match3Exception.of_code(code, message)   — overrides with a specific business code

    Chaining:
      .ctx(key=value)    — attach context for logging and debugging
      .as_ex(exception)  — wrap any exception as the cause

    Business code resolution:
      .resolve_code()    — walks the cause chain, returns the first non-zero code

    Key constraint: keep try blocks minimal — each try wraps exactly one call.
    """

    def __init__(self, message: str, code: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self._context: list[tuple[str, object]] = []

    @classmethod
    def of(cls, message: str) -> "Match3Exception":
        return cls(message, code=0)

    @classmethod
    def of_code(cls, code: int, message: str) -> "Match3Exception":
        return cls(message, code=code)

    def ctx(self, **kwargs: object) -> "Match3Exception":
        for key, value in kwargs.items():
            self._context.append((key, value))
        return self

    def as_ex(self, exception: BaseException) -> "Match3Exception":
        self.__cause__ = exception
        return self

    def resolve_code(self) -> int:
        if self.code != 0:
            return self.code
        cause = self.__cause__
        while cause is not None:
            if isinstance(cause, Match3Exception) and cause.code != 0:
                return cause.code
            cause = getattr(cause, "__cause__", None)
        return 0

    def __str__(self) -> str:
        return self._build_string(set())

    def _build_string(self, exclude: set[tuple[str, str]]) -> str:
        parts = [self.message]
        display = []
        for k, v in self._context:
            if v is not None:
                vs = str(v)
                if (k, vs) not in exclude:
                    display.append((k, vs))
        if display:
            parts.append("(" + ", ".join(f"{k}:{v}" for k, v in display) + ")")
        cause = self.__cause__
        if cause is not None:
            next_exclude = exclude.copy()
            for k, v in self._context:
                if v is not None:
                    next_exclude.add((k, str(v)))
            if isinstance(cause, Match3Exception):
                cs = cause._build_string(next_exclude)
                if cs:
                    parts.append(f" as: {cs}")
            else:
                parts.append(f" as ex: {cause}")
        return "".join(parts)
```

业务码定义在 `app/common/constants/codes.py` 中——这是**唯一权威来源**。完整码值及分层规则见 `090-error/error-design.md` 第一节，禁止在任何其他文件中重新定义或内联数字字面量。
