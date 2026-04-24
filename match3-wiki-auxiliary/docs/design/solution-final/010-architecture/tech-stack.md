# 技术栈

## 汇总表

| 组件 | 技术 | 版本 | 选型理由 |
|-----------|------------|---------|-----------|
| 后端框架 | FastAPI | 0.111+ | 原生异步、OpenAPI 自动文档、SSE 支持 |
| 前端框架 | Next.js | 14（App Router） | RSC、流式渲染、基于文件的路由 |
| UI 组件库 | shadcn/ui | Latest | Radix UI + Tailwind，无运行时依赖，主题可完全自定义 |
| 多语言（i18n） | next-intl | 3.x | App Router 原生支持，服务端/客户端共享翻译，按路由加载 |
| 通知提示（Toast） | sonner | Latest | 轻量、无障碍、队列管理，开箱即用的自动消失动画 |
| 关系型数据库 | PostgreSQL | 18 | ACID、JSONB、全文搜索兜底 |
| ORM | SQLAlchemy | 2.0.48（Core + ORM） | 成熟稳定、类型安全、Alembic 迁移 |
| 向量数据库 | Milvus | 2.6.14 | 十亿级 ANN、GPU 加速、IVF_FLAT + HNSW |
| 关键词搜索 | Elasticsearch | 9.3.3 | BM25、通过 RRF 实现混合搜索、经大规模验证 |
| 图数据库 | Neo4j | 2026.03.1 | Cypher 查询、Leiden 社区检测、原生图结构 |
| 任务队列 | Celery | 5.x | 成熟稳定、Redis broker、重试 + ETA、canvas |
| 消息中间件 | Redis | 8.6.2 | Pub/sub、任务队列、会话缓存 |
| 对象存储 | MinIO | RELEASE.2025-10-15 | S3 兼容、自托管、分片上传 |
| 结构化日志 | Loguru | 0.7.3 | 零配置、结构化输出、异步安全 |
| 文本嵌入 | OpenAI text-embedding-3-small | — | 1536 维，语义质量强 |
| 图片嵌入 | CLIP ViT-L/14 | — | 768 维，零样本图文对齐 |
| LLM | GPT-4o / Claude-opus-4-5 | — | 按任务类型可配置 |
| 重排序器 | cross-encoder/ms-marco-MiniLM-L-6-v2 | — | 快速、准确、本地运行 |
| 视觉理解 | GPT-4V / Claude Vision | — | 图片描述、OCR、截图分析 |
| 语音识别 | Whisper large-v3 | — | 音频/视频转写 |
| 文档预处理 | markitdown | Latest | 微软出品，PDF/DOCX/HTML → Markdown |
| 长文档检索 | PageIndex（VectifyAI） | API | 层级目录树导航，无需向量 |
| 认证 | JWT（python-jose） | — | 无状态，RS256 或 HS256 |
| 容器化 | Docker + Docker Compose | — | 一条命令启动完整本地技术栈 |
| 数据库迁移 | Alembic | Latest | SQLAlchemy 原生，版本追踪 |
| 配置管理 | config.yaml + .env | — | config.yaml 存非敏感配置（模型名、连接池、功能开关），.env 存凭证（密码、API Key）；均在启动时严格校验，无默认值 |

---

## PostgreSQL

用于所有关系型数据：用户、工作区、原始文件、Wiki 页面、Q&A 会话、标签。

关键设计选择：
- **JSONB 列**：用于灵活的元数据（原始文件元数据、Wiki frontmatter、RAG 上下文快照）
- **软删除**：通过 `delete_time TIMESTAMPTZ NULL` 实现——永不硬删除记录
- **UUID 主键**：避免多租户场景下的顺序 ID 猜测
- **每张表都有 workspace_id**：行级多租户隔离

通过 SQLAlchemy 配置连接池（参数来自 `rt.config.database`，连接串组装自 `rt.env`）：
```python
engine = create_engine(
    f"postgresql+psycopg2://{env.POSTGRES_USER}:{env.POSTGRES_PASSWORD}"
    f"@{env.POSTGRES_HOST}:{env.POSTGRES_PORT}/{env.POSTGRES_DB}",
    pool_size=config.database.pool_size,
    max_overflow=config.database.max_overflow,
    pool_pre_ping=True,   # detect stale connections
    pool_recycle=config.database.pool_recycle,
)
```

---

## Milvus

两个集合：

### `text_chunks` 集合
- **维度**：1536（text-embedding-3-small）
- **索引**：HNSW（M=16，ef_construction=200）
- **距离度量**：COSINE
- **字段**：chunk_id、raw_file_id、workspace_id、content、embedding、chunk_type、page_num、metadata_json

### `image_chunks` 集合
- **维度**：768（CLIP ViT-L/14）
- **索引**：IVF_FLAT（nlist=1024）
- **距离度量**：IP（内积，归一化）
- **字段**：chunk_id、raw_file_id、workspace_id、image_path、clip_embedding、gpt4v_description、metadata_json

