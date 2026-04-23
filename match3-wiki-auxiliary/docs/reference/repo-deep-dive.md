---
id: repo-deep-dive
title: GitHub 仓库深度调研报告
owner: arch-01
created_at: 2026-04-20
status: v1.0
scope: operator 2026-04-19 提供的 9 个 GitHub 仓库 + arch-01 补充的 1 个（OpenKB）+ CAG/Prompt Caching 技术范式 1 个
audience: operator / pm-01 / dev-* / 任何需要理解我们技术选型来源的人
---

# GitHub 仓库深度调研报告

> **本报告的定位**：不是"评分选型表"（那是 [`tech-selection.md`](tech-selection.md) 的任务），而是**对每个仓库进行"进源码看过"的深度描述**，回答：
>
> 1. 这个项目在做什么？
> 2. 核心能力有哪些？
> 3. 知识库构建的逻辑是什么？
> 4. 许可证与合规边界
> 5. 对 ConsultingBrain 的启示（吸收什么 / 不吸收什么）
>
> **调研方式**：进入每个仓库实际看 README + 架构文档 + 核心源码入口，而非只看首页介绍。

---

## 0. 综述（先看这一页）

### 0.1 10 个项目按"对 ConsultingBrain 贡献度"排序

| 排名 | 项目 | 贡献度 | 一句话定位 |
|---|---|---|---|
| ⭐⭐⭐ | **OpenKB** | 最高 | 可直接集成代码的 LLM Wiki + PageIndex CLI |
| ⭐⭐⭐ | **Youtu-RAG** | 最高（本轮上调） | **完整的多租户 Agentic RAG 后端**（此前低估，详见 §2） |
| ⭐⭐⭐ | **PageIndex**（OpenKB 依赖） | 高 | 独立的 Apache-2.0 向量-less 长文档检索引擎 |
| ⭐⭐ | **Karpathy LLM Wiki gist** | 高 | 所有 wiki 方案的思想原点 |
| ⭐⭐ | **rohitg00 LLM Wiki v2** | 高 | 在 Karpathy 基础上补了生命周期 / 图谱 / 搜索 / 自动化的范式增量 |
| ⭐⭐ | **llm_wiki**（nashsu，Tauri 桌面应用） | 中（范式） | Karpathy 范式的完整桌面应用实现（GPL，仅学不抄） |
| ⭐⭐ | **Obsidian-Brain-OS** | 中 | 个人数字分身 + 三阶段夜间流水线蓝本 |
| ⭐ | **CAG / Prompt Caching 文章** | 中 | Anthropic/OpenAI prompt caching 工程范式，对咨询长上下文场景价值大 |
| ⭐ | **workshop-agentic-search** | 低 | Weaviate / Elastic 的 Agentic 搜索教学 notebook |
| ❌ | **enso-os** | 完全不相关 | Agent 纪律系统（Claude Code 插件），非知识库 |
| ❌ | **gstack** | 完全不相关 | Claude Code 的虚拟工程团队 skill 包（Garry Tan 开发） |

https://github.com/VectifyAI/OpenKB
https://github.com/TencentCloudADP/youtu-rag
https://github.com/VectifyAI/PageIndex
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
https://github.com/nashsu/llm_wiki
https://github.com/FairladyZ625/Obsidian-Brain-OS
https://x.com/_avichawla/status/2045767552526340205
https://github.com/iamleonie/workshop-agentic-search
https://github.com/amazinglvxw/enso-os
https://github.com/garrytan/gstack


https://github.com/microsoft/markitdown（这个是用来前置处理文档的，包括了mineru也可以）


### 0.2 本轮调研产生的 3 条修正建议（需要反写进其他文档）

1. **Youtu-RAG 评价上调**：之前在 `tech-selection.md` 中记为"单租户 + 本地部署哲学与多租户云部署冲突"。**实际**它是完整多租户 FastAPI 后端（`utu/rag/api/` 下有 `kb_config_routes.py` 49KB + `services/` + `migrations/` + `models/`），**其 API 层架构对我们有直接借鉴价值**，不是只能"仅参考范式"。
2. **PageIndex 独立性**：OpenKB 只是它的 CLI 封装；**PageIndex 本身是独立 pip 包**（VectifyAI / Apache-2.0），我们集成时可以**直接用上游包**，不必走 OpenKB，灵活度更高。
3. **CAG（Prompt Caching）纳入方案**：`assets/cag.md` 讲的 Anthropic/OpenAI prompt caching 范式，对"咨询场景长 system prompt + 顾问范式模板 + 租户静态上下文"的成本 / 延迟优化**价值非常大**，应纳入 P1 优化方向（见 §12）。

### 0.3 三类"知识库构建逻辑"分类

| 范式 | 核心动作 | 代表项目 | 适用场景 |
|---|---|---|---|
| **传统 RAG**（retrieve-and-answer） | 每次查询时临时检索 chunk → LLM 组合答案；无持久化"编译产物" | youtu-rag 的 path-chunk、大多数商业 RAG | 事实型问题、规模大、更新频繁 |
| **LLM Wiki**（compile-once） | 入库时就让 LLM 产出结构化 wiki 页面（summary / concept / comparison），查询时读 wiki | Karpathy gist、rohitg00 v2、llm_wiki（nashsu）、OpenKB | 综合型问题、深度推理、需要跨文档关联 |
| **Reasoning-based**（vectorless） | 长文档切章节树，LLM 在树上推理式导航 | PageIndex / OpenKB path-page | 长 PDF（咨询报告、研究报告） |

**ConsultingBrain 采纳"三者并存"**（见 `docs/architecture.md` §4.1）——这是本报告最核心的结论。

---

## 1. OpenKB（VectifyAI）⭐⭐⭐

### 1.1 定位

