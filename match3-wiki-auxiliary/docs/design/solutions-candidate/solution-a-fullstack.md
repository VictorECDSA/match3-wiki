# 方案 A — 全栈自研平台

**Full-Stack Custom Platform · 功能最全、完全掌控**

2026-04-21 · 三消知识库系统设计

**标签：** Next.js 前端 · FastAPI 后端 · Milvus 向量库 · Neo4j 图数据库 · Multi-Agent RAG · GraphRAG · 多模态

---

> **适合场景：** 需要完全自定义 UI/UX、计划商业化、有 2-3 名开发者、不接受任何第三方平台限制。
> 预计 12-16 周完成，是四种方案中功能最完整、可定制性最高的。

## 一、整体架构

```text
┌─────────────────────────────────────────────────────────────────┐
│                          用户层                                   │
│  浏览器/App                                                       │
│  ├── Wiki 阅读页面（Docusaurus 静态站）                            │
│  ├── Wiki 编辑界面（自研 MDX Editor / Obsidian 桌面版）            │
│  └── Q&A 问答界面（自研 Chat UI）                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / WebSocket
┌──────────────────────────▼──────────────────────────────────────┐
│                     API 网关层（FastAPI）                          │
│  /api/wiki/*   — Wiki CRUD + 版本管理                             │
│  /api/qa/*     — Q&A 对话接口（流式输出 SSE）                      │
│  /api/ingest/* — 资料摄入接口（URL/PDF/图片/视频）                 │
│  /api/admin/*  — 用户管理、权限、审计日志                           │
└──────┬────────────────────┬────────────────┬─────────────────────┘
       │                    │                │
┌──────▼──────┐  ┌──────────▼────────┐  ┌───▼───────────────────┐
│  内容管理层  │  │    RAG 检索层      │  │    任务队列层           │
│  PostgreSQL │  │  Hybrid Search    │  │  Celery + Redis       │
│  ├ wiki 页面 │  │  ├ Milvus（向量）  │  │  ├ 异步摄入任务        │
│  ├ 版本历史  │  │  ├ Elasticsearch  │  │  ├ 批量向量化           │
│  ├ 用户/角色 │  │  │  （BM25）      │  │  ├ Graphify 更新       │
│  └ audit 记录│  │  ├ Neo4j（图谱）   │  │  └ 定时更新任务        │
└─────────────┘  │  └ Reranker       │  └───────────────────────┘
                 └──────────────────┘
┌────────────────────────────────────────────────────────────────┐
│                     AI 服务层                                    │
│  LLM: Claude API / OpenAI API（可按需切换）                       │
│  Embedding: text-embedding-3-large（文本） + CLIP（图像）          │
│  Reranker: BGE-reranker-v2 / Cohere reranker                   │
│  Vision: GPT-4V / Claude 3.5（多模态解析）                        │
└────────────────────────────────────────────────────────────────┘
```

## 二、RAG Pipeline 设计

### 2.1 摄入 Pipeline（Ingestion）

| 步骤 | 名称 | 技术 |
|------|------|------|
| 1 | 来源解析 | Unstructured.io / PyMuPDF / Whisper |
| 2 | 清洗标准化 | 语言检测 / 去重 hash / 翻译（可选） |
| 3 | 语义分块 | Semantic Chunking / Parent-Child |
| 4 | 多模态提取 | 图片→CLIP / 表格→结构化 / GPT-4V 描述 |
| 5 | 双路入库 | 向量→Milvus / 关键词→ES / 图谱→Neo4j |
| 6 | Wiki 编译 | frontmatter / 数据丰富度 / sources 追踪 |

### 2.2 查询 Pipeline（Query — Multi-Agent）

```text
用户问题
    │
    ▼
[Adaptive Router Agent]
    ├── 简单问题（直接回答，无需检索）
    ├── 标准问题 → [Wiki RAG Agent]
    │               ├── Multi-Query 改写（3 个变体）
    │               ├── Hybrid Search（Milvus + ES，k=100）
    │               ├── Parent-Child 上下文扩展
    │               ├── Reranking（BGE Cross-Encoder，取 Top 8）
    │               └── CRAG 质检 → 不足时 Web Search 兜底
    ├── 实体关联问题 → [Graph Agent]
    │               ├── 实体识别（NER）
    │               ├── Neo4j 子图遍历（2-3 跳）
    │               └── 子图摘要生成
    ├── 数据/指标问题 → [Market Data Agent]
    │               ├── 结构化查询（PostgreSQL frontmatter）
    │               └── 数据表格检索
    └── 多源融合问题 → 以上 Agent 并行，[Verifier Agent] 质检
                                         ↓
                                 [Writer Agent]
                                 最终回答 + 来源引用
```

