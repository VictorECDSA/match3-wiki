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

两者均在 `main.py` 中构建，注入 `Match3Runtime`，其他所有模块通过 `rt.config.xxx` 和 `rt.env.XXX` 访问，**不得**在业务代码中调用 `os.getenv()` 或引用全局实例。

```python
# app/config/config.py
# 用途：非敏感配置，来自 config.yaml
# 连接池大小、模型名称、功能开关、并发数、日志级别
# 凭证和连接字符串放到 .env
import os
import yaml
from app.common.exceptions import Match3Exception
from app.common.constants import codes


class Config:
    """从 config.yaml 加载的应用配置。

    层级结构与 config.yaml 保持一致。
    所有必填字段无默认值——缺少字段将导致启动退出。
    访问方式：rt.config.database.pool_size，rt.config.llm.default_model
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


# 所有子配置类遵循相同的 _require() 验证模式。
# 此处展示关键子类；其他类（AppConfig、ServerConfig 等）结构相同。

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
    """llm.default_provider、llm.default_model、llm.providers[{name, models[{name, temperature, max_tokens}]}]"""

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
    """embed.model（text-embedding-3-small）、embed.clip_model（ViT-L/14）、embed.dimension、embed.batch_size"""

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
    """minio.endpoint（host:port，无协议头）、minio.bucket、minio.secure"""

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


# 禁止在此处创建全局实例！
# Config 只应在 main.py 中构建，并注入 runtime。
# 其他模块通过 rt.config 访问配置
```

```python
# app/config/env.py
# 用途：来自 .env 的敏感信息
# 所有字段必填，不允许默认值
# 扁平结构——与 .env 键名完全一致（UPPER_SNAKE_CASE）
import os
from dotenv import load_dotenv
load_dotenv()


class Env:
    """从 .env 加载的环境变量。扁平结构，无嵌套。

    所有必填值在启动时校验——缺少键将导致退出。
    访问方式：rt.env.POSTGRES_PASSWORD，rt.env.OPENAI_API_KEY
    """

    def __init__(self):
        # PostgreSQL
        self.POSTGRES_HOST     = self._require("POSTGRES_HOST")
        self.POSTGRES_PORT     = self._require("POSTGRES_PORT")
        self.POSTGRES_DB       = self._require("POSTGRES_DB")
        self.POSTGRES_USER     = self._require("POSTGRES_USER")
        self.POSTGRES_PASSWORD = self._require("POSTGRES_PASSWORD")
        # 向量与搜索存储
        self.MILVUS_URI        = self._require("MILVUS_URI")
        self.ES_URL            = self._require("ES_URL")
        self.NEO4J_URI         = self._require("NEO4J_URI")
        self.NEO4J_USER        = self._require("NEO4J_USER")
        self.NEO4J_PASSWORD    = self._require("NEO4J_PASSWORD")
        # 缓存与队列
        self.REDIS_URL             = self._require("REDIS_URL")
        self.CELERY_BROKER_URL     = self._require("CELERY_BROKER_URL")
        self.CELERY_RESULT_BACKEND = self._require("CELERY_RESULT_BACKEND")
        # 对象存储
        self.MINIO_ACCESS_KEY  = self._require("MINIO_ACCESS_KEY")
        self.MINIO_SECRET_KEY  = self._require("MINIO_SECRET_KEY")
        # LLM / AI
        self.OPENAI_API_KEY    = self._require("OPENAI_API_KEY")
        self.ANTHROPIC_API_KEY = self._require("ANTHROPIC_API_KEY")
        self.PAGEINDEX_API_KEY = self._require("PAGEINDEX_API_KEY")
        # 认证
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


# 禁止在此处创建全局实例！
# Env 只应在 main.py 中构建，并注入 runtime。
# 其他模块通过 rt.env 访问环境变量
```

---

## Match3Runtime — 冻结依赖容器

所有外部依赖均以 **Protocol 接口**存入 Runtime，不持有任何具体实现类。这带来两个关键收益：

1. **Mock 注入零成本**：测试时直接用 `MagicMock()` 替换 `rt.llm`、`rt.embedder` 等，无需 `@patch` 任何全局符号
2. **实现可随时替换**：将 OpenAI 换成 Anthropic、将 MinIO 换成云端 S3 SDK，只需修改 `build_runtime()` 中的具体类，所有服务代码零改动

