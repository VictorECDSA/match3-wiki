# 工具链取舍说明

本文对照 PRD（`match3-wiki-prd.html`）第六节「工具链方案」中列出的所有工具、组件及 PageIndex，逐一说明在 match3-wiki 技术设计中是否采用，以及背后的决策理由。对于已采用的工具，说明具体在系统哪个模块哪个环节发挥什么作用、不用它会怎样，以及有哪些同类可靠替代方案；对于未采用的工具，说明若要集成进来需要怎样调整方案。

---

## 一、已采用的工具 / 组件

### 1. PageIndex（VectifyAI → pageindex.ai）

**在系统中的位置与作用**

PageIndex 在系统中介入两个不同阶段，缺一不可：

**摄取阶段**（Ingest Worker）：所有 PDF 均走 markitdown → 语义分块 → embed（Milvus/ES）→ 图谱抽取（Neo4j）的完整流水线。当 PDF 文件页数 ≥ 20 时，`ingest_task` **额外**（并行，不影响分块结果）调用 `_register_pageindex()`：将文档上传至 PageIndex API，获得一个 `doc_id` 和分层目录树（TOC Tree），分别写入 `t_raw_files.f_pageindex_doc_id` 和 `t_raw_files.f_pageindex_tree`。这是一个**附加**动作，大型 PDF 同时具备 hybrid-search 和 doc-navigate 两条检索路径。

**检索阶段**（QAService → doc-navigate 路径）：用户提问时，`QAService._select_path()` 检查 `raw_file.pageindex_doc_id` 是否存在，若存在则进入 doc-navigate 路径。`PageIndexRetriever` 让 LLM 在 TOC Tree 上导航——反复问"哪个章节最相关"——最终定位到具体页面，调用 `client.chat_completions()` 检索页面内容并流式输出答案。同一文档的 hybrid-search 路径（分块向量检索）也始终可用，路由器根据查询类型自动选择最合适的路径。

**不用它会怎样**：大型 PDF 失去 doc-navigate 路径，只能走 hybrid-search 分块检索。对于"第三章关于留存率的完整论述"这类需要完整章节上下文的问题，分块后跨章节的逻辑关系被割裂，LLM 拿到的是零散片段而非完整章节，答案质量显著下降。doc-navigate 路径整体消失，Q&A 路由器的三条路径变成两条。

**同类可靠替代方案及利弊**：

| 替代方案 | 优势 | 劣势 |
|---|---|---|
| **LlamaIndex HierarchicalNodeParser**（自建） | 完全自控、无外部 API 依赖、可离线部署 | 需自行实现 TOC 提取与章节路由，工程量大，对无规范目录的 PDF 效果差 |
| **传统向量分块（Milvus ANN）** | 复用现有 hybrid-search 基础设施，零额外依赖 | 跨章节推理能力弱，无法精确定位页码来源 |
| **Azure Document Intelligence** | OCR + 版面分析能力强，支持表格/图形提取 | 约 $1.5/1000 页，侧重结构提取而非推理检索 |

**换用建议**：若需消除外部 API 依赖，可用 LlamaIndex `HierarchicalNodeParser` 自建，但需额外投入 2~3 周，且 doc-navigate 路径的实现逻辑需完整重写。

---

### 2. Whisper（OpenAI Whisper large-v3）

**在系统中的位置与作用**

Whisper 是摄取管线中处理音视频文件的唯一入口，位于 Ingest Worker 的 `_parse_audio` 和 `_parse_video` 分支内：

**音频文件**（`.mp3 / .wav / .m4a / .ogg`）：`_parse_audio` 将文件写入临时路径后直接调用 `_transcribe_audio()`，Whisper 输出转写文本，随后送入 `_semantic_chunk()` 分块，最终写入 PostgreSQL、Milvus、Elasticsearch，参与正常检索流程。

**视频文件**（`.mp4 / .mov / .avi / .mkv`）：`_parse_video` 先用 ffmpeg 从视频中提取音轨（16kHz 单声道 WAV），再调用 `_transcribe_audio()` 转写；同时以 1fps 提取关键帧（最多 50 帧，实际送给 GPT-4V 处理前 10 帧）。音轨转写文本和关键帧描述分别生成 TEXT chunk 和 IMAGE chunk，都进入检索系统。

