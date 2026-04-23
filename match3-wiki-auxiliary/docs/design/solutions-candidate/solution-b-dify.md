[← 返回总览](overview.md) · [方案 A: 全栈自研](solution-a-fullstack.md) · [方案 C: RAGFlow](solution-c-ragflow.md) · [方案 D: 轻量栈](solution-d-lightweight.md)

---

# 方案 B — Dify 低代码平台

**Dify-Based Low-Code Stack · 3-4 周上线，1 人可维护**

2026-04-21 · 三消知识库系统设计

**标签：** Dify 自托管 · Obsidian Wiki · Docusaurus 发布 · Hybrid Search · Workflow RAG · 多用户 Workspace

> ⭐ **强烈推荐：最快上线、功能完整、1 人可运维**

---

> **核心优势：** Dify 是目前最成熟的开源 LLM 应用平台，内置知识库管理、混合检索、Workflow 编排、多用户权限、API 发布，自托管一个 Docker Compose 命令即可启动。配合 Obsidian（Wiki 编辑）+ Docusaurus（对外发布），形成完整闭环，无需从零开发任何后端服务。

---

## 一、整体架构

```text
┌────────────────────────────────────────────────────────────────────┐
│                          内容创作层                                  │
│  Obsidian（本地 Vault）                                              │
│  ├── Wiki 页面编辑（Markdown + frontmatter + [[wikilink]]）          │
│  ├── Obsidian Web Clipper（浏览器插件，随手收集原始资料到 raw/）       │
│  └── Dataview 插件（统计数据丰富度、追踪 status=draft 页面）          │
└──────────────────────┬─────────────────────────────────────────────┘
                       │ git push / sync
┌──────────────────────▼─────────────────────────────────────────────┐
│                     Dify 平台（自托管 Docker）                        │
│                                                                     │
│  ┌──────────────────┐  ┌────────────────────────────────────────┐  │
│  │   Knowledge Base  │  │         Workflow / Chatflow             │  │
│  │                  │  │                                        │  │
│  │  ├ wiki 知识库    │  │  ┌─────────────────────────────────┐  │  │
│  │  │  (Hybrid 检索) │  │  │   Adaptive Router               │  │  │
│  │  ├ raw 知识库     │  │  │   ├── 简单问题 → 直接回答        │  │  │
│  │  │  (原始资料)    │  │  │   ├── 标准问题 → Wiki RAG        │  │  │
│  │  └ market 知识库  │  │  │   ├── 市场数据 → Market RAG      │  │  │
│  │    (市场数据)     │  │  │   └── 复杂问题 → Multi-Agent     │  │  │
│  │                  │  │  └─────────────────────────────────┘  │  │
│  │  Hybrid Search:  │  │   ↓ CRAG 质检                         │  │
│  │  向量 + 关键词   │  │   ↓ Reranking                         │  │
│  │  + Reranking     │  │   ↓ 来源引用生成                       │  │
│  └──────────────────┘  └────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ 用户管理  │  │  API Key │  │ 对话历史  │  │   摄入 Pipeline   │  │
│  │ (RBAC)   │  │  管理    │  │  (存储)   │  │  (Workflow)       │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────────┘  │
└─────────────────────────┬──────────────────────────────────────────┘
                          │  Dify API
         ┌────────────────┴─────────────────┐
         │                                   │
┌────────▼──────────┐            ┌──────────▼──────────┐
│  Docusaurus 站点   │            │  嵌入式 Q&A 悬浮窗   │
│  (对外公开 Wiki)   │            │  (iframe / JS SDK)  │
│  GitHub Pages 托管 │            │  嵌入在 Wiki 页面中  │
└───────────────────┘            └─────────────────────┘
```

---

## 二、Dify 知识库配置（高召回率方案）

### 2.1 知识库分区设计