```python
# app/runtime.py
from __future__ import annotations
from dataclasses import dataclass
from logging import Logger
from typing import TYPE_CHECKING, Protocol, Iterator, TypedDict

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from pymilvus import MilvusClient
    from elasticsearch import Elasticsearch
    from neo4j import Driver
    from redis import Redis
    from app.config.config import Config
    from app.config.env import Env


# ---------------------------------------------------------------------------
# 智能接口（Protocol）
# 具体实现位于 app/intelligence/
# ---------------------------------------------------------------------------

class ToolCallResult(TypedDict):
    """complete_with_tools() 返回的单条工具调用记录。"""
    tool_call_id: str
    tool_name: str
    arguments: dict
    # 原始 assistant 消息 dict（role=assistant），可直接追加到 messages 列表
    assistant_message: dict
    finish_reason: str   # "tool_calls" | "stop" | "length"


class LLMCaller(Protocol):
    """LLM 文本补全接口。实现类：OpenAILLMCaller、AnthropicLLMCaller。"""
    def complete(
        self, messages: list[dict], *,
        model: str | None = None,
        temperature: float = 0.0,
        response_format: dict | None = None,
    ) -> str: ...
    def stream(self, messages: list[dict], *, model: str | None = None) -> Iterator[str]: ...
    def complete_with_tools(
        self, messages: list[dict], tools: list[dict], *,
        model: str | None = None,
        tool_choice: str = "auto",
    ) -> list[ToolCallResult]:
        """执行一步 ReAct，附带工具定义。

        返回 ToolCallResult 列表——每个 tool_call 对应一项。
        若 finish_reason 为 "stop"（无工具调用），返回单项：tool_name=""，arguments={}，并附 assistant_message。
        调用方在每次后续调用前，必须将 assistant_message 追加到 messages。
        """
        ...


class Embedder(Protocol):
    """用于稠密+稀疏混合搜索的文本嵌入接口。实现类：OpenAIEmbedder。"""
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def embed_both(self, texts: list[str]) -> tuple[list[list[float]], list[dict]]: ...


class ImageEmbedder(Protocol):
    """用于多模态搜索的 CLIP 图片/文本嵌入接口。实现类：CLIPImageEmbedder。"""
    def embed_image(self, image_path: str) -> list[float]: ...
    def embed_text(self, text: str) -> list[float]: ...


class Transcriber(Protocol):
    """音频/视频转文本转写接口。实现类：WhisperTranscriber。"""
    def transcribe(self, audio_path: str) -> str: ...


class Reranker(Protocol):
    """检索候选项交叉编码器重排序接口。"""
    def rerank(self, query: str, candidates: list[str], top_k: int = 20) -> list[tuple[int, float]]: ...


class ObjectStorage(Protocol):
    """S3 兼容对象存储接口。实现类：MinioObjectStorage。
    目标 bucket 在构建时通过 config.minio.bucket 注入。
    """
    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...
    def get_object(self, key: str) -> bytes: ...
    def delete_object(self, key: str) -> None: ...


class PageIndexClient(Protocol):
    """长文档层级目录树导航接口（VectifyAI）。实现类：VectifyPageIndexClient。"""
    def add(self, pdf_path: str) -> str: ...
    def get_tree(self, doc_id: str) -> dict: ...
    def get_page_content(self, doc_id: str, pages: list[int]) -> str: ...


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Match3Runtime:
    """注入到每个服务和任务的不可变依赖容器。

    - config：非敏感配置（连接池大小、模型名称、功能开关）—— rt.config.xxx
    - env：敏感凭证（密码、API Key）—— rt.env.XXX
    - 所有智能接口成员均类型化为 Protocol 接口，而非具体类。

    禁止通过导入全局单例来构建服务。
    始终以显式参数接收 runtime。
    """
    # ── 配置与环境 ─────────────────────────────────────────────────────────
    config: "Config"   # 来自 config.yaml 的非敏感配置（连接池大小、模型名称、功能开关）
    env: "Env"         # 来自 .env 的敏感凭证（密码、API Key、JWT Secret）
    logger: Logger     # 应用全局 logger（"match3"）

    # ── 存储客户端 ───────────────────────────────────────────────────────────
    db_engine: "Engine"        # SQLAlchemy engine → PostgreSQL（ORM 会话 + 原生 SQL）
    redis: "Redis"             # Redis 客户端——缓存和 Celery 结果后端
    milvus: "MilvusClient"     # Milvus 客户端——向量相似度搜索（稠密 + 稀疏）
    es: "Elasticsearch"        # Elasticsearch 客户端——BM25 关键词搜索
    neo4j: "Driver"            # Neo4j 驱动——知识图谱查询

    # ── 智能接口（Protocol——在 build_runtime() 内部替换实现）──
    llm: LLMCaller             # 文本补全 + 流式输出；实现类：OpenAILLMCaller、AnthropicLLMCaller
    embedder: Embedder         # 稠密 + 稀疏文本嵌入；实现类：OpenAIEmbedder（+ BGE-M3 稀疏）
    image_embedder: ImageEmbedder  # CLIP 图片/文本嵌入，用于多模态搜索
    transcriber: Transcriber   # 音频/视频 → 转写文本；实现类：WhisperTranscriber
    reranker: Reranker         # 检索候选项交叉编码器重排序
    storage: ObjectStorage     # S3 兼容对象存储；实现类：MinioObjectStorage（bucket 在构建时注入）
    pageindex: PageIndexClient # 长文档层级导航；实现类：VectifyPageIndexClient


def build_runtime(config: "Config", env: "Env") -> Match3Runtime:
    """构建完整注入的 Match3Runtime。在 main.py 启动时调用一次。"""
    import logging
    from sqlalchemy import create_engine
    from pymilvus import MilvusClient
    from elasticsearch import Elasticsearch
    from neo4j import GraphDatabase
    from redis import Redis
    from app.intelligence.llm import OpenAILLMCaller
    from app.intelligence.embedder import OpenAIEmbedder
    from app.intelligence.image_embedder import CLIPImageEmbedder
    from app.intelligence.transcriber import WhisperTranscriber
    from app.intelligence.reranker import CrossEncoderReranker
    from app.intelligence.storage import MinioObjectStorage
    from app.intelligence.pageindex import VectifyPageIndexClient
    from app.common.exceptions import Match3Exception

    logger = logging.getLogger("match3")
    cfg, e = config, env

    postgres_url = (
        f"postgresql+psycopg2://{e.POSTGRES_USER}:{e.POSTGRES_PASSWORD}"
        f"@{e.POSTGRES_HOST}:{e.POSTGRES_PORT}/{e.POSTGRES_DB}"
    )

    try:
        db_engine = create_engine(
            postgres_url,
            pool_size=cfg.database.pool_size,
            max_overflow=cfg.database.max_overflow,
            pool_timeout=cfg.database.pool_timeout,
            pool_recycle=cfg.database.pool_recycle,
            pool_pre_ping=True,
        )
    except Exception as ex:
        raise Match3Exception.of("failed to create_engine").ctx(url="<redacted>").as_ex(ex)

    try:
        redis_client = Redis.from_url(e.REDIS_URL, max_connections=cfg.redis.max_connections)
    except Exception as ex:
        raise Match3Exception.of("failed to connect redis").ctx(url="<redacted>").as_ex(ex)

    try:
        milvus_client = MilvusClient(uri=e.MILVUS_URI)
    except Exception as ex:
        raise Match3Exception.of("failed to connect milvus").ctx(uri="<redacted>").as_ex(ex)

    try:
        es_client = Elasticsearch(e.ES_URL)
    except Exception as ex:
        raise Match3Exception.of("failed to connect elasticsearch").ctx(url=e.ES_URL).as_ex(ex)

    try:
        neo4j_driver = GraphDatabase.driver(e.NEO4J_URI, auth=(e.NEO4J_USER, e.NEO4J_PASSWORD))
    except Exception as ex:
        raise Match3Exception.of("failed to connect neo4j").ctx(uri=e.NEO4J_URI).as_ex(ex)

    return Match3Runtime(
        config=config,
        env=env,
        logger=logger,
        db_engine=db_engine,
        redis=redis_client,
        milvus=milvus_client,
        es=es_client,
        neo4j=neo4j_driver,
        llm=OpenAILLMCaller(
            api_key=e.OPENAI_API_KEY,
            default_model=cfg.llm.default_model,
        ),
        embedder=OpenAIEmbedder(
            api_key=e.OPENAI_API_KEY,
            model=cfg.embed.model,
            batch_size=cfg.embed.batch_size,
        ),
        image_embedder=CLIPImageEmbedder(model=cfg.embed.clip_model),
        transcriber=WhisperTranscriber(model="large-v3"),
        reranker=CrossEncoderReranker(model=cfg.rerank.model, top_k=cfg.rerank.top_k),
        storage=MinioObjectStorage(
            endpoint=cfg.minio.endpoint,
            access_key=e.MINIO_ACCESS_KEY,
            secret_key=e.MINIO_SECRET_KEY,
            bucket=cfg.minio.bucket,
            secure=cfg.minio.secure,
        ),
        pageindex=VectifyPageIndexClient(api_key=e.PAGEINDEX_API_KEY),
    )
```