**OpenKB (Open Knowledge Base)** — 开源 CLI 工具，把原始文档编译成结构化的、互相引用的 wiki 式知识库。核心技术是 **PageIndex**（同一家 VectifyAI 出品的向量-less 长文档检索）+ LLM 驱动的知识编译。

思想源头：Karpathy 的 LLM Wiki gist。OpenKB 把它做成了可直接 `pip install` 的 CLI 工具。

### 1.2 核心能力

| 能力 | 实现 |
|---|---|
| **短文档处理** | 用 `markitdown`（微软 MIT）转 Markdown，LLM 直接读全文 |
| **长文档处理** | 用 `pageindex` 包构建层次化章节树，LLM 在树上推理检索 |
| **Wiki 编译** | LLM 按 `AGENTS.md` schema 生成 summary / concepts / index / log 等页面 |
| **交互命令** | `openkb init / add / query / chat / watch / lint / list / status` |
| **Prompt Caching** | 编译流程专门设计为"共同 prefix + 并发 step"以吃满 LLM cache（见 compiler.py） |
| **多模型支持** | 通过 LiteLLM 支持 OpenAI / Anthropic / Gemini 等 |
| **Obsidian 兼容** | 输出就是 `.md` + `[[wikilinks]]`，可直接当 Obsidian vault 用 |

### 1.3 知识库构建逻辑

OpenKB 的入库 5 步编译管线（看过 `openkb/agent/compiler.py` 源码确认）：

```
Step 1：构造公共 context A = (schema.md + 文档全文)
Step 2：A → LLM 生成 summary 页（JSON 结构：{brief, content}）
Step 3：A + summary → LLM 规划 concepts（create / update / related 三类）
Step 4：并发调用 LLM（共用 prefix A 吃 cache）生成新 concept + 改写 update 的 concept
Step 5：代码层加 cross-link + 更新 index.md
```

**目录结构**（即知识的组织方式）：

```
wiki/
├── index.md              ← 内容目录（给 LLM 导航用）
├── log.md                ← 操作流水账
├── AGENTS.md             ← schema，告诉 LLM 怎么维护 wiki
├── sources/              ← 原文（markitdown 转换后的全文）
├── summaries/            ← 每文档一份摘要页
├── concepts/             ← 跨文档综合的概念页 ← "重点产物"
├── explorations/         ← 查询结果归档
└── reports/              ← lint 报告
```

**短 vs 长文档处理**：

| 维度 | 短文档 | 长 PDF（≥ 20 页） |
|---|---|---|
| 转换 | markitdown → Markdown | PageIndex → 章节树 + summary |
| 图像 | pymupdf 内联提取 | PageIndex 提取 |
| LLM 读什么 | 全文 | 章节树（而非全文） |

### 1.4 许可证

**Apache-2.0**，商用友好。**代码可直接继承使用**。

### 1.5 对 ConsultingBrain 的启示

**直接采用**：
- PageIndex 的集成方式（但考虑直接用上游 pip 包 `pageindex`，不一定走 OpenKB 的 CLI 壳）
- `compiler.py` 中 5 步 prompt caching 友好的编译管线设计
- 目录结构的"业务产物 vs 系统产物"分层（`sources/` vs `summaries/` vs `concepts/`）
- `AGENTS.md` schema 文件作为"LLM 维护指令"的做法
- `provider/model` 统一模型命名规范（来自 LiteLLM，我们虽不用 LiteLLM 但可沿用命名）

**不采用**：
- CLI 命令形态（我们要做 SaaS）
- LiteLLM 自托管（operator 已拍板用 OpenRouter 直连）
- 本地文件 wiki 产出（我们要存 Postgres/对象存储 + 检索索引）
- 单用户、无权限模型（我们要多租户 + ACL）

---

## 2. Youtu-RAG（腾讯云 ADP）⭐⭐⭐ 【本轮评价上调】

### 2.1 定位

腾讯云 Agent Development Platform 出品的**下一代 Agentic RAG 系统**，宣传口号"Local Deployment · Autonomous Decision · Memory-Driven"。

### 2.2 核心能力（深度看源码后更正）

**✅ 此前低估的一面**：Youtu-RAG **不是单租户 + 本地哲学**，实际是**完整的多租户 FastAPI 后端**。

`assets/youtu-rag/utu/` 里看到：

| 模块 | 说明 |
|---|---|
| `utu/rag/api/main.py` | FastAPI app，集成了 10+ 路由（chat / agent / knowledge_base / file / minio_files / embedding / reranker / kb_config / config / monitor / memory） |
| `utu/rag/api/kb_config_routes.py`（**49.67 KB**） | 知识库配置管理的完整 CRUD + 关联 API |
| `utu/rag/api/services/` | 业务服务层 |
| `utu/rag/api/models/` | Pydantic 模型 |
| `utu/rag/api/migrations/` | 数据库迁移（Alembic） |
| `utu/rag/api/minio_client.py`（22.65 KB） | 专门的 MinIO 客户端 |
| `utu/agents/` | 完整 agent 框架：`simple_agent.py`（23KB）/ `orchestrator_agent.py` / `orchestra_agent.py` / `workforce_agent.py` / `parallel_orchestrator_agent.py` |
| `utu/tools/memory_toolkit.py`（**77 KB**） | 巨大的记忆管理工具集 |
| `utu/rag/knowledge_builder/` | 知识构建管线 |
| `utu/rag/knowledge_retrieval/` | 检索管线（含 Meta Retrieval） |
| `utu/rag/rerankers/` | Reranker 集成 |
| `utu/rag/storage/` | 存储抽象层 |
| `utu/rag/rag_agents/` | RAG 场景专用 Agent |
| `utu/tracing/` | OpenTelemetry instrumentation + db_tracer |

**核心能力一览**（8+ 个 Agent）：