搜索时在每次查询的 `workspace_id` 标量字段上使用分区键过滤器，以强制实现租户隔离。

---

## Elasticsearch

两个索引：

### `text_chunks` 索引
- Mapping：`content`（text，BM25）、`workspace_id`（keyword）、`raw_file_id`（keyword）、`chunk_type`（keyword）、`tags`（keyword 数组）
- 用途：关键词搜索、BM25 排名、混合搜索 RRF 合并

### `wiki_pages` 索引
- Mapping：`title`（text）、`content`（text）、`topic`（keyword）、`workspace_id`（keyword）、`tags`（keyword 数组）
- 用途：Wiki 全文搜索、主题发现

---

## Neo4j

图 Schema（完整 Cypher DDL 见 `050-database/neo4j.md`）：

**节点标签**：`Game`、`Company`、`Developer`、`Mechanic`、`Market`、`Revenue`、`UACreative`、`Hook`

**关系类型**：`MADE_BY`、`HAS_MECHANIC`、`COMPETING_WITH`、`INSPIRED_BY`、`USES_HOOK`、`TARGETS_MARKET`、`EARNS_REVENUE`、`MENTIONED_IN`

用途：
- GraphRAG：在向量块的基础上进行实体子图检索
- 趋势分析："哪些游戏使用了相同的钩子类型？"
- Wiki 页面中的跨实体链接

---

## Celery + Redis

五个队列，各有不同的 Worker 并发数：

| 队列 | 并发数 | 任务 | 备注 |
|-------|-------------|-------|-------|
| `ingest` | 4 | ingest_task | I/O 密集型，可并行运行 |
| `embed` | 2 | embed_task | GPU/API 密集型，受速率限制 |
| `graph` | 2 | graph_task | LLM 密集型，受速率限制 |
| `compile` | 1 | compile_task | 长时运行，token 消耗量大 |
| `rag` | 2 | rag_task | LLM 密集型，Q&A 答案生成 |

任务重试配置：
```python
from app.common.constants import constants

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,   # 1 minute
    queue=constants.QUEUE_INGEST,
)
def ingest_task(self, raw_file_id: str) -> None:
    ...
```

---

## PageIndex

PageIndex（VectifyAI，Apache-2.0）通过层级目录树导航提供无需向量的长文档检索。用于 ≥20 页的 PDF。

```python
from pageindex import IndexConfig, PageIndexClient

client = PageIndexClient(api_key=os.environ["PAGEINDEX_API_KEY"])

# Upload document
doc_id = client.add(pdf_path)  # returns doc_id string

# Fetch hierarchical table-of-contents tree
tree = client.get_tree(doc_id)
# tree is a nested dict: { title, page_range, children: [...] }

# Fetch specific pages
content = client.get_page_content(doc_id, pages=[7, 8, 9])
```

LLM 通过反复询问"目录的哪个分支与 [query] 最相关？"来导航目录树——递归直至到达叶子页面，再检索这些页面。

这避免了对长结构化 PDF（游戏设计文档、市场报告、研究论文）进行分块时产生的错误。

---

## markitdown

微软的 markitdown 库将 PDF、DOCX、PPTX、HTML、CSV 转换为 Markdown，并保留标题结构。

```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert(file_path)   # result.text_content is Markdown string
```

用作所有文档类型在分块之前的预处理步骤。文档中嵌入的图片会被单独提取并发送给 GPT-4V 进行描述。

---

## CLIP（图片嵌入）

用于图片及包含图片的文档：

```python
import torch
import clip
from PIL import Image

model, preprocess = clip.load("ViT-L/14", device="cuda" if torch.cuda.is_available() else "cpu")

def embed_image(image_path: str) -> list[float]:
    image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        embedding = model.encode_image(image)
    embedding = embedding / embedding.norm(dim=-1, keepdim=True)  # normalize
    return embedding.squeeze().tolist()

def embed_text_for_image_search(text: str) -> list[float]:
    tokens = clip.tokenize([text]).to(device)
    with torch.no_grad():
        embedding = model.encode_text(tokens)
    embedding = embedding / embedding.norm(dim=-1, keepdim=True)
    return embedding.squeeze().tolist()
```

文本查询使用 CLIP 的文本编码器进行嵌入，然后通过 IP 度量在 `image_chunks` 集合中搜索。

---

## Whisper（音频/视频转写）

```python
import whisper

model = whisper.load_model("large-v3")

def transcribe(audio_path: str) -> str:
    result = model.transcribe(audio_path, language="en")
    return result["text"]
```

视频文件：使用 `ffmpeg` 提取音频，然后进行转写。以 1fps 提取关键帧用于图片分析。

---

## 重排序器

交叉编码器在本地运行（无需 API 调用）。用于 `hybrid-search` 的最后一步，将前 150 个候选重排序至前 20 个。

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, candidates: list[str], top_k: int = 20) -> list[tuple[int, float]]:
    pairs = [(query, c) for c in candidates]
    scores = reranker.predict(pairs)
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)
    return indexed[:top_k]
```