---

## 异常处理规范

本系统所有异常均使用 `Match3Exception` 模式（与 `AnimException` 完全相同）：

```python
# app/common/exceptions.py
from __future__ import annotations
from typing import Optional


class Match3Exception(Exception):
    """支持链式传递和上下文键值对的异常类。

    工厂方法：
      Match3Exception.of(message)              — code=0，保留因果链中的 code
      Match3Exception.of_code(code, message)   — 以特定业务码覆盖

    链式调用：
      .ctx(key=value)    — 附加上下文，用于日志和调试
      .as_ex(exception)  — 将任意异常包装为原因

    业务码解析：
      .resolve_code()    — 遍历因果链，返回第一个非零 code

    关键约束：保持 try 块最小——每个 try 只包裹一次调用。
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

---

## 数据流：文件导入

```
1. 用户通过 POST /api/v1/ingest/upload 上传文件
2. API 将原始文件保存至 MinIO → 插入 RawFile 记录（status=pending）
3. API 将 ingest_task(raw_file_id) 入队 → 返回 {task_id}
4. Worker: ingest_task
   a. 从 MinIO 加载文件
   b. 按文件类型分发至解析器：
      - 所有 PDF   → markitdown → 文本块；PDF ≥ 20 页时**额外**注册 PageIndex（附加行为，不替代分块）
      - 图片           → CLIP embed + GPT-4V 描述
      - 视频           → 提取关键帧 + Whisper 转写
      - 音频           → Whisper 转写
      - HTML/MD/CSV/TXT → markitdown 或直接解析
   c. 对文本进行分块（语义分块或固定大小兜底）
   d. 将 embed_task(chunk_ids) 入队
   e. 将 graph_task(raw_file_id) 入队