| 知识库名称 | 内容 | 检索策略 | 分块策略 |
|---|---|---|---|
| **wiki-core** | wiki/ 下所有已编译的 Markdown 页面 | Hybrid Search + Reranking | 按 H2/H3 语义分块，Parent=完整页面 |
| **raw-gdc** | GDC 演讲 PDF（原始） | Hybrid Search，启用 PDF 图表提取 | 500 tokens，overlap=50，保留标题链路 |
| **raw-reports** | 市场报告 PDF（Sensor Tower 等） | 关键词为主 + 向量辅助 | 按表格/段落分块，表格整体保留 |
| **raw-web** | WebFetch 抓取的网页文章 | Hybrid Search | 语义分块 |
| **multimodal** | 图表、截图、GDC 图片 | Vision Embedding | 图片 + GPT-4V 生成的文字描述双入库 |

### 2.2 检索参数配置（Dify UI 可直接设置）

```text
知识库检索设置（Dify Settings → Knowledge Base）:
  检索方式：混合检索（Hybrid）
  向量模型：text-embedding-3-large 或 bge-m3
  关键词权重：0.4（适合三消专有名词多的场景）
  向量权重：0.6
  Top K：60（初始召回量，后续 Reranking 再筛选）
  Reranking 模型：cohere-rerank-v3 或 bge-reranker-v2-m3
  Reranking Top N：8（最终送入 LLM 的文档数）
  相关度阈值：0.3（CRAG 兜底触发阈值）
```

---

## 三、Dify Workflow 设计（Q&A Pipeline）

### 3.1 Adaptive RAG 主流程

**① 问题分类路由** `Dify: LLM Node → Condition Node`

LLM 判断问题类型：简单事实 / 机制设计 / 市场数据 / 跨域复杂问题。输出 category 字段。

**② Multi-Query 改写** `Dify: LLM Node（并行）`

将原始问题改写为 3 个不同表述，并行检索后 RRF 融合。提升专有名词/口语化问题的召回率。

**③ 知识库检索** `Dify: Knowledge Retrieval Node`

按问题 category 路由到对应知识库（wiki-core / raw-gdc / raw-reports）。Hybrid Search + Reranking 自动执行。

**④ CRAG 质检** `Dify: LLM Node + Condition Node`

检查召回内容相关度。若分数低于阈值（无相关文档）→ 触发 Web Search 工具兜底（Dify 内置 Google/Bing 搜索工具）。

**⑤ 答案生成 + 来源引用** `Dify: LLM Node（Answer Node）`

基于过滤后的文档生成答案，强制输出引用来源（文件名 + 页码 + 数据时间）。System Prompt 包含 Self-RAG 质检指令。

**⑥ 幻觉自检（Self-RAG）** `Dify: LLM Node（可选）`

检查答案中的具体数字/断言是否有文档支撑。不支持的内容标注"待验证"而非直接呈现。

### 3.2 多模态摄入 Workflow

```text
触发：用户上传文件（PDF/图片/URL）

[文件类型判断]
    ├── PDF → Dify PDF 解析器（含表格结构保留）
    │         → 嵌入图片 → GPT-4V 生成图表描述
    │         → 文字内容 + 图表描述 合并分块
    │
    ├── 图片（PNG/JPG）→ CLIP 向量化（进 multimodal 知识库）
    │                  → GPT-4V 生成描述文字
    │                  → 双路入库（向量 + 文字描述）
    │
    ├── URL → Jina AI Reader（Dify 内置）抓取正文
    │        → 清洗 → 分块 → 进 raw-web 知识库
    │
    └── 视频 URL（YouTube）→ 调用外部 Whisper API 转录
                           → 转录文字进 raw-gdc 知识库

[自动 Wiki 编译（可选）]
    → LLM 根据资料内容判断对应哪个 wiki 页面
    → 生成 Markdown + frontmatter（data_richness 自评）
    → 写入 wiki/ 目录（通过 Git API 或 Webhook 同步）
```

---

