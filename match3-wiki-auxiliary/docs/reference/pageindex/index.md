# PageIndex

> 官网：https://pageindex.ai
> 开发者文档：https://docs.pageindex.ai
> 开源仓库：https://github.com/VectifyAI/PageIndex
> 出品方：VectifyAI

## 工具定位

PageIndex 是一个 **vectorless（无向量）、基于推理（reasoning-based）的 RAG 检索框架**，模拟人类专家浏览和提取长文档知识的方式。它不使用向量嵌入、不做固定 chunk 切块、不依赖相似度搜索，而是将文档转为**层级化树状索引**，让 LLM 在树上**像翻书一样导航**并决定读哪一段。

官方在 FinanceBench（金融长文档问答基准）上达成 98.7% 的准确率，并在多项评测中超过传统向量 RAG。

在 match3-wiki 工具链中，PageIndex 适合承担**长文档（如 Sensor Tower/AppMagic/data.ai 的 PDF 市场报告、Facebook Ad Library 政策文档、游戏 GDD 等）**的精准检索角色——这些文档结构化强、章节含义明确，用树索引 + LLM 推理的检索精度显著高于 chunk + 向量。

## 原理介绍

### 核心理念：为什么"无向量"

传统 RAG 的工作流是：文档切块 → embedding → 存入向量库 → query embedding → cosine 相似度 Top-K。
这套流程的三个结构性问题：

1. **切块破坏语义边界**：固定 token 窗口把表格、小节、论证链拦腰切断。
2. **相似度 ≠ 相关性**：Top-K 经常命中"字面相似但逻辑无关"的片段。
3. **不可解释**：检索结果是一组分数，无法告诉你"为什么是这一段"。

PageIndex 的替代方案：保留文档的**原生层级结构**（目录、章节、子节），让 LLM 像人类专家一样**顺着目录往下钻**，每一步的决策都可打印、可审计。

### 架构与核心模块

```
┌──────────────────────────────────────────────────────┐
│                    PageIndex                         │
│                                                      │
│   ┌──────────────┐       ┌────────────────────┐      │
│   │ Document     │       │   Chat API (Beta)  │      │
│   │ Processing   │──────▶│   对话式问答接口   │      │
│   │ (Tree Index  │       └────────────────────┘      │
│   │  Generation) │       ┌────────────────────┐      │
│   └──────┬───────┘       │   Tree Search      │      │
│          │               │ ─ LLM Tree Search  │      │
│          ▼               │ ─ Hybrid Tree      │      │
│   ┌──────────────┐       │   Search           │      │
│   │  Tree Index  │──────▶└────────────────────┘      │
│   │ (hierarchical│       ┌────────────────────┐      │
│   │   JSON)      │──────▶│   Doc Search       │      │
│   └──────────────┘       │ ─ by Metadata      │      │
│                          │ ─ by Semantics     │      │
│   ┌──────────────┐       │ ─ by Description   │      │
│   │ Legacy: OCR /│       └────────────────────┘      │
│   │  Retrieval   │                                   │
│   └──────────────┘                                   │
└──────────────────────────────────────────────────────┘
         │                          ▲
         ▼                          │
    Python / JS SDK · REST API · MCP Server
```

**核心模块说明**：

- **Document Processing（Tree Index 生成）**：PageIndex 的入口。输入 PDF/长文档，输出一个层级化 JSON 树。每个节点对应一个章节/小节，附带标题、摘要、页码范围和原文指针。生成过程本身由 LLM 完成——模型像实习生整理目录一样标注每一节写的是什么。
- **Tree Search（树搜索）**：检索主力。
  - *LLM Tree Search*：纯 LLM 从根节点开始，基于查询和每个节点的摘要决定"往下钻哪个分支"，直到叶子节点取出原文。
  - *Hybrid Tree Search*：在 LLM 导航的基础上叠加轻量信号（如关键词命中），在超长文档上加速。
- **Doc Search（文档级搜索）**：多文档库场景下的"先选文档再检索"两级机制。支持按 Metadata（作者/日期/标签）、Semantics（语义）、Description（人工/LLM 描述）三种方式筛选出候选文档。
- **Chat API（Beta）**：封装好的对话式接口，底层自动编排 Tree Search + 上下文组装。
- **Legacy（OCR/Retrieval）**：旧版遗留模块，OCR 用于扫描版 PDF 预处理。
- **MCP Server**：把 PageIndex 作为 Model Context Protocol 服务器暴露，Claude Desktop / Cursor / Windsurf 等 MCP 客户端可直接挂载。