**不用它会怎样**：`_parse_audio` 和 `_parse_video` 两个分支无法完成，对应文件的摄取任务直接 FAILED。所有游戏试玩解说视频、行业播客、展会演讲录音的内容完全无法进入知识库——不是检索质量下降，是根本没有内容可检索。对于三消游戏情报库来说，买量素材视频、竞品试玩录屏、UA创意分析视频的音频内容全部丢失。视频文件仍可提取关键帧（CLIP + GPT-4V 路径不依赖 Whisper），但音频内容为零。

**同类可靠替代方案及利弊**：

| 替代方案 | 优势 | 劣势 |
|---|---|---|
| **faster-whisper**（SYSTRAN/faster-whisper） | 同权重，CTranslate2 推理速度快 4–8 倍，显存更低 | 无说话人分离（diarization）能力 |
| **WhisperX**（m-bain/whisperX） | 词级时间戳 + 说话人分离（pyannote.audio），适合多人播客 | 依赖 Hugging Face token，配置更复杂 |
| **Deepgram Nova-2**（云 API） | 极快，支持实时流式，REST/WebSocket 双接口 | 约 $0.0043/分钟，音频上传第三方 |
| **AssemblyAI**（云 API） | 内置 LeMUR 功能（摘要、章节划分） | 约 $0.37/小时，延迟高于 Deepgram |

**换用建议**：若摄取量大，可将 `_get_whisper_model()` 内的模型替换为 **faster-whisper**，两者输出格式相同，`_transcribe_audio()` 接口无需修改，改动成本极低。

---

### 3. 数据来源平台（Facebook Ad Library / TikTok Creative Center / Sensor Tower / AppMagic / MobileAction / DataEye）

**在系统中的位置与作用**

这些平台是系统的**内容来源**，而非系统内部组件。它们不出现在任何 Worker 或 Service 的代码路径中。运营人员从这些平台手动导出 PDF/CSV 后，通过 `POST /api/v1/ingest/upload` 接口上传，同时在 `tags` 字段中标注数据来源（如 `["market/sensor-tower", "entities/royal-match"]`）。摄取管线不区分来源，统一处理。

**若要更紧密集成**：可新增 Celery 定时任务（如 `ingest_from_sensor_tower`），对接各平台 Open API 定期拉取数据后自动写入摄取管线，无需改动核心 RAG 架构，改动范围仅限新增 Worker task。

---

### 4. markitdown（Microsoft）

**在系统中的位置与作用**

markitdown 是摄取管线的"格式统一层"，位于 Ingest Worker 的文档解析分支中，将多种格式转换为统一的 Markdown 文本供后续分块使用：

- **所有 PDF**：`_parse_pdf_markitdown()` 调用 `MarkItDown().convert(pdf_path)`，输出 Markdown 后送入 `_semantic_chunk()`；页数 ≥ 20 的 PDF 在此基础上**额外**注册 PageIndex（附加行为，不影响分块流程）
- **DOCX / PPTX / HTML**：`_parse_markitdown()` 分支，逻辑相同
- **HTML 网页剪藏**：同上

Markdown 和 CSV 格式不经过 markitdown（前者直接解析，后者走 `_parse_tabular()`）。

**不用它会怎样**：PDF、Word 文档、PowerPoint、HTML 网页剪藏全部无法解析，对应摄取任务 FAILED。这意味着大量行业报告、竞品分析 PPT 无法进入知识库。系统事实上退化为只能处理图片、音视频和纯文本，文档类内容覆盖大幅缩水。

**同类可靠替代方案**：IBM Docling（结构还原更优，表格/公式支持好）、MinerU（多语言 OCR 强）——两者可替换 markitdown，接口层只需修改 `_parse_markitdown()` 的调用方式。

---

## 二、未采用的工具 / 组件

### 1. nvk/llm-wiki（及同类 LLM-Wiki 工具）

**未采用原因**：单机命令行工具，架构上无法支撑多租户并发与状态管理

llm-wiki 是本地命令行工具，适合单人在本机批量生成静态 Markdown 文件。match3-wiki 的 Wiki 编译需要多租户隔离、并发控制、状态追踪（compiling / ready / failed）、强制重编译触发——这些均通过 `WikiCompileService` + Celery `wiki_compile_task` 实现，与数据库和工作区深度耦合，无法直接套用命令行工具。