### 2.3 高召回率保障措施

| 措施 | 解决的问题 | 实现方式 |
|------|-----------|---------|
| **Multi-Query 改写** | 用户措辞与文档术语不一致 | LLM 生成 3 个不同表述，分别检索后 RRF 融合 |
| **HyDE 假设性文档** | 短问题与长文档 embedding 距离大 | LLM 生成假答案，用假答案向量检索 |
| **Hybrid Search + RRF** | 专有名词（CPI、Candy Crush）纯语义搜不到 | Milvus 语义 + Elasticsearch BM25，RRF 融合 |
| **Parent-Child 索引** | 小块匹配精，但上下文不够 | 小块检索，返回父块完整上下文 |
| **Cross-Encoder Reranking** | 向量检索返回噪声文档 | BGE-reranker-v2-m3，Top 100 → Top 8 |
| **GraphRAG 多跳推理** | 答案散落在多文档，需关联推理 | Neo4j 实体图谱，沿关系 2-3 跳遍历 |
| **CRAG Web 兜底** | 知识库内容不够，搜不到相关资料 | 相关性低于阈值时回退到 Web 搜索 |
| **Semantic Chunking** | 固定大小切块截断完整语义 | 相邻句子相似度骤降处切块 |

---

## 三、技术栈详细选型

### 3.1 前端

| 模块 | 技术选型 | 理由 |
|------|---------|------|
| Wiki 阅读站 | Docusaurus 3.x | Markdown 原生、中文搜索（Algolia）、SEO 优秀、GitHub Pages 免费部署 |
| Wiki 编辑 | 自研 MDX Editor 或 Obsidian（桌面） | frontmatter 可视化编辑 + wikilink 自动补全 |
| Q&A Chat UI | Next.js 14 + Vercel AI SDK | 流式输出（SSE）、来源引用气泡、消息历史 |
| Admin 后台 | Next.js + shadcn/ui | 用户管理、Audit 面板、摄入任务监控 |
| 状态管理 | Zustand + React Query | 轻量、Server State / Client State 分离 |

### 3.2 后端

| 模块 | 技术选型 | 理由 |
|------|---------|------|
| API 框架 | FastAPI + Python 3.12 | 异步支持好、自动 OpenAPI 文档、与 AI 生态（LangChain/LlamaIndex）无缝集成 |
| 数据库 | PostgreSQL 16 | Wiki 内容、用户、版本历史、frontmatter 结构化查询 |
| 向量数据库 | Milvus 2.x（自托管） | 生产级、支持混合检索、IVF_HNSW 索引、分区隔离多用户 |
| 全文检索 | Elasticsearch 8.x | BM25 算法、中文分词（IK analyzer）、与 Milvus 并行组成 Hybrid Search |
| 图数据库 | Neo4j Community | 游戏/机制/公司实体图谱、Cypher 查询语言、GraphRAG 多跳推理 |
| 对象存储 | MinIO（自托管） | PDF、图片、视频帧存储，S3 兼容 API |
| 任务队列 | Celery + Redis | 异步摄入任务、批量向量化、定时更新 |
| 缓存 | Redis | Q&A 结果缓存、热门问题快速响应 |

### 3.3 AI 模型层

| 功能 | 模型选型 | 备注 |
|------|---------|------|
| 主力 LLM | Claude 3.5 Sonnet / GPT-4o | 问答生成、Multi-Query 改写、CRAG 质检 |
| 文本 Embedding | text-embedding-3-large（OpenAI）或 bge-m3（本地） | 1536 维，中英双语强；bge-m3 零成本 |
| 图像 Embedding | CLIP（openai/clip-vit-large-patch14） | 图表、截图、游戏界面截图向量化 |
| Reranker | BGE-reranker-v2-m3（本地） | 中英双语 Cross-Encoder，零 API 费用 |
| 视觉理解 | GPT-4V / Claude 3.5 Vision | PDF 图表描述、GDC 演讲图表内容提取 |
| 语音转录 | Whisper large-v3（本地） | GDC 视频演讲转文字 |
| 实体提取 | spaCy + GLiNER（本地） | 从文档提取游戏/公司/人物实体，构建知识图谱 |