### 数据流

```
┌──────────┐
│ 长文档    │  PDF / DOCX / 扫描件
│（输入）   │
└─────┬────┘
      │ upload
      ▼
┌──────────────────┐
│ Tree Index       │  LLM 解析目录与章节结构
│ Generation       │  生成 JSON 树（每节附摘要 + 页码）
└─────┬────────────┘
      │
      ▼
┌──────────────────┐
│ Tree Index       │  持久化存储：章节→摘要→原文指针
│（层级化 JSON）    │
└─────┬────────────┘
      │
      │  query 进来
      ▼
┌──────────────────┐
│ LLM Agentic      │  从根节点开始：
│ Navigation       │   "这个问题更像在哪个章节？"
│（树搜索）         │   → 选中分支 → 读摘要 → 继续钻
│                  │   → 命中叶子 → 提取原文
└─────┬────────────┘
      │
      ▼
┌──────────────────┐
│ 检索结果          │  附带推理路径（根 → 章 → 节 → 段）
│（可追溯可解释）   │  可直接引用原文页码
└──────────────────┘
```

与向量 RAG 的关键差异：

| 维度 | 传统向量 RAG | PageIndex |
|---|---|---|
| 索引结构 | 扁平 chunk + embedding | 层级化 Tree |
| 检索方式 | cosine 相似度 Top-K | LLM 在树上推理导航 |
| 切块 | 固定 token 窗口 | 无需切块，按语义单元 |
| 数据库 | 向量数据库 | JSON 树文件 / 对象存储 |
| 可解释性 | 仅相似度分数 | 完整推理路径 + 引用页码 |
| 长文档适配 | 差（需大量切块） | 强（层级越深越有利） |
| 成本模型 | embedding + 向量查询 | 每次查询多次 LLM 调用 |

PageIndex 的取舍很直接：**用 LLM token 成本换取检索质量和可解释性**。对高价值长文档（法律/金融/研报/技术规范），这笔交易通常划算。

## 详细用法

### 接入方式总览

PageIndex 提供 7 种接入通道，按使用门槛从低到高：

1. **Chat Platform** — https://chat.pageindex.ai 浏览器直传直问
2. **Developer Dashboard** — https://dash.pageindex.ai 获取 API Key、管理文档
3. **REST API** — 任意语言 HTTP 调用
4. **Python SDK** — `pageindex` pip 包
5. **JavaScript SDK** — Node/浏览器环境
6. **MCP Server** — 作为 MCP 工具挂到 Claude Desktop / Cursor
7. **开源自部署** — 克隆 GitHub 仓库，企业级私有化部署

### 标准使用流程

```
1. Dashboard 注册 → 拿到 API Key
        ↓
2. 上传文档 → 触发 Tree Index 生成（分钟级，异步）
        ↓
3. 轮询状态 → 拿到 doc_id 和 tree JSON
        ↓
4. 发起查询 → 走 Tree Search 或 Chat API
        ↓
5. 获得答案 + 推理路径 + 原文引用
```

### Python SDK 典型调用

```python
# 安装：pip install pageindex
# 下面给出核心调用片段，实际参数以官方 /sdk/tree 文档为准

from pageindex import PageIndex

client = PageIndex(api_key="YOUR_API_KEY")

# (1) 上传文档并生成 Tree Index
doc = client.documents.create(file_path="./market-report.pdf")
# doc.id 是后续检索的凭证；Tree 生成是异步的
client.documents.wait_until_ready(doc.id)

# (2) 拿到树结构（可持久化到本地）
tree = client.documents.get_tree(doc.id)

# (3) Tree Search 检索
result = client.search.tree(
    doc_id=doc.id,
    query="2024 年中国市场合成类三消游戏 DAU 前五是哪些？",
    mode="hybrid",  # llm | hybrid
)
# result.answer        -> 最终答案
# result.trace         -> 节点导航路径（可解释性核心）
# result.citations     -> 原文页码 + 片段

# (4) Chat API（多轮对话）
chat = client.chat.create(doc_ids=[doc.id])
chat.send("这份报告的核心结论是什么？")
chat.send("其中关于变现模型的部分展开讲讲。")
```