## 四、Dify 多用户 + 权限配置

### 4.1 Dify 内置权限体系

| Dify 角色 | 对应知识库角色 | 可做的事 |
|---|---|---|
| **Owner** | Super Admin | 全部权限：管理成员、API Key、账单、所有知识库 |
| **Admin** | Editor | 创建/编辑知识库；管理 Workflow；邀请成员 |
| **Member** | Contributor | 使用已有应用；上传文档到知识库（需 Admin 审核） |
| **API 访问** | Reader/API User | 通过 API Key 调用 Q&A 接口（嵌入 Docusaurus） |

### 4.2 多工作空间方案

> Dify 企业版支持多 Workspace。社区版（自托管）可通过以下方式实现隔离：

- 按知识库分权：不同用户组只能访问各自的知识库分区
- 按 App 分权：为不同角色创建不同 Dify App（Editor App vs Reader App）
- 多实例部署：如果需要完全隔离，部署多个 Dify 实例，用 Nginx 路由

---

## 五、Obsidian Wiki 层

### 5.1 Obsidian 插件配置

| 插件 | 用途 |
|---|---|
| **Obsidian Web Clipper** | 浏览器插件，一键收集网页到 raw/ 目录 |
| **Dataview** | SQL 式查询：列出所有 status=draft 的页面、data_richness 统计 |
| **Templater** | Wiki 页面模板（自动填充 frontmatter 必填字段，减少遗漏） |
| **Git** | 自动同步到 GitHub，触发 Docusaurus 构建和 Dify 知识库更新 |
| **Local REST API** | 暴露本地 REST API，允许外部脚本写入 Obsidian Vault |
| **Excalidraw** | 在 Wiki 页面内绘制设计图（流程图/棋盘示意图） |

### 5.2 Obsidian → Dify 自动同步

```bash
# GitHub Actions（.github/workflows/sync-to-dify.yml）

# 触发：git push 到 main 分支（wiki/ 目录有变动）

# 步骤：
#   1. 检测变动的 .md 文件列表
#   2. 对每个变动文件：
#      a. 读取文件内容 + frontmatter
#      b. 调用 Dify Knowledge Base API 更新/新增文档
#         PUT /v1/datasets/{dataset_id}/documents/{doc_id}
#      c. 如果文件被删除，同步删除 Dify 中的对应文档
#   3. 触发 Docusaurus 构建（自动发布到 GitHub Pages / Vercel）
```

```python
# 同步脚本伪代码
for changed_file in get_changed_files("wiki/"):
    content = read_file(changed_file)
    frontmatter = parse_frontmatter(content)
    dify_client.upsert_document(
        dataset_id = WIKI_DATASET_ID,
        name = changed_file,
        content = content,
        metadata = {
            "type": frontmatter.type,
            "status": frontmatter.status,
            "data_richness": frontmatter.data_richness,
            "last_updated": frontmatter.last_updated
        }
    )
```

---

## 六、Docusaurus 对外 Wiki 站

### 6.1 嵌入 Dify Q&A

```javascript
// docusaurus.config.js — 全站注入 Dify 悬浮对话窗
scripts: [
  {
    src: 'https://your-dify.com/embed.min.js',
    id: 'match3-wiki-bot',
    'data-token': process.env.DIFY_PUBLIC_TOKEN,
    defer: true,
  }
]

// 效果：所有 Wiki 页面右下角出现悬浮聊天按钮
// 点击展开，自动携带当前页面 URL 作为上下文
// 可问"这个机制在哪些游戏中有实现？""这个数据的来源是哪里？"
```

### 6.2 页面内嵌 Q&A 组件

```jsx
// 在 Wiki 页面 Markdown 中直接嵌入
import DifyQA from '@site/src/components/DifyQA';

<DifyQA
  context="mechanics/special-pieces"
  placeholder="问问关于特殊棋子的设计问题..."
/>
```

---

## 七、GraphRAG 补充方案