---

## 四、多用户权限设计

### 4.1 角色定义

| 角色 | 权限 | 场景 |
|------|------|------|
| **Super Admin** | 全部权限 + 系统配置 | 系统管理员 |
| **Editor** | 新增/编辑/删除 Wiki 页面；摄入资料；审核 Audit | 内容建设者 |
| **Contributor** | 新增 Wiki 草稿（不可直接发布）；提交资料到 raw/；提交 Audit | 外部贡献者 |
| **Reader** | 阅读已发布 Wiki；使用 Q&A 问答 | 知识库用户 |
| **API User** | 只能调用 Q&A API（带 API Key） | 外部系统集成 |

### 4.2 多工作空间隔离

```text
workspace_id 贯穿全系统：
  PostgreSQL:  所有表增加 workspace_id 列 + Row-Level Security
  Milvus:      每个 workspace 对应独立 Collection 或 Partition
  Neo4j:       节点/关系增加 workspace 属性，查询时强制过滤
  Redis:       Key 前缀隔离：{workspace_id}:{cache_type}:{key}
```

---

## 五、动态资料摄入接口

### 5.1 支持的输入格式

| 格式 | 解析工具 | 特殊处理 |
|------|---------|---------|
| URL（网页） | Playwright + html2text | 去广告、提取正文、保留表格结构 |
| PDF | PyMuPDF + Unstructured.io | 表格→结构化数据；图片→GPT-4V 描述；排版还原 |
| 图片（PNG/JPG） | CLIP（向量）+ GPT-4V（文字描述） | 截图中的文字用 OCR 提取；图表用 Vision 解读 |
| 视频（MP4/YouTube） | yt-dlp 下载 + Whisper 转录 | 音频→文字；关键帧抽取→图像向量化 |
| Word/PPT | python-docx / python-pptx | 保留标题层级结构；提取嵌入图片 |
| Markdown | 原生解析 | 识别 frontmatter；wikilink 转换为图谱关系 |
| 音频 MP3 | Whisper | 播客/访谈转文字后走文本 Pipeline |

### 5.2 摄入 API

```python
# 摄入 URL
POST /api/ingest
{
  "source": "https://gamediscover.co/match-3-history",
  "type": "url",
  "wiki_target": "history/genre-origins",   // 可选：自动编译到哪篇 wiki
  "workspace_id": "match3-wiki",
  "tags": ["history", "match3-classic"],
  "auto_compile": true                       // 是否立即编译 wiki 页面
}

# 摄入本地文件（multipart form）
POST /api/ingest/file
  file: gdc2024-royal-match.pdf
  workspace_id: match3-wiki
  auto_compile: true

# 查询摄入任务状态
GET /api/ingest/tasks/{task_id}

# 返回示例
{
  "task_id": "abc-123",
  "status": "completed",
  "raw_file": "raw/gdc2024-royal-match.pdf",
  "chunks_created": 48,
  "wiki_compiled": "mechanics/special-pieces.md",
  "data_richness": "★★★★☆"
}
```

---

## 六、Wiki 页面功能设计

### 6.1 Wiki 编辑器功能