### JavaScript SDK 典型调用

```javascript
// 安装：npm i pageindex
import { PageIndex } from "pageindex";

const client = new PageIndex({ apiKey: process.env.PAGEINDEX_KEY });

const doc = await client.documents.create({ filePath: "./report.pdf" });
await client.documents.waitUntilReady(doc.id);

const result = await client.search.tree({
  docId: doc.id,
  query: "What are the top monetization strategies mentioned?",
});
console.log(result.answer, result.trace);
```

### MCP 集成（Claude Desktop / Cursor）

在 MCP 客户端的配置文件中登记 PageIndex 服务器，之后对话里可直接让模型调用 `pageindex.search` 等工具。具体的 server 命令和环境变量见官方 `/mcp` 文档，典型形态类似：

```json
{
  "mcpServers": {
    "pageindex": {
      "command": "npx",
      "args": ["-y", "@vectifyai/pageindex-mcp"],
      "env": { "PAGEINDEX_API_KEY": "..." }
    }
  }
}
```

### Cookbook 中的 4 种典型范式

官方文档的 `/cookbook` 章节给出 4 类进阶用法，覆盖不同场景：

- **Agentic Vectorless RAG**：纯树搜索，完全不用向量，追求最高可解释性。
- **Vectorless RAG**：简化版，固定策略而非 agentic 推理。
- **Vision RAG**：对含图表/截图的 PDF 启用视觉解析，把图表纳入树节点。
- **Agentic Retrieval**：多文档库场景，先 Doc Search 筛文档，再 Tree Search 钻内容。

## 在 match3-wiki 项目中的作用

### 适用场景

PageIndex 在 match3-wiki 中定位为**长文档精准检索层**，与 Obsidian（知识管理 UI）、向量 RAG（全库语义搜索）互补：

- **市场报告精读**：Sensor Tower / AppMagic / data.ai 的 30–200 页 PDF，章节结构清晰，Tree Search 能精准定位到"合成三消 2024 Q3 收入榜"这类具体小节。
- **GDD/策划文档检索**：竞品泄露的 GDD、官方博客合集，按玩法模块（关卡/经济/UI/进度系统）分章节，LLM 导航天然匹配设计师的查询意图。
- **政策与条款**：Facebook Ad Library 政策、各平台素材审核规则等——错一条引用就可能误导判断，PageIndex 的"可追溯到页码"是硬需求。
- **行业研报归档**：以文档为单位而不是以 chunk 为单位管理，方便按来源筛选、按时间滚动更新。

### 与其他工具的协作

```
Facebook Ad Library / Sensor Tower / AppMagic
          │ 导出 PDF
          ▼
    raw/market/ 原始素材
          │
          ▼
     PageIndex  ←──  长文档精读 / 章节级检索
          │
          │ 检索结果 + 原文引用
          ▼
    wiki/ 编译产出（含引用链接回 PDF 页码）
          │
          ▼
       Obsidian  ←──  浏览、反向链接、Graph View
```

- 与 **Obsidian**：Obsidian 管理"已编译的 wiki 知识"，PageIndex 管理"未编译的原始长文档"。
- 与 **向量 RAG**：短笔记、跨文档模糊检索用向量；长文档精读用 PageIndex。两套索引可以并存。
- 与 **Graphify / nvk-llm-wiki**：PageIndex 提供检索 API，后者负责把检索结果编排成 wiki 页面。

## 局限性

- **Token 成本**：每次查询都要多次 LLM 调用，对高频查询或短文档不经济。
- **索引耗时**：Tree Index 生成是分钟级异步任务，不适合边上传边查的交互。
- **弱结构文档表现下降**：目录混乱、无章节标题的纯文本文件，树的层级质量会打折扣。
- **多文档推理有限**：擅长"单文档深钻"，跨多文档综合推理仍需上层编排（见 Cookbook 的 Agentic Retrieval）。
- **依赖上游 LLM**：推理质量直接受底层模型（Claude / GPT 等）影响，模型掉线 = 检索掉线。
- **生态年轻**：2025 年下半年才进入视野，第三方工具、IDE 插件、监控面板尚不成熟。
