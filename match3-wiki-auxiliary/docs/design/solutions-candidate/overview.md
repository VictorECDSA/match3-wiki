# 三消知识库系统

**系统设计方案总览 · 4 种方案对比**

2026-04-21 · 基于 yupi.md RAG 技术体系

`Q&A 问答` `Wiki 页面` `动态资料摄入` `多模态` `多用户` `高召回率 RAG`

---

## 一、需求全景

| 功能维度 | 具体需求 | 技术挑战 |
|---|---|---|
| **Wiki 页面层** | 结构化知识页面浏览、编辑、版本管理 | Markdown 渲染 + frontmatter 管理 + 权限控制 |
| **Q&A 问答层** | 基于知识库的自然语言问答，答案可溯源 | RAG 检索精度 + 来源引用 + 幻觉控制 |
| **动态资料摄入** | 随时加入 URL/PDF/视频/图片等到知识库 | 多格式解析 + 自动分块向量化 + 即时生效 |
| **多模态支持** | 图表、截图、视频帧、PDF 内嵌图片可检索 | 视觉 Embedding + 图文混排解析 |
| **多用户** | 不同角色（管理员/编辑/读者）权限不同 | 认证授权 + 工作空间隔离 + 审计日志 |
| **高召回率 RAG** | 复杂问题（跨文档推理、术语精确匹配） | Hybrid Search + Reranking + GraphRAG |

---

## 二、RAG 技术选型矩阵

根据 yupi.md 中的 16 种 RAG 方案，针对三消知识库的特点选取最合适的组合：

### ✅ Hybrid Search（必选）

向量语义检索 + BM25 关键词检索并行，RRF 融合。解决"CPI 4012 错误"这类专有名词精确匹配失效的问题。

### ✅ Reranking（必选）

Cross-Encoder 精排，从 Hybrid Search 捞出的 50-150 个候选中筛出真正相关的 5-10 个。生产环境必备。

### ✅ Parent-Child Retrieval（必选）

小块精确匹配，返回所属大块上下文。三消 Wiki 页面结构化强，适合分层索引。

### ✅ GraphRAG（推荐）

游戏/公司/机制实体关联图。回答"哪些游戏用了 X 机制且 UA 策略相似"需要跨文档多跳推理。

### ✅ Adaptive RAG（推荐）

路由器判断问题复杂度，简单问题直接回答，复杂问题走完整 Pipeline，降低延迟和成本。

### ✅ Multi-Agent RAG（高级）

Router + Wiki Agent + Market Agent + UA Agent + Verifier，各司其职，适合多数据源场景。

### ✅ Multimodal RAG（必选）

图表/截图/PDF 图片 Embedding，视觉语言模型生成回答。三消 GDC 演讲有大量图表。

### ✅ CRAG（推荐）

检索结果质检 + 回退 Web 搜索兜底。知识库内容不够时自动补充，保证召回率。

### ⚡ Speculative RAG（可选）

多小模型并行生成草稿，大模型验证。延迟敏感时使用，降低响应时间约 30-40%。

---

## 三、四种方案概览

### 方案 A — 全栈自研平台（Full-Stack Custom Platform）🏆 功能最全

从头自建，完全掌控每一层。前端 Next.js + 后端 FastAPI + Milvus 向量库 + Neo4j 图数据库 + PostgreSQL 元数据。

`Next.js` `FastAPI` `Milvus` `Neo4j` `Multi-Agent RAG` `GraphRAG`

| 维度 | 评分 |
|---|---|
| 功能完整 | ★★★★★ |
| 可定制性 | ★★★★★ |
| 启动速度 | ★☆☆☆☆ |
| 运维成本 | ★★★☆☆ |

⏱ 预计 12-16 周 · 👤 需 2-3 人开发

[→ 查看详细方案](solution-a-fullstack.md)

---

### 方案 B — Dify 低代码平台（Dify-Based Low-Code）⭐ 推荐首选

以 Dify 开源平台为核心，自托管部署。内置多用户、混合检索、工作流编排，配合 Obsidian 做 Wiki 编辑层。

`Dify` `Obsidian` `Docusaurus` `Hybrid Search` `Workflow RAG`

| 维度 | 评分 |
|---|---|
| 功能完整 | ★★★★☆ |
| 可定制性 | ★★★☆☆ |
| 启动速度 | ★★★★★ |
| 运维成本 | ★★★★★ |

⏱ 预计 3-4 周 · 👤 1 人可完成

[→ 查看详细方案](solution-b-dify.md)

---

### 方案 C — RAGFlow + Obsidian（RAGFlow Hybrid Stack）

RAGFlow 专注深度文档解析（PDF/表格/图表），Obsidian 保持 Wiki 编辑体验，Docusaurus 对外发布。三层分工明确。

`RAGFlow` `Obsidian` `Docusaurus` `Deep Document Parse`

| 维度 | 评分 |
|---|---|
| 功能完整 | ★★★★☆ |
| 文档解析 | ★★★★☆ |
| 启动速度 | ★★★★☆ |
| 运维成本 | ★★★☆☆ |

⏱ 预计 4-6 周 · 👤 1-2 人

[→ 查看详细方案](solution-c-ragflow.md)

---