- **Chat Agent**：基础对话 + 短/长期记忆
- **Web Search Agent**：联网搜索
- **KB Search Agent**：向量检索 + rerank
- **Meta Retrieval Agent**：⭐ 带问题意图解析 + metadata filter（对应我们 FEAT-018 Pre-Filter 的思路，可直接借鉴实现细节）
- **File QA Agent**：Python 读取文件
- **Excel Agent**：复杂表格问答（question decomposition + code execution）
- **Text2SQL Agent**：自然语言转 SQL + 执行反思
- **QA Learning**：⭐ 记录问答例子 + 自动学习 Agent 路由策略（对应我们 FEAT-004 黄金范例 + FEAT-010 模板引擎的组合，**非常值得借鉴**）

**双层记忆机制**：
- 短期记忆：Session 内多轮对话
- 长期记忆：跨 Session 的"成功经验"复用（在遇到相似问题时跳过重复计算）

### 2.3 知识库构建逻辑

```
文件上传（支持 PDF/Word/MD/Excel/Image/Database 等 12+ 格式）
   ↓
文档解析（OCR: Youtu-Parsing / HiChunk：层次化切块 / 元数据自动抽取 + summary 自动生成）
   ↓
关联到知识库（支持：文件关联 / 数据库关联 / 例子关联）
   ↓
向量化构建（Youtu-Embedding 2B 参数中文 embedding）
   ↓
查询时：
   问题意图解析（Meta Retrieval Agent）
   → 工具选择（autonomous decision：是否检索？怎么检索？调哪个 Agent？）
   → 向量检索 + metadata filter
   → rerank（jina-reranker-v3 / 自家 reranker）
   → 答案生成 + 长期记忆更新
```

**关键创新**：
- **Autonomous Decision**：Agent 自主决定是否 / 如何检索（不是每次都盲 RAG）
- **Memory-Driven**：相似历史问题可以复用经验（"long-term memory"）
- **Metadata Retrieval**：对"时效性偏好 / 流行度偏好"等问题类型，Recall 从 34.52% 提到 45.21%

### 2.4 许可证

**MIT**，商用友好。**代码可直接继承使用或深度借鉴**。

### 2.5 对 ConsultingBrain 的启示

**直接借鉴（代码级）**：
- `utu/rag/api/` FastAPI 结构组织 → 我们的 `backend/api/` 可参考
- `utu/rag/api/kb_config_routes.py` 的知识库 CRUD + 关联 API → FEAT-017 目录管理直接参考
- `utu/rag/api/dependencies.py` 的 agent 生命周期 + DI 模式 → 我们的 `core/auth` + `core/retrieval` DI 可参考
- Meta Retrieval Agent 的问题意图解析 prompt → 我们 FEAT-018 PermissionResolver + 问题路由可参考
- QA Learning 机制（长期记忆 + Agent 路由学习）→ FEAT-004 黄金范例 + FEAT-010 模板的集成参考点
- `utu/tracing/` 的 OpenTelemetry + db_tracer 配置 → 我们可观测性可参考

**吸收范式（不直接搬代码）**：
- 8 个 Agent 的业务划分（Chat / Web / KB / Meta / File / Excel / Text2SQL / 短长期记忆）
- 双层记忆机制（但我们 MVP 只做短期，长期放 FEAT-013 P1）
- "Autonomous Decision"的 Agent 做法（我们 MVP 先不上，用 DeterministicPipeline 建立基线）

**不采用**：
- `minio_client.py`：operator 2026-04-20 拍板本地 FS，不用 MinIO
- `memory_toolkit.py` 77KB 直接搬：太大；我们先用简单 session store，长期记忆 P1 再做
- 它内置的 `Youtu-Embedding` / `Youtu-Parsing` / `Youtu-HiChunk`：我们用 `bge-large-zh-v1.5` + MinerU/markitdown/PaddleOCR 三选一开关

### 2.6 ⚠️ 需要重点重评的一点

**之前（`tech-selection.md` §2.2）**写的是"单租户 + 本地哲学与多租户云部署冲突"——**此结论部分错误**，需要在下一轮 tech-selection.md 更新时修正为：

> Youtu-RAG 的 `utu/rag/api/` 层已经是完整的多租户 FastAPI 后端，租户 / 用户 / 空间模型清晰，代码可深度借鉴。但它的存储层（MinIO）和模型层（LiteLLM + Youtu 专属模型）与 operator 最新决策不一致，需要替换。

---

## 3. PageIndex（隐藏主角）⭐⭐⭐

### 3.1 定位

VectifyAI 出品的**向量-less 长文档检索引擎**。核心创新：**不用向量，靠 LLM 在章节树上推理式导航**。OpenKB 只是它的 CLI 封装。

### 3.2 核心能力（从 OpenKB/openkb/indexer.py 看到的调用方式）

```python
from pageindex import IndexConfig, PageIndexClient

client = PageIndexClient(api_key=os.environ.get("PAGEINDEX_API_KEY", "") or None)
doc_id = client.add(pdf_path)          # 上传 PDF，自动 OCR + 章节树提取
page_content = client.get_page_content(doc_name, pages=[7, 8, 9])   # 按页取内容
tree = client.get_tree(doc_id)         # 取章节层次树
```

两种部署模式：
- **本地开源版**：无外部依赖（但无 OCR）
- **Cloud 版**（需 `PAGEINDEX_API_KEY`）：支持 OCR + 大文档 + 更快的 TOC 生成

### 3.3 知识库构建逻辑（针对长文档）

```
PDF ≥ 20 页（阈值可配）
    ↓
PageIndex.add(pdf) → 自动：
    1. 页面提取（若云版，还会 OCR 扫描件）
    2. 层次化 TOC（目录树）抽取（TOC 准确性有一定随机性，indexer.py 里做了 3 次 retry 兜底）
    3. 每个节点/子节点生成 summary
    4. 返回 doc_id + tree
    ↓
查询时：
    LLM 读"章节树"（而非全文）→ 推理出应该看哪几页
    → client.get_page_content(doc_name, pages=[...]) 取实际内容
    → LLM 组合答案
```