**若要集成进来，需要这样调整**：

llm-wiki 的五步编译管线（收集上下文 → 摘要 → 概念规划 → 并行章节生成 → 交叉链接）与 `030-rag/processing/wiki-compile.md` 中自研的 OpenKB 流程高度同构。若要引入 llm-wiki 作为编译引擎：

1. 将 llm-wiki 封装为 `wiki_compile_task` 内的一个调用，输入 `workspace_id + topic + chunks`，输出 Markdown 字符串
2. 将 llm-wiki 的文件系统输出（写 `.md` 文件）改为写入 `t_wiki_pages.f_content`
3. 在外层补齐多租户隔离和状态管理逻辑

改动量：中等（约 1 周），主要风险是提示词格式与现有输出 Schema 的对齐。

---

### 2. Graphify（safishamsi/graphify）

**未采用原因**：面向代码库，与本项目的文本实体提取需求不匹配

Graphify 的核心是对代码库（Python/JS/Go）做 Tree-sitter AST 分析后构建知识图谱。match3-wiki 的图谱需求是从游戏行业文本中提取 `Game / Company / Mechanic / Hook` 等业务实体，属于语义 NLP 提取，与代码静态分析路径根本不同。现有 `graph_task` 已实现 LLM 抽取实体关系 → 写入 Neo4j 的完整流程。

**若要集成进来，需要这样调整**：

Graphify 的 `--neo4j` 导出模式支持对文本做语义节点/边生成，理论上可替换现有实体提取步骤：

1. 在 `graph_task` 的实体提取阶段，以子进程方式调用 Graphify，传入文本内容
2. 对 Graphify 输出的 Cypher 语句或 `graph.json` 加上 `workspace_id` 前缀，避免跨工作区污染
3. 由于 Graphify 不原生支持多租户命名空间，需外层包装

