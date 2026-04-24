# Runtime 配置与环境变量

Runtime 组件的配置分两处：

- **`config.yaml`** — 非敏感配置（连接池大小、超时、provider 选择等），由 `backend/app/config/config.py` 的 `Config` 加载，暴露为 `rt.config`。
- **`.env`** — 敏感信息（连接串、密码、Access Key），由 `backend/app/config/env.py` 的 `Env` 加载，暴露为 `rt.env`。

两者在应用启动时严格校验：**所有声明字段均为必填，无默认值**。缺失字段直接抛 `Match3Exception.of_code(codes.CONFIG_MISSING_REQUIRED, ...)`（见 [`../design/solution-final/090-error/error-design.md`](../design/solution-final/090-error/error-design.md)）。

---

## config.yaml

全部 Runtime 相关配置位于 `runtime` 节点下。每个组件都有 `provider` 字段，用于选择实现；实现的参数放在 `implementations.<provider>` 子节点下。

```yaml
runtime:

  # ----- Logger（不由 build_runtime 创建，但仍从配置读取） -----
  logger:
    level: INFO               # DEBUG | INFO | WARNING | ERROR | CRITICAL
    format: json              # json | text
    rotation: 1 day           # 日志轮转周期（Loguru 语法）
    retention: 7 days         # 日志保留时长
    log_file: logs/match3-wiki.log   # 日志文件路径（空则仅输出到 stderr）

  # ----- CacheStore -----
  cache_store:
    provider: redis
    implementations:
      redis:
        max_connections: 50
        socket_timeout: 5     # 秒
        decode_responses: true

  # ----- MessageQueue（Celery Broker / Result Backend） -----
  message_queue:
    provider: redis
    implementations:
      redis:
        max_connections: 50
        socket_timeout: 5

  # ----- DatabaseEngine -----
  database:
    provider: postgresql
    implementations:
      postgresql:
        pool_size: 10
        max_overflow: 20
        pool_timeout: 30      # 秒
        pool_recycle: 3600    # 秒
        pool_pre_ping: true
        echo: false           # 开发期可设 true 以打印 SQL

  # ----- VectorDatabase -----
  vector_db:
    provider: milvus
    implementations:
      milvus:
        timeout: 30           # 秒
        consistency_level: Eventually   # Strong | Bounded | Eventually | Session

  # ----- GraphDatabase -----
  graph_db:
    provider: neo4j
    implementations:
      neo4j:
        max_connection_lifetime: 3600     # 秒
        max_connection_pool_size: 50
        connection_acquisition_timeout: 60  # 秒
        default_database: neo4j

  # ----- FullTextSearch -----
  fulltext_search:
    provider: elasticsearch
    implementations:
      elasticsearch:
        request_timeout: 30   # 秒
        max_retries: 3
        retry_on_timeout: true
        verify_certs: true

  # ----- ObjectStorage -----
  object_storage:
    provider: minio
    implementations:
      minio:
        bucket: match3-wiki-files   # 默认 bucket
        secure: false               # 生产环境必须为 true
        region: us-east-1           # MinIO 可任意，S3 兼容
```

---

## .env

所有连接凭证、密钥都从环境变量读取。**生产环境通过 secret manager 注入；禁止提交 `.env` 到版本控制。**

```bash
# ===== App =====
APP_ENV=production            # development | staging | production

# ===== PostgreSQL =====
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DB=match3
POSTGRESQL_USER=match3_user
POSTGRESQL_PASSWORD=

# ===== Redis（CacheStore） =====
# 格式：redis://[:password@]host:port/db
REDIS_CACHE_URL=redis://localhost:6379/0

# ===== Redis（MessageQueue，Celery） =====
REDIS_BROKER_URL=redis://localhost:6379/1
REDIS_RESULT_URL=redis://localhost:6379/2

# ===== Milvus =====
MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=                # 空串代表无认证；Milvus Cloud 必填

# ===== Neo4j =====
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=

# ===== Elasticsearch =====
# 多个节点用逗号分隔，例如：http://es1:9200,http://es2:9200
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_USER=elastic
ELASTICSEARCH_PASSWORD=

# ===== MinIO =====
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
```

---

## 字段归属速查

| 字段类别 | 归 `config.yaml` | 归 `.env` |
|----------|------------------|-----------|
| provider 选择 | ✅ | |
| 连接池 / 超时 / 重试 | ✅ | |
| 功能开关 / 默认值 | ✅ | |
| 主机、端口、协议拼接 | | ✅（通过 `_HOST`/`_PORT`/`_URI`/`_URL`） |
| 用户名、密码、Token、Key | | ✅ |
| 环境标识（`APP_ENV`） | | ✅ |

原则：**同一字段只在一处定义**。`config.yaml` 不包含任何密码或主机名；`.env` 不包含任何池大小或超时。

---

## 报错

配置加载失败统一走 `400010` / `400011`：

```python
# backend/app/config/config.py
from app.common.exceptions import Match3Exception
from app.common.constants import codes

def load_config(path: str) -> Config:
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError as e:
        raise Match3Exception.of_code(codes.CONFIG_FILE_NOT_FOUND,
                                      "config file not found").ctx(path=path).as_ex(e)

    try:
        return Config.model_validate(raw)     # Pydantic 严格校验
    except ValidationError as e:
        raise Match3Exception.of_code(codes.CONFIG_MISSING_REQUIRED,
                                      "invalid config").ctx(path=path).as_ex(e)
```