**为什么不用向量**：长文档切块向量化 + top-K 会把章节结构信息丢掉，导致召回碎片化；章节树保留了"这段在讲什么、属于哪一章"的层次感，更适合推理式问题。

### 3.4 许可证

**Apache-2.0**，商用友好。代码可直接集成。

### 3.5 对 ConsultingBrain 的启示

**直接集成**：我们的 `path-page` 路径就是它（已在 `docs/architecture.md` §4.1 写明）。

**集成细节（从源码读出来的新发现）**：
- `PAGEINDEX_API_KEY` 可选：不设则本地开源版（无 OCR），设则用 Cloud 版（有 OCR）
- TOC 抽取有随机性，建议**入库时 retry 3 次**（OpenKB 就是这样做的）
- 实际调用是简单的 HTTP client 形态，集成代价很低（< 0.5 天）
- 返回的章节树可以存 Postgres（JSONB），不必放本地文件

**注意**：operator 已拍板 MinerU / markitdown / PaddleOCR 三选一做前处理（docs/deployment.md §6）。PageIndex 是**独立的"长文档检索路径"**，与前处理不冲突；前处理负责把 PDF 转成 Markdown（走 `path-chunk` / `path-entry`），PageIndex 负责长 PDF 的**原生结构化检索**（走 `path-page`）。两路并行。

---

## 4. Karpathy LLM Wiki（gist，原始范式）⭐⭐

### 4.1 定位

Andrej Karpathy 2026-01 发布的一篇**范式文档**（不是代码仓库），描述"用 LLM 持续编译 + 维护一个私人 wiki"的核心思想。所有 wiki 方案的思想原点。

### 4.2 核心思想

**"Stop re-deriving, start compiling."**（不要每次重新推导，要一次编译、持续维护）

- **RAG 问题**：每次查询都要从头检索 + 组合答案，没有积累
- **Wiki 解**：LLM 在入库时就把每个 source 读完、写成结构化页面，查询时只读 wiki，答案越来越丰富

### 4.3 三层架构（Three Layers）

```
Raw sources（原始资料）  ← 不可变、人类 curate
    ↓
Wiki（LLM 生成的 Markdown 页面）  ← LLM 全权维护
    ↓
Schema（CLAUDE.md / AGENTS.md）  ← LLM 的"维护指令手册"，与人类共同演化
```

### 4.4 三大操作（Three Operations）

- **Ingest**：读 source → 写 summary → 更新 index / entity / concept 页面 → 追加 log（一份 source 可能改 10-15 个页面）
- **Query**：读 index 找相关页 → 读 相关页 → 综合回答 + 引用；**好答案可以回存为新 wiki 页面**（探索也会 compound）
- **Lint**：定期体检——找矛盾、过时、孤儿页、缺失引用

### 4.5 两个特殊文件

- `index.md`：内容目录（替代 RAG infra，100 source / 几百页规模够用）
- `log.md`：时间线记录（一致前缀便于 `grep | tail` 取最近操作）

### 4.6 许可证

无代码许可证（纯文档）。**思想可自由采纳**。

### 4.7 对 ConsultingBrain 的启示

这份文档是我们 `path-entry`（基于"知识条目"的检索路径）的**设计哲学源头**。我们在 `docs/architecture.md` §3 明确引用了它。

**核心采纳**：
- 三层架构（raw / wiki / schema）的思想 → 我们的"业务视角 vs 检索视角解耦"（§6.5）
- "编译而非检索"（compile, not retrieve）→ `path-entry` 的定义
- Ingest / Query / Lint 三操作 → 我们入库 + 问答 + 夜间 lint 管线
- `index.md` 不一定要放弃：小规模租户内部可用于导航
- 好答案回存 wiki → FEAT-005 资产库 + FEAT-004 黄金范例

**限制**：
- 范式本身不适合 > 100 source 的规模（作者亲口说）——所以我们要在它基础上补 RAG + PageIndex 才能规模化

---

## 5. rohitg00 LLM Wiki v2（gist，进阶范式）⭐⭐

### 5.1 定位

rohitg00（来自 agentmemory 项目）写的 **Karpathy LLM Wiki 的生产级增强版**。把 Karpathy 的范式推进一步，补了"生产实际跑几千会话后发现的缺口"。

### 5.2 增强内容（9 个范式）

1. **Memory Lifecycle**（知识生命周期）：
   - **Confidence scoring**：每条事实带 confidence 分数，随时间衰减、随多源强化
   - **Supersession**：新 claim 显式取代旧 claim，旧 claim 保留但标 stale
   - **Forgetting**（Ebbinghaus 遗忘曲线）：长时间未用 → 淡出（架构决定慢衰减，临时 bug 快衰减）
   - **Consolidation tiers**：Working → Episodic → Semantic → Procedural（四层从原始观察到工作流模式）

2. **Typed Knowledge Graph**：实体抽取 + 类型化关系（"uses" / "depends on" / "contradicts" / "caused" 等），Graph traversal 找下游影响

3. **Hybrid Search**：BM25 + Vector + Graph traversal + RRF（reciprocal rank fusion）

4. **Event-Driven Automation**：On new source / On session start / On session end / On query / On memory write 各种 hook 自动触发

5. **Quality & Self-Correction**：每条内容自评分 + 自动 lint + 矛盾自动消解

6. **Multi-Agent & Collaboration**：多 agent 并发观察合并到 shared wiki，Last-write-wins + 时间戳仲裁

7. **Privacy & Governance**：Ingest 时过滤 API key / PII；全操作审计

8. **Crystallization**：完成的探索链自动蒸馏成 wiki 页面，作为新一层 source

9. **Output Beyond Markdown**：不只 md，也输出 comparison table / timeline / deck / JSON export

### 5.3 许可证

纯文档，无代码。**范式可自由采纳**。