> Dify 不原生支持 GraphRAG，但可以通过以下方式补充多跳推理能力：

### 7.1 方案：Dify + 外部 GraphRAG 工具节点

```text
在 Dify Workflow 中增加一个 HTTP Request 节点：

[问题实体识别] — LLM Node：从问题中提取实体（游戏/公司/机制名）
       ↓
[Graph 查询] — HTTP Node：
  POST http://graphify-service/query
  {
    "entities": ["Royal Match", "special pieces"],
    "hops": 2
  }
  返回：相关子图摘要文字
       ↓
[合并图谱结果 + 向量检索结果] — LLM Node：综合两路证据生成答案
```

### 7.2 Graphify 部署（PRD 已规划）

```yaml
# 同 Docker Compose 启动 Graphify
  graphify:
    image: safishamsi/graphify:latest
    volumes:
      - ./wiki:/wiki
    command: graphify serve --wiki /wiki --port 8001

# Dify 中注册为工具（Tool）
  # 工具名：graph_search
  # URL：http://graphify:8001/query
  # 参数：entities（实体列表）, hops（跳数，默认 2）
```

---

## 八、完整部署方案

### 8.1 docker-compose.yml

```yaml
version: '3.8'
services:
  # Dify 核心（自带 PostgreSQL + Redis + Nginx）
  dify:
    image: langgenius/dify:latest
    ports: ["3000:3000"]
    volumes:
      - ./dify-data:/app/api/storage
    environment:
      SECRET_KEY: your-secret-key
      DIFY_PORT: 3000

  # Graphify — 知识图谱服务（可选但推荐）
  graphify:
    image: safishamsi/graphify:latest
    volumes:
      - ./wiki:/wiki:ro
    ports: ["8001:8001"]
    command: graphify serve --wiki /wiki

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl

# 可选：本地 bge-m3 embedding 服务（零 API 费用）
  embedding:
    image: ghcr.io/huggingface/text-embeddings-inference:cpu-1.5
    command: --model-id BAAI/bge-m3
    ports: ["8080:80"]
```

### 8.2 费用估算

| 项目 | 方案 | 月费用 |
|---|---|---|
| VPS（Dify 主机） | 4核8G（Hetzner / Vultr） | $25-40 |
| LLM API | Claude API（按量）**启用 Prompt Caching 可节省 60-80%** | $8-25（缓存后） |
| Embedding | bge-m3 本地部署（零成本）或 OpenAI text-embedding-3-small | $0 / $5-15 |
| Reranker | bge-reranker 本地（推荐）或 Cohere reranker | $0 / $10-30 |
| Docusaurus 托管 | Vercel / GitHub Pages | $0 |
| 域名 + SSL | Cloudflare | $10/年 ≈ $1/月 |
| **合计** | 本地模型优先方案 | **$46-101/月** |

---

## 八·五、CAG / Prompt Caching 成本优化

> **来源：repo-deep-dive 的 CAG 研究结论。** 三消知识库的 System Prompt + 静态 wiki 摘要属于「高度重复的静态上下文」，完全符合 Prompt Caching 的适用条件。实测 API 成本可下降 60-80%。

### 4 层 Prompt 结构（Claude cache_control）

```text
[Layer 1 — 永久缓存，极少变]           ← cache_control: ephemeral（首次后自动入 KV）
  System prompt：角色设定、回答规则、引用格式要求
  全局 wiki 摘要（~2000 tokens）：核心机制关键词表、游戏名称标准化列表

[Layer 2 — 每日更新，每天缓存 1 次]    ← cache_control: ephemeral（daily rebuild）
  今日新增/变更的 wiki 页面摘要
  市场数据快照（最新日期的数字概要）

[Layer 3 — 每次查询，动态构建]         ← 不缓存，按查询实时检索
  当前问题检索到的 Top-5 文档片段
  当前对话历史（最近 6 轮）

[Layer 4 — 用户输入]
  用户当前问题
```