| 功能 | 实现 |
|------|------|
| Frontmatter 可视化编辑 | 表单化输入：data_richness 星级选择器、status 下拉、tags 多选、sources 列表 |
| [[wikilink]] 自动补全 | 输入 [[ 时弹出所有 wiki 页面列表，支持模糊搜索 |
| AI 辅助撰写 | 选中文字 → "让 AI 扩展此段" / "检索相关来源" / "翻译为中文" |
| 来源引用助手 | 侧边栏展示当前 raw/ 目录资料，一键插入引用 |
| 版本历史 Diff | 任意两个版本之间 diff 对比，支持回滚 |
| Audit 提交 | 选中文字 → 右键 "提交纠错" → 填写 severity 和描述 |

### 6.2 Wiki 阅读页面功能

| 功能 | 实现 |
|------|------|
| 全文搜索 | Algolia DocSearch（中文支持）或 Pagefind（本地） |
| 悬浮 Q&A 面板 | 阅读页面右侧固定 Q&A 输入框，上下文自动注入当前页面 |
| 知识图谱可视化 | 页面底部展示当前实体的关联图（Graphify + D3.js 渲染） |
| 数据时效标记 | 超过 2 年的数据自动显示 `[数据过期]` 警告气泡 |
| 引用溯源 | 点击数字角标 → 跳转 raw/ 原始文件位置（带高亮） |

---

## 七、项目目录结构

```text
match3-wiki-platform/
├── frontend/
│   ├── wiki-site/          # Docusaurus 静态站
│   ├── chat-ui/            # Next.js Q&A 界面
│   └── admin/              # Next.js 管理后台
├── backend/
│   ├── api/                # FastAPI 主服务
│   │   ├── routers/        # wiki / qa / ingest / admin
│   │   ├── services/       # rag / ingest / wiki / graph
│   │   └── models/         # SQLAlchemy ORM
│   ├── workers/            # Celery 任务
│   │   ├── ingest.py       # 资料摄入 Pipeline
│   │   ├── vectorize.py    # 批量向量化
│   │   └── graph_update.py # 知识图谱更新
│   └── rag/
│       ├── retriever.py    # Hybrid Search + Reranking
│       ├── graph_rag.py    # GraphRAG 多跳推理
│       ├── agents/         # Multi-Agent 调度
│       └── pipeline.py     # 查询 Pipeline 入口
├── wiki/                   # Markdown 内容目录（同 PRD 结构）
├── raw/                    # 原始资料目录
├── docker-compose.yml      # 本地开发环境
└── k8s/                    # 生产部署配置
```

---

## 八、部署方案

### 8.1 本地开发

```bash
# 启动全部服务
docker-compose up -d

# 服务列表
postgres:5432     # 主数据库
milvus:19530      # 向量数据库
elasticsearch:9200 # 全文检索
neo4j:7474        # 图数据库
redis:6379        # 缓存 + 任务队列
minio:9000        # 对象存储

# 启动 API
uvicorn api.main:app --reload

# 启动 Worker
celery -A workers worker --loglevel=info
```

### 8.2 生产部署（推荐）

| 服务 | 部署方式 | 月费用估算 |
|------|---------|-----------|
| API + Workers | VPS（4 核 8G）或 Fly.io | $40-80 |
| Milvus | Zilliz Cloud（托管）或 VPS 自托管 | $50-100 |
| PostgreSQL | Supabase Free / Railway | $0-25 |
| Elasticsearch | 同 API VPS 共部署 | 包含在上方 |
| Neo4j | Neo4j Aura Free（5M 节点） | $0（Free 够用） |
| Wiki 静态站 | Vercel / GitHub Pages | $0 |
| 对象存储 | Cloudflare R2（10GB free） | $0 |
| **合计** | | **$90-205/月** |

---

## 九、实施时间线

| 周次 | 里程碑 | 交付物 |
|------|--------|--------|
| 第 1-2 周 | 基础设施搭建 | Docker Compose 环境；数据库 Schema；Milvus + ES 初始化 |
| 第 3-4 周 | 摄入 Pipeline | URL/PDF/图片摄入 API；Celery 异步任务；向量化入库 |
| 第 5-6 周 | 基础 RAG | Hybrid Search API；Reranking；Q&A 基础问答 |
| 第 7-8 周 | Wiki 功能 | CRUD API；Docusaurus 集成；版本历史 |
| 第 9-10 周 | 高级 RAG | GraphRAG（Neo4j）；Multi-Agent 架构；CRAG 兜底 |
| 第 11-12 周 | 多用户 + 多模态 | RBAC 权限；工作空间隔离；图片/视频摄入 |
| 第 13-14 周 | 前端完善 | Chat UI；Admin 后台；Wiki 编辑器 |
| 第 15-16 周 | 测试 + 上线 | 性能优化；安全审计；生产部署 |

---

> ⚠️ **风险提示：** 方案 A 工程量最大。建议先评估是否值得投入 12-16 周，
> 如果首要目标是 Phase 1 的内容建设，强烈建议先用方案 D 或 B 快速启动，
> 后续再按需迁移至方案 A。

> ✅ **最大优势：** 完全掌控每一层，可以根据三消 Wiki 的特定需求深度定制，
> 没有任何第三方平台的功能限制，适合长期商业化运营。