### 5.4 对 ConsultingBrain 的启示

这份是我们 `docs/architecture.md` §3（设计哲学）里很多原则的来源。**直接吸收的内容**：

| v2 范式 | 对应 ConsultingBrain 实现 |
|---|---|
| Confidence scoring | `knowledge_entry.confidence` 字段（MVP 预留 schema，P1 启用） |
| Typed knowledge graph | `KnowledgeGraphNode / Edge` schema（P2 启用） |
| Hybrid search + RRF | `path-chunk` BM25 + 稠密 + RRF（MVP 默认） |
| Event-driven automation | FEAT-011 夜间管线（P1） |
| Quality & self-lint | FEAT-004 黄金范例 + lint（P1） |
| Privacy governance | FEAT-001 审计 + FEAT-008 后台 |
| Crystallization | FEAT-005 资产库的设计目标 |
| Output beyond markdown | FEAT-012 媒体提示词生成（P1） |

**不直接采用**：
- Multi-Agent 合并的 last-write-wins → 我们不做多 Agent 并发维护 wiki（MVP 是 deterministic pipeline）
- Consolidation 的四层 → 对咨询场景过重，P2 视情况

---

## 6. llm_wiki（nashsu，Tauri 桌面应用）⭐⭐

### 6.1 定位

**基于 Tauri 的跨平台桌面应用**，把 Karpathy LLM Wiki 范式做成"开箱即用的桌面软件"。支持 macOS / Windows / Linux。UI 是三栏布局（Knowledge Tree / Chat / Preview）。

### 6.2 核心能力

| 能力 | 实现 |
|---|---|
| **两步链式思考 Ingest** | Analysis 步骤 → Generation 步骤（比 Karpathy 单步更高质量） |
| **SHA256 增量缓存** | 源文件 hash 一致则跳过 |
| **持久化 Ingest 队列** | 串行处理，防止并发 LLM 调用；崩溃可恢复 |
| **4-Signal 相关度模型** | Direct link(×3.0) + Source overlap(×4.0) + Adamic-Adar(×1.5) + Type affinity(×1.0) |
| **Louvain 社区检测** | 自动发现知识聚类（graphology-communities-louvain），带 cohesion 评分 |
| **Graph Insights** | 意外连接 + 知识缺口 + 桥节点，每个 insight 可触发 Deep Research |
| **多阶段检索** | Tokenized search（含 CJK bigram）→ 可选 Vector（LanceDB）→ Graph expansion → Budget Control |
| **Review System** | LLM 标记需人工判断的项，限定 action 类型 |
| **Deep Research** | Tavily web search + LLM 合成到 wiki |
| **Chrome Web Clipper** | 自研 Manifest V3 插件（Readability.js + Turndown.js） |
| **Multi-format** | PDF / DOCX（docx-rs）/ PPTX（XML 解析）/ XLSX（calamine）|
| **技术栈** | Tauri v2（Rust 后端）+ React 19 + TypeScript + Vite + sigma.js + LanceDB |

### 6.3 知识库构建逻辑

```
Raw source（PDF/DOCX/PPTX/XLSX → 结构化 Markdown）
   ↓
Step 1（Analysis）：LLM 读 source → 结构化分析（实体、概念、与现有 wiki 冲突、wiki 结构建议）
   ↓
Step 2（Generation）：LLM 读分析 → 生成 wiki files（source 摘要 / entity 页 / concept 页 / 更新 index/log/overview/review 项）
   ↓
自动 embedding（若开启向量搜索）
   ↓
4-Signal 图谱更新（sources[] / wikilinks / Adamic-Adar / type affinity）
   ↓
Louvain 社区检测自动发现聚类
   ↓
查询时：Tokenized → (可选 Vector) → Graph expansion → Budget-controlled context → LLM 综合答
```

### 6.4 关键约束

作者亲口在 README 里写："**this architecture only suits up to ~40 万字 / ~100 documents**"（40 万字 / 100 篇上限）—— 对 ConsultingBrain 的 1 万份文档规模是**数量级不够**。

### 6.5 许可证

**GPL-3.0 strong copyleft**——**代码不能继承到我们闭源产品**。

### 6.6 对 ConsultingBrain 的启示

**吸收范式（不搬代码）**：
- 两步链式思考 ingest（比单步质量高）→ FEAT-002 的"双阶段摄入" source / summary
- 4-Signal 相关度模型 → FEAT-018 在 P2 启用图谱时的关系权重设计
- Louvain 社区检测 → 离线管线 FEAT-011 可做"知识聚类发现"（P1 扩展）
- Graph Insights（意外连接 + 知识缺口 + 桥节点） → FEAT-011 产物结构的参考
- Review System 的限定 action 类型（create page / deep research / skip） → 我们顾问工作台 FEAT-004 的"纠错 action" 参考
- 2-hop graph expansion with decay → P2 启用图谱后的检索范式

**完全不采用**：
- 代码（GPL）
- 桌面应用形态（我们是 SaaS）
- 40 万字规模上限的架构假设（我们要 1 万份 × 百万字规模）
- 本地 LanceDB（我们用 Milvus）

---

## 7. Obsidian-Brain-OS（FairladyZ）⭐⭐

### 7.1 定位

**数字分身操作系统**——不只是 wiki，更接近"个人 + 团队 AI 工作流操作系统"。以 Obsidian 作为 UI，以 Claude Code / OpenClaw 等 Agent 作为执行体。

作者强调："Brain OS 是 LLM Wiki + 第二大脑 + 24 小时贴身管家 + 有边界的工作分身"。

### 7.2 核心能力