### 在 Dify Workflow 中实现

```text
# Dify System Prompt 节点 — 使用 Jinja2 模板分层注入
# 注：Dify 调用 Claude API 时自动传递 cache_control，
#     需在 Dify Model Provider 配置中开启 "Enable Prompt Cache"

System Prompt 模板：
---
[ROLE]
You are a Match-3 game industry expert assistant. ...
[/ROLE]

[STATIC_WIKI_SUMMARY]  {# 每日从 wiki/ 编译一次，约 1500 tokens #}
{{ static_wiki_summary }}
[/STATIC_WIKI_SUMMARY]
---
# ↑ 以上内容加 cache_control，首次调用后进入 KV 缓存
# 后续调用只需计算 [DYNAMIC_CONTEXT] 以下的 tokens

[DYNAMIC_CONTEXT]
{{ retrieved_passages }}
[/DYNAMIC_CONTEXT]

[CONVERSATION]
{{ chat_history }}
[/CONVERSATION]
```

### 成本对比（以每月 5000 次查询为例）

| 场景 | 输入 tokens/次 | 月费用（Claude Sonnet） |
|---|---|---|
| 无缓存（原始） | ~4000 | ~$48 |
| 启用 Prompt Cache（Layer 1-2 命中） | ~800（动态部分） | **~$10** |
| 节省 | -80% | **节省 ~$38/月** |

---

## 九、实施步骤（3-4 周）

**① 第 1-3 天：Dify 部署 + 知识库初始化**

- VPS 上 docker-compose up 启动 Dify
- 创建 5 个知识库分区（wiki-core / raw-gdc / raw-reports / raw-web / multimodal）
- 配置 Hybrid Search + Reranking 参数
- 上传冷启动种子资料（PRD 第十节清单中的 14 份）

**② 第 4-7 天：Workflow 搭建**

- 在 Dify 可视化界面搭建 Adaptive RAG Workflow
- 配置 Multi-Query 改写节点（3 个查询变体）
- 配置 CRAG 质检 + Web Search 兜底节点
- 测试问答效果，调整 Top K / Reranking 参数

**③ 第 8-14 天：Obsidian + Git 集成**

- 配置 Obsidian Vault 目录结构（对应 PRD wiki/ 结构）
- 安装必要插件（Templater / Dataview / Git）
- 编写 GitHub Actions 同步脚本（wiki 变动 → Dify 知识库更新）
- 设置 Docusaurus 站点，连接 GitHub 自动构建

**④ 第 15-21 天：多模态 + 多用户**

- 配置 PDF 摄入 Workflow（含图表描述提取）
- 配置图片摄入 Workflow（CLIP + GPT-4V 双路）
- 邀请团队成员，配置权限
- 在 Docusaurus 嵌入 Dify 悬浮 Q&A 组件

**⑤ 第 22-28 天：GraphRAG + 优化**

- 部署 Graphify 服务，生成初始知识图谱
- 在 Dify Workflow 中注册 graph_search 工具
- A/B 测试不同 RAG 策略的召回效果
- 正式上线，开始 Phase 1 内容建设

---

### ✅ 优势

- 3-4 周可上线，1 人维护
- Dify 界面调整 RAG 参数无需写代码
- 内置多用户、API 管理、对话历史
- Hybrid Search + Reranking 开箱即用
- 完整 Workflow 可视化编排
- 社区活跃，问题易找到解答
- 月费用仅需 $46-101（启用 Prompt Cache 可降至 $33-66）

### ⚠️ 局限

- GraphRAG 需要外接 Graphify 服务
- UI 定制受 Dify 框架限制
- 如果 Dify 版本升级有 Breaking Change，需要迁移
- 大规模用户（1000+）需要升级 VPS 配置

---

[← 返回总览](overview.md) · [方案 C: RAGFlow →](solution-c-ragflow.md)