主要挑战：Graphify 用于纯文本语义提取时相当于只用了其 LLM 语义层，性价比不高。更适合的替代是 [ms-graphrag-neo4j](https://github.com/neo4j-contrib/ms-graphrag-neo4j)，专为文档实体提取设计，集成成本更低。

---

### 3. Obsidian

**未采用原因**：桌面本地工具，与服务端多租户架构根本不兼容

Obsidian 是桌面端单用户笔记软件，运行在本地文件系统上。match3-wiki 的 Wiki 内容存储于 PostgreSQL `t_wiki_pages`，通过 Next.js 前端实时渲染，数据存在服务端、支持多租户，与 Obsidian 的本地 `.md` 文件运行模式根本不兼容。

**若要集成进来，需要这样调整**：

走"导出"路线而非"集成"路线：

1. 新增 `GET /api/v1/wiki/export?workspaceId=xxx` 接口，将 `status = ready` 的页面批量导出为 `.md` 压缩包
2. 导出 Markdown 中将内链格式对齐为 `[[topic]]`，使 Obsidian 双链功能正常解析
3. 用户下载后解压到本地 Vault 即可浏览

此方式不修改服务端核心架构，但导出的是静态快照，不支持实时同步。

---

### 4. Repomix（及同类代码仓库打包工具）

**未采用原因**：内容域不涉及代码仓库，无适用场景

Repomix 将代码仓库打包成单一文本供 LLM 处理，适用于代码分析场景。Match3 Wiki 的内容域是游戏行业情报，不涉及代码仓库。现有 markitdown 已覆盖业务所需的全部文件类型。

**若要集成进来，需要这样调整**：

若业务需求扩展到「Unity 插件源码文档化」：

1. 新增 `file_type = "repo_archive"`，摄取接口接收 `.zip` 代码仓库
2. Ingest Worker 新增处理分支：解压后调用 repomix（或 [Code2Prompt](https://github.com/raphaelmansuy/code2prompt)）生成单一文本
3. 生成文本送入现有标准分块 → 向量化流程

改动量：小（约 3 天），对现有架构无破坏性影响。

---

### 5. Claude Code

**未采用原因**：开发侧工具，不是可嵌入运行时的组件

Claude Code 是 AI 辅助编程工具，用于本次设计文档和代码的起草与迭代，属于开发侧工具，不是可嵌入运行时的 SDK 或库，不出现在技术栈列表中。

---

### 6. Docusaurus

**未采用原因**：静态站点生成器，无法支撑动态多租户 Wiki 的实时更新需求

Docusaurus 适合发布静态开发者文档站点。match3-wiki 的 Wiki 是动态生成、存于 PostgreSQL、按需检索的在线内容，通过 Next.js 实时渲染，动态更新和多租户隔离需求无法用静态站满足。

**若要集成进来，需要这样调整**：

适用于"对外发布只读公开 Wiki"场景：

1. 新增导出任务，将指定工作区所有 `status = ready` 的 Wiki 页面写成 Docusaurus MDX 格式
2. 触发 `npm run build` 生成静态 HTML
3. 上传至 MinIO 或 CDN，通过独立子域名对外提供访问

改动量：中等（约 1 周），需新增 `wiki_publish_static` Celery task 和构建流水线，与现有 API 动态服务不冲突。

---

### 7. WebFetch / agent-browser（网页实时抓取）

**未采用原因**：实时抓取引入不稳定性，系统选择采集与服务解耦的架构

match3-wiki 将数据采集与知识库服务解耦，用户上传已整理好的文件，避免引入实时抓取的不稳定性（反爬、内容变化、速率限制）。

**若要集成进来，需要这样调整**：

1. 新增摄取接口 `POST /api/v1/ingest/crawl`，接收 `url` 和 `tags`
2. Ingest Worker 新增 `ingest_from_url` 任务，调用 Jina Reader（`https://r.jina.ai/{url}`，开源）或自托管 Crawl4AI 将网页转为 Markdown
3. 后续走现有 markitdown → 分块 → 向量化标准流程，`file_type` 设为 `"webpage"`

改动量：小（约 3 天），对现有架构无破坏性影响，可作为摄取管线的扩展插件按需开启。

---

## 三、match3-wiki 新增的核心工具（PRD 未列出）

以下工具在 PRD 中未明确提及，但在 match3-wiki 中引入：

| 工具 / 组件 | 在系统中的位置与作用 | 同类替代 |
|---|---|---|
| **CLIP ViT-L/14** | Ingest Worker：图片和视频关键帧生成 768 维嵌入，写入 Milvus `image_chunks` 集合；Q&A 阶段：`search_images_by_text()` 用 CLIP 文本编码器将查询词编码为向量，在 `image_chunks` 中做图文语义检索 | OpenCLIP、BLIP-2 |
| **Elasticsearch** | Embed Worker：文本 chunk 写入 ES 建 BM25 索引；hybrid-search：`hybrid_search()` 查 ES 获取关键词排名结果，与 Milvus 向量结果做 RRF 融合；doc-navigate：`QAService` 查询 `t_raw_files WHERE pageindex_doc_id IS NOT NULL` 找到可用的 PageIndex 文档列表，再由 LLM 从目录树中选择最相关节点 | OpenSearch、Typesense |
| **cross-encoder reranker** | hybrid-search 检索的最后一步：`hybrid_search()` 召回 top-150，reranker 对 query-chunk 对打分后精排至 top-20，再送入 LLM context window，显著提升答案质量 | Cohere Rerank API、bge-reranker-large |
| **Neo4j** | Graph Worker：LLM 从文本中抽取实体关系后写入 Neo4j；hybrid-search GraphRAG 方法：在向量检索结果基础上扩展实体子图，支持多跳推理（"Royal Match 的竞品都用了哪些 Hook？"） | Amazon Neptune、TigerGraph |
| **Celery + Redis** | 所有耗时任务异步化：ingest / embed / graph / compile 四条队列各自独立并发，API 立即返回 task_id，用户无需等待。Redis 同时承担 Celery broker 和结果后端 | RQ（更轻量）、Temporal（更重但功能全） |
| **MinIO** | API 层：上传文件先存 MinIO，返回 `object_key`；Ingest Worker：从 MinIO 取文件后处理；图片处理后压缩版本也回写 MinIO 供前端展示 | AWS S3、Cloudflare R2 |
| **Alembic** | 数据库版本管理，CI/CD 部署时执行 `alembic upgrade head` 完成 schema 迁移，确保多环境一致性 | Flyway、Liquibase |