| 能力 | 说明 |
|---|---|
| 多 Agent 团队 | 主 Agent + Writer + Chronicle + Observer + 可扩展 |
| **Observer（自进化观察者）** | 每天检查系统运行状态 / 找重复错误 / 提改进建议 |
| **夜间三阶段流水线**（02:00-04:00） | Article Integration / Conversation Mining / Knowledge Amplification |
| 个人事务系统 | 每日驾驶舱 / 待办 / 承诺跟踪 |
| 提醒事项集成 | Brain ↔ Apple Reminders 双向同步 |
| 边界与治理 | 个人 / 工作 / 团队上下文分层隔离 |

### 7.3 知识架构（三层物理隔离）

```
READING/   ← 人读的（精炼策展）
  ├─ 01-DOMAINS/       领域知识卡
  ├─ 02-TOPICS/        主题聚合页
  ├─ 03-PATTERNS/      验证过的模式卡
  └─ 04-DIGESTS/       ⭐ 每日 digest（用户的入口）
WORKING/   ← AI 的工作坊（原始输入、草稿、候选）
  ├─ 01-ARTICLE-NOTES/
  ├─ 02-PATTERN-CANDIDATES/
  ├─ 03-TOPIC-DRAFTS/
  └─ 04-RESEARCH-QUESTIONS/
SYSTEM/    ← 管线内部（索引、报告、job state、meta）
```

"**Capture Once, Process Forever**" + "**Separate Reading from Working**" 是核心设计原则。

### 7.4 夜间流水线（知识飞轮）

```
22:00  用户白天捕获（文章 / 对话 / 想法）
  │
02:00  ┌─ Article Integration ────────────────┐
       │  读 WORKING/01-ARTICLE-NOTES/         │
       │  写 READING/01-DOMAINS/ + 02-TOPICS/  │
       │  产出：digest 段 + 机器可读 run report  │
       └───────────────────────────────────────┘
  │
03:00  ┌─ Conversation Mining ────────────────┐
       │  读 AI 对话 transcript（近 3 天）       │
       │  写 知识 note 草稿 + pattern candidates│
       └───────────────────────────────────────┘
  │
04:00  ┌─ Knowledge Amplification ────────────┐
       │  读 今日完整 digest                     │
       │  写 跨域连接 + 推荐阅读                  │
       └───────────────────────────────────────┘
  │
05:00  可选 Knowledge graph canvas
07:00  Morning Brief（给 Personal Ops）
  │
08:00  用户醒来，看 digest
```

**关键设计**：每阶段隔离（失败不相互影响）；空跑写 no-op 报告；全量 git commit。

### 7.5 许可证

**MIT**，商用友好。**代码可参考使用**。

### 7.6 对 ConsultingBrain 的启示

**FEAT-011（P1 离线批处理管线）直接以此为蓝本**。

**吸收到我们系统**：
- 三阶段夜间流水线结构（Article Integration / Conversation Mining / Knowledge Amplification）
- "每阶段隔离会话"的工程纪律（失败不互相影响）
- "空跑写 no-op 报告"的做法
- "READING vs WORKING vs SYSTEM" 三层物理隔离 → 我们"业务可见区 / 离线产物区 / 系统内部区"
- Observer Agent 范式（系统自己监控自己）→ 我们 FEAT-011 的"元层监控"
- Digest 作为用户入口 → 顾问工作台的"每日洞察" UI 可参考
- 边界治理（个人 / 工作 / 团队分层） → 对应我们的租户 / 空间 / 可见范围三元组

**不采用**：
- 以 Obsidian 为 UI（我们做 SaaS Web）
- Apple Reminders 集成（咨询场景不需要）
- 以 cron + Claude Code 的部署形态（我们用 Celery + APScheduler）
- 单用户、无租户模型（我们 SaaS 多租户）

---

## 8. workshop-agentic-search（Weaviate / Elastic）⭐

### 8.1 定位

Weaviate / Elastic 团队出品的 **Agentic Search 教学 notebook**。教人怎么用 LangChain + 各种工具做"Agent 自主决定怎么检索"。不是生产级项目。

### 8.2 核心内容

3 个 Jupyter Notebook，每个展示一种"上下文工程 + 检索工具"的组合：

| Topic | Context source | Retrieval tool |
|---|---|---|
| 01 Vanilla Agentic Search | 本地 Elasticsearch | Semantic search tool |
| 02 Agentic Search with DB query | 本地 Elasticsearch | ESQL Query execution tool + Agent Skills |
| 03 Agentic Search with Shell | 本地 filesystem | Shell tool + jina-grep-cli |

数据集：AI Engineer Europe Conference schedule（`data/session.json`）—— 演示用。

### 8.3 知识库构建逻辑

没有自己的"知识库构建"逻辑——它是演示如何**在已有数据源上做 agentic retrieval**：
- 数据源可以是 DB / 文件系统 / 向量库
- Agent 自主决定调用哪个工具（semantic / 精确查询 / shell / grep）
- LangChain 做 Agent 编排

### 8.4 许可证

MIT（教学用），无约束。

### 8.5 对 ConsultingBrain 的启示

**仅吸收范式**：
- Agent + 多工具箱 模式（semantic + DB + shell + grep）→ FEAT-013（P1）顾问专家 Agent 的工具集设计
- "shell 工具不是银弹"的反思（参考资源链接）

**完全不直接用**：
- 不上 LangChain（operator 已定 MVP 用自建 DeterministicPipeline）
- 不直连 Elasticsearch（我们通过 RetrievalGateway 统一入口）

---

## 9. enso-os ❌ 不相关（已排除）

### 9.1 定位

**Agent 纪律系统**（不是知识库）。包装在 Claude Code / Gemini CLI / Hermes / OpenClaw 等 AI Agent 外面，添加"代码强制的错误学习、主动遗忘、自我保护"。

作者原话：**"Enso is not a memory system. It's a discipline system."**

### 9.2 核心能力

10 个 lifecycle hooks，4 层（Immutable / Learning / Memory / Guard）：

```
Error → Capture（代码强制）→ Distill（异步）→ Store → Inject next session → Avoid
```