### 方案 D — 轻量本地栈（Lightweight Local Stack）💻 本地优先

LlamaIndex + Chroma + Streamlit，全本地运行。零云成本，数据完全私有，适合个人启动或快速验证 RAG 效果。

`LlamaIndex` `Chroma` `Streamlit` `MkDocs` `本地 LLM`

| 维度 | 评分 |
|---|---|
| 功能完整 | ★★★☆☆ |
| 数据私有 | ★★★★★ |
| 启动速度 | ★★★★★ |
| 零成本 | ★★★★★ |

⏱ 预计 1-2 周 · 👤 1 人可完成

[→ 查看详细方案](solution-d-lightweight.md)

---

## 四、全面对比表

| 维度 | 方案 A 全栈自研 | 方案 B Dify ⭐ | 方案 C RAGFlow | 方案 D 轻量栈 |
|---|---|---|---|---|
| **Wiki 页面** | 自研编辑器 + MDX | Obsidian + Docusaurus | Obsidian + Docusaurus | Markdown + MkDocs |
| **Q&A 界面** | 自研 Chat UI | Dify Chat 内置 | RAGFlow Chat | Streamlit Chat |
| **Hybrid Search** | ✅ 完全自定义 | ✅ 内置开箱即用 | ✅ 内置 | ✅ LlamaIndex 实现 |
| **Reranking** | ✅ Cohere/BGE | ✅ 内置支持 | ✅ 内置 | ✅ BGE-reranker |
| **GraphRAG** | ✅ Neo4j + 自研 | ⚠️ 需自定义工作流 | ⚠️ 需外接 | ⚠️ LlamaIndex Graph |
| **Multi-Agent** | ✅ 完全自定义 | ✅ Dify Workflow | ⚠️ 有限支持 | ⚠️ 基础支持 |
| **多模态（图片/PDF图）** | ✅ CLIP + GPT-4V | ✅ 支持视觉模型 | ✅ 深度文档解析 | ⚠️ 基础支持 |
| **动态资料摄入** | ✅ 全格式 Pipeline | ✅ 上传 UI + API | ✅ 内置 Pipeline | ✅ Python 脚本 |
| **多用户 + RBAC** | ✅ 完全自定义 | ✅ 内置 Workspace | ✅ 内置团队 | ⚠️ 基础 Auth |
| **CRAG（Web 兜底）** | ✅ | ✅ Workflow 实现 | ⚠️ 需配置 | ✅ LlamaIndex |
| **Adaptive RAG 路由** | ✅ | ✅ Dify Condition | ⚠️ | ✅ |
| **数据私有化** | ✅ 自托管 | ✅ 自托管 | ✅ 自托管 | ✅ 完全本地 |
| **启动时间** | 12-16 周 | 3-4 周 | 4-6 周 | 1-2 周 |
| **开发人力** | 2-3 人 | 1 人 | 1-2 人 | 1 人 |
| **月运维成本** | $200-500（云服务器） | $50-150（VPS） | $80-200（VPS） | $0（本地） |

---

## 五、决策指南

| 条件 | 推荐方案 |
|---|---|
| 如果你是个人启动 | → **方案 D 轻量栈**：1-2 周跑通，先验证内容价值，再升级 |
| 如果你要快速上线 | → **方案 B Dify**：3-4 周可用，功能完整，1 人可维护，强烈推荐 |
| 如果有大量 PDF/GDC 演讲 | → **方案 C RAGFlow**：深度文档解析是其核心优势，表格/图表识别最强 |
| 如果要完全自定义 UI/UX | → **方案 A 全栈自研**：完全掌控，但需要 12+ 周和 2-3 人 |
| PRD Phase 1 冷启动阶段 | → **方案 D → 方案 B 迁移路径**：先用 D 建 30 篇内容，再用 B 发布 |
| PRD Phase 3 对外发布 | → **方案 B 或 A**：Docusaurus 建站 + 完整 RAG 查询 API |

---

## 六、推荐演进路径

> 针对 PRD 的四阶段计划，推荐以下演进路径，避免早期过度投入架构，内容优先。

| PRD 阶段 | 推荐方案 | 重点 |
|---|---|---|
| **Phase 1（第 1-8 周）** 高质量内容优先 | 方案 D 轻量栈 | 快速建立 30+ 篇 Wiki，验证内容价值；本地 RAG 问答测试召回效果 |
| **Phase 2（第 9-16 周）** 扩展品类 + 图谱化 | 迁移至方案 B (Dify) 或方案 C (RAGFlow) | 引入多用户协作；建立 GraphRAG 层；接入图表/PDF 多模态解析 |
| **Phase 3（第 17 周+）** 发布与可见度 | 方案 B + Docusaurus | Docusaurus 对外发布 Wiki；Dify API 对外提供 Q&A；SEO 优化 |
| **Phase 4（持续运营）** 或有更高需求 | 升级至方案 A | 若需要完全定制 UI/商业化，再投入全栈自研 |

---

文档版本 v1.0 · 2026-04-21 · 配套文件：
[方案 A](solution-a-fullstack.md) · [方案 B](solution-b-dify.md) · [方案 C](solution-c-ragflow.md) · [方案 D](solution-d-lightweight.md)