5. Worker: embed_task
   a. 批量嵌入文本块 → 写入 Milvus
   b. 批量嵌入图片块 → 写入 Milvus（CLIP 集合）
   c. 将所有块索引至 Elasticsearch（BM25）
6. Worker: graph_task
   a. LLM 实体提取：游戏、公司、指标、日期、机制
   b. 将节点和关系写入 Neo4j
7. 将 RawFile status 更新为 DONE
```

---

## 数据流：Q&A 查询

```
1. 用户发送 POST /api/v1/qa/ask（或 GET with SSE）
2. QAService.ask(query, workspace_id, user_id)
3. RAGRouter.route(query) → 选择路径：chunk | entry | page
4. 执行路径：
   hybrid-search:
     a. AdaptiveRAG 选择子方法（naive/multi-query/HyDE/hybrid/graph/等）
     b. 从 Milvus + ES 检索文本块
     c. 使用交叉编码器重排序
     d. 生成答案（流式 SSE）
   wiki-lookup:
     a. 按 slug/topic 查找 Wiki 条目页面
     b. 直接返回已编译的 Wiki 页面（若已过期则重新编译）
   doc-navigate:
     a. PageIndex 目录树导航
     b. 从长 PDF 检索特定页面
     c. 根据页面内容生成答案
5. 通过 SSE 流式返回 token
6. 将 QASession + QATurn 写入 PostgreSQL
```

---

## 数据流：Wiki 编译

```
1. 用户触发 POST /api/v1/wiki/compile（或定时任务）
2. WikiCompileService.compile(topic, workspace_id)
3. 将 compile_task(topic, workspace_id) 入队
4. Worker: compile_task（OpenKB 五步法）
   a. 上下文收集：汇聚所有标记到该主题的原始文件 → 构建上下文
   b. 摘要：LLM 将上下文总结为结构化摘要
   c. 概念规划：LLM 列出所有需要覆盖的概念/子章节
   d. 并行概念生成：
      - 派生 N 个子智能体任务（N = 主题复杂度，5 或 8 个）
      - 每个子智能体生成一个章节（共享系统提示前缀以利用缓存）
   e. 交叉链接：LLM 插入 [[wikilinks]] 指向其他 Wiki 条目
5. 将 WikiPage 写入 PostgreSQL + 将 .md 保存至 MinIO
6. 将 WikiPage status 更新为 PUBLISHED
```