- **Immutable 层**：写入必须校验 / 不能修改自己的规则 / session end 审计（3 hook）
- **Learning 层**：记录每次工具调用 / 捕获错误 / 蒸馏教训（3 hook）
- **Memory 层**：下一次 session 注入教训
- **Guard 层**：内存预算上限 / 阻止泄密/注入 / 自动维护（3 hook）

主动遗忘：37 天未用 lesson 删除；> 50 个 lesson LRU；trace > 14 天删除。

### 9.3 许可证

MIT。

### 9.4 为什么排除

**和我们产品完全无关**——它管的是 AI 开发 Agent 的"纪律"，不是咨询公司的文档问答。

**唯一潜在用途**：如果我们将来搭建自己的 Dev Agent（帮助 arch/pm/dev sub-agents 运行时执行纪律）可以参考。但跟 ConsultingBrain 产品本身零关系。

---

## 10. gstack ❌ 不相关（已排除）

### 10.1 定位

Garry Tan（Y Combinator CEO）的**个人 AI 工程团队 skill 包**——把 Claude Code 包装成 23 个虚拟角色（CEO / Eng Manager / Designer / Reviewer / QA / CSO / Release Engineer 等）+ 8 个 power tool 的 skill 集合。

典型用法：`/office-hours`（讨论需求）/ `/plan-ceo-review`（CEO 视角评审）/ `/review`（代码评审）/ `/qa`（QA 用真实浏览器测）/ `/ship`（发布）。

### 10.2 核心能力

- 23 个 `.md` skill 文件，每个定义一个虚拟角色 + prompt
- 8 个 power tool（含 `/browse` 浏览器自动化）
- 团队模式 + 自动更新机制
- 适配 Claude Code / OpenClaw 等 Agent 宿主

### 10.3 许可证

MIT。

### 10.4 为什么排除

**跟知识库完全无关**——它是"如何用 AI Agent 像一个工程团队一样做软件"的方法论 + 工具集。

**唯一潜在用途**：我们自己的 `.ocp_harness/` 多 Agent 协作框架设计可以参考它的 skill 组织方式，但跟 ConsultingBrain 产品本身零关系。

---

## 11. CAG / Prompt Caching 技术范式（assets/cag.md）⭐

### 11.1 定位

不是 GitHub 仓库，是一篇技术文章（operator 保存在 `assets/cag.md`）。讲两件事：

1. **CAG（Cache-Augmented Generation）** = RAG + 直接把静态高价值知识缓存到模型的 KV memory 里
2. **Prompt Caching 工程学**（以 Claude Code 达到 92% cache 命中率为例）

### 11.2 核心思想

**RAG 的问题**：每次查询都查向量库，对"几个月没变"的静态信息来说是浪费。

**CAG 解**：
- **静态层**（政策、文档、方法论）：一次性缓存到 KV memory
- **动态层**（最近更新、实时文档）：走 RAG 检索
- 结果：更快 / 更便宜 / 冗余更少

**关键约束**：只缓存**静态、高价值、很少变**的知识。全缓存会爆上下文窗口。

### 11.3 Prompt Caching 工程经济学（Claude Code 92% 案例）

- Cache 读：0.1× 基准价格（90% 折扣）
- Cache 写：1.25× 基准价格（25% 溢价）
- 1h 扩展缓存：2.0×

**实际效果**：20,000 token 系统 prompt + 50 turn 会话 → 1.84M token 缓存读 + 160K token 动态计算 → **$1.15（vs 无缓存 $6.00，省 81%）**

### 11.4 三大工程纪律（缓存的"脆弱性"）

1. **不要 session 中间改工具**：工具定义是缓存 prefix 一部分，改动即全部失效
2. **不要中途切模型**：cache 是模型特定的
3. **不要 mutate prefix 更新状态**：要改状态追加到 user message 尾部，别改 system prompt

Prompt 结构建议：
```
1. 系统指令 + 行为规则（最上）← 不要中途改
2. 工具定义（上）← 一次加载全部
3. 检索 context + 引用文档（中）← 会话内稳定
4. 对话历史 + 工具输出（下）← 动态追加
```

### 11.5 对 ConsultingBrain 的启示（⭐⭐ 本轮新发现）

**咨询场景是 Prompt Caching 的理想适用场景**：
- 系统 prompt 长（含 G1-G6 规则 + 租户上下文 + 顾问范式模板）
- 同一顾问/高管会话多 turn（反复问问题）
- 租户静态信息（"本租户行业是金融 + 人寿保险，标准方法论是 PEST / 波特五力"）跨 session 稳定

**建议加入架构**（可追加到 `docs/architecture.md`）：

| 建议 | 说明 | 阶段 |
|---|---|---|
| **MVP**：QA Pipeline 的 Prompt 结构严格按 CAG 四层分层（system / tools / retrieved context / history） | 零成本（只是写法纪律）；为后续 caching 铺路 | MVP |
| **MVP**：所有 LLM 调用不得在 session 中改模型 | 纪律 | MVP |
| **P1**：给 OpenRouter 请求加 `cache_control` 标记（Anthropic 模型原生支持，OpenAI 模型自动缓存） | 实际开启 prompt caching | P1 |
| **P1**：租户级"静态上下文"单独缓存（行业 + 方法论模板 + 全局基本库目录 TOC） | 命中率可期达到 80%+ | P1 |
| **P2**：引用材料（长文档 chunks）做分 breakpoint 缓存 | 对"同一文档反复被多个用户问"的场景降本 | P2 |
| **监控**：每次 API 响应追踪 `cache_creation_input_tokens / cache_read_input_tokens` | 在 FEAT-007 用量统计中加一个"cache 效率"维度 | P1 |

**成本预估**（以 Claude Sonnet 4.5 为例）：
- MVP：20K 系统 prompt × 每用户日均 20 query × 1000 用户 → $600/月 不启用 caching；启用后理论 **降至 $130/月**
- 如果加上引用材料缓存（每文档 5K tokens × 100 热门文档），潜在月省更多

### 11.6 CAG 与 RAG 的边界（对我们三路径的启示）

| 路径 | 适合什么 | 是否适合 CAG 化 |
|---|---|---|
| path-chunk（向量检索） | 事实型细节查询、动态内容 | ❌ 动态，不该缓存 |
| path-entry（知识条目） | 方法论、概念、综合视角 | ⚠️ 部分条目（如全局方法论）✅；租户私有条目 ❌ |
| path-page（PageIndex 长文档） | 咨询报告原文追溯 | ⚠️ 热门文档的章节树 ✅；冷门文档 ❌ |
| **全局基本库目录 TOC** | 导航 + context | ✅ 强烈推荐缓存 |
| **系统 prompt + G1-G6 规则** | 每次都要读 | ✅ 强烈推荐缓存 |

---

## 12. 总结：建议最终吸收清单（一页汇总）

### 12.1 直接继承代码（Apache-2.0 / MIT，合规友好）

| 来源 | 继承内容 | 合规 |
|---|---|---|
| **PageIndex**（独立 pip 包） | 长文档检索，`path-page` 路径 | Apache-2.0 ✅ |
| **OpenKB compiler.py** | 5 步 prompt caching 友好的编译管线设计 | Apache-2.0 ✅ |
| **markitdown** | 通用文档解析（L1 候选之一） | MIT ✅ |
| **Youtu-RAG `utu/rag/api/` 架构** | FastAPI 路由组织 / DI 模式 / tracing | MIT ✅ |
| **Youtu-RAG Meta Retrieval Agent prompt** | 问题意图解析 | MIT ✅ |

### 12.2 吸收范式，自研实现

| 范式 | 应用 FEAT |
|---|---|
| Karpathy 三层架构（raw / wiki / schema） | 全系统哲学，`docs/architecture.md` §3 |
| Karpathy "编译而非检索" | `path-entry` 定义 |
| rohitg00 v2 confidence / supersession / forgetting | `knowledge_entry` schema 预留字段，P1 启用 |
| rohitg00 v2 hybrid search + RRF | `path-chunk` MVP 实现 |
| llm_wiki(nashsu) 两步链式 ingest | FEAT-002 source + summary 双阶段 |
| llm_wiki(nashsu) 4-signal graph 模型 | P2 图谱启用时的关系权重 |
| Obsidian-Brain-OS 三阶段夜间流水线 | FEAT-011（P1） |
| Obsidian-Brain-OS READING vs WORKING vs SYSTEM 隔离 | 全系统数据分区 |
| Youtu-RAG 双层记忆 | FEAT-013（P1 顾问专家 Agent）设计 |
| Youtu-RAG QA Learning | FEAT-004 黄金范例 + FEAT-010 模板集成 |
| **CAG / Prompt Caching 纪律**（本轮新增） | QA Pipeline Prompt 分层结构（MVP）+ cache_control 标记（P1） |

### 12.3 完全排除

| 项目 | 原因 |
|---|---|
| enso-os | Agent 纪律系统，与产品无关 |
| gstack | Claude Code skill 包，与产品无关 |
| llm_wiki(nashsu) 代码本身 | GPL-3.0 不能商用 |
| Karpathy gist 的"index.md 替代 RAG"做法 | 仅适合 100 source 以下规模 |
| Weaviate workshop 的 LangChain 用法 | operator 已定不上 LangChain |

---

## 13. 本次调研产生的文档变更建议

以下内容 arch-01 建议落盘更新（待 operator 批准）：

### CR-003（建议）

1. **`docs/research/tech-selection.md` §2 更正 Youtu-RAG 评价**：从"单租户哲学与多租户冲突"改为"其 API 层实际是多租户 FastAPI 后端，可深度借鉴"
2. **`docs/architecture.md` 加入 §4.8（或 §5.2 扩展）CAG / Prompt Caching 架构建议**：系统 prompt 分层纪律 + OpenRouter cache_control 预留
3. **`tasks/backlog/FEAT-003` 技术备注** 追加：Prompt 结构严格按 CAG 四层分层（MVP 纪律）
4. **`tasks/backlog/FEAT-007` 技术备注** 追加：增加 cache 效率监控维度（`cache_creation_input_tokens / cache_read_input_tokens`）
5. **新建 `tasks/backlog/FEAT-019-prompt-caching-optimization.md`**（P1）：OpenRouter cache_control + 租户静态上下文缓存 + 效率监控面板

**是否做 CR-003 请 operator 指示**；本调研报告本身是**独立交付物**，上述只是基于调研发现的扩展建议，arch-01 不擅自修改产品方案。

---

## 14. 相关文档

- 架构主文：[docs/architecture.md](../architecture.md)
- 选型结论：[docs/research/tech-selection.md](tech-selection.md)
- MVP 清单：[docs/mvp-feature-list.md](../mvp-feature-list.md)
- 部署文档：[docs/deployment.md](../deployment.md)

### 调研数据源（本报告直接引用过的文件）

- `assets/youtu-rag/README.md` + `utu/rag/api/main.py` + 源码树
- `assets/llm_wiki/README.md`
- `assets/OpenKB/README.md` + `openkb/agent/compiler.py` + `openkb/indexer.py`
- `assets/Obsidian-Brain-OS/README.md` + `docs/architecture.md` + `docs/nightly-pipeline.md`
- `assets/442a6bf555914893e9891c11519de94f/llm-wiki.md`（Karpathy）
- `assets/2067ab416f7bbe447c1977edaaa681e2/llm-wiki.md`（rohitg00 v2）
- `assets/workshop-agentic-search/README.md`
- `assets/enso-os/README.md`
- `assets/gstack/README.md` + `DESIGN.md`
- `assets/cag.md`（CAG / Prompt Caching 文章）
