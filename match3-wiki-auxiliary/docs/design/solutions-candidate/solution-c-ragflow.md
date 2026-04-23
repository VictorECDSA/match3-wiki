[← 返回总览](overview.md) · [方案 A: 全栈自研](solution-a-fullstack.md) · [方案 B: Dify ⭐](solution-b-dify.md) · [方案 D: 轻量栈](solution-d-lightweight.md)

---

# 方案 C — RAGFlow + Obsidian

**RAGFlow Hybrid Stack · 深度文档解析专家**

2026-04-21 · 三消知识库系统设计

`RAGFlow 深度解析` `Obsidian Wiki 编辑` `Docusaurus 发布` `PDF 图表识别` `三层分工架构` `4-6 周上线`

> 📄 **核心优势：GDC 演讲 PDF + 市场报告表格解析质量最高**

---

> **为什么选方案 C？**
> 三消 Wiki 的核心原始资料是 GDC 演讲 PDF（含大量设计图表）和市场报告（含数据表格）。
> RAGFlow 的核心竞争力是 **深度文档解析（Deep Document Understanding）**——它能识别 PDF 中的表格结构、图表标注、图文关系，而不是简单按字数切块。
> 如果你的知识库有大量此类原始资料，RAGFlow 的召回质量会显著优于 Dify 的默认解析。

---

## 一、RAGFlow 核心解析能力

| 能力 | 说明 |
|---|---|
| 📊 **表格精准识别** | 市场报告中的数据表格（CPI / ROAS / 市场份额）完整保留，不被切断拆散 |
| 🖼️ **图文关联保留** | GDC PDF 中图表的标题、注解与图片关联存储，检索时图文同步召回 |
| 📑 **版面布局理解** | 双栏排版、页眉页脚、注脚等正确处理，不会把页码当正文内容索引 |
| 🔗 **层级结构保留** | PDF 书签/标题层级作为 Parent-Child 分块依据，天然支持层级索引 |
| 🌐 **多语言混排** | 中英文混排 PDF 正确处理，GDC 演讲英文 + 笔记中文标注均可解析 |
| ⚡ **增量更新** | 文档更新时只重新解析变更部分，不重建全量索引，节省成本 |

---

## 二、整体架构（三层分工）

```text
┌────────────────────────────────────────────────────────────────────┐
│  层 1：内容创作层（Obsidian）                                        │
│                                                                     │
│  Obsidian Vault（本地）                                             │
│  ├── wiki/        — 编译后的知识页面（Markdown + frontmatter）       │
│  ├── raw/         — 原始资料（任意格式，零门槛摄入）                  │
│  └── audit/       — 人工纠错队列                                     │
│                                                                     │
│  关键插件：Templater（模板）/ Dataview（统计）/ Git（同步）           │
│            Obsidian Web Clipper（网页收集）                          │
└───────────────────────┬────────────────────────────────────────────┘
                        │ 文件变动 → Git Push
┌───────────────────────▼────────────────────────────────────────────┐
│  层 2：RAG 引擎层（RAGFlow 自托管）                                   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Document Processing Pipeline                                │   │
│  │  ├── DeepDoc（RAGFlow 内置深度解析引擎）                       │   │
│  │  │   ├── PDF 表格识别（Table Detection）                     │   │
│  │  │   ├── 图表 OCR + 图文关联                                  │   │
│  │  │   ├── 版面分析（Layout Analysis）                         │   │
│  │  │   └── 多语言处理                                          │   │
│  │  ├── 分块策略：Book / Paper / Presentation / Manual 模式     │   │
│  │  └── 向量化：bge-m3 + 稀疏向量（BM25）                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Retrieval Pipeline（Hybrid Search + Reranking）              │   │
│  │  Elasticsearch（BM25）+ Infinity（向量）+ RRF 融合 + Reranker │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Agent / Agentic Chat                                        │   │
│  │  RAGFlow 内置 Agentic RAG（工具调用 + 多轮对话 + 引用展示）   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└───────────────────────┬────────────────────────────────────────────┘
                        │ API / iframe
┌───────────────────────▼────────────────────────────────────────────┐
│  层 3：发布层（Docusaurus + Q&A 嵌入）                               │
│                                                                     │
│  Docusaurus 静态站 ← GitHub Actions 自动构建                         │
│  ├── Wiki 页面（SEO 优化，对外可见）                                  │
│  ├── 嵌入 RAGFlow Chat Widget（右下角悬浮窗）                         │
│  └── Algolia 全文搜索                                               │
└────────────────────────────────────────────────────────────────────┘
```

---

## 三、RAGFlow 分块模式选型（针对三消 Wiki 资料）

| 资料类型 | RAGFlow 分块模式 | 原因 |
|---|---|---|
| GDC 演讲 PDF（有幻灯片结构） | **Presentation** 模式 | 按幻灯片页面分块，保留每页标题 + 内容 + 图表注解 |
| 市场报告 PDF（有表格/图表） | **Paper** 模式 | 学术论文模式，表格整体保留，图文关联强 |
| Wiki Markdown 页面 | **Naive** 模式 + 按 H2 分块 | 结构简单，按 Markdown 标题层级切分即可 |
| Web 抓取文章 | **General** 模式 | 通用模式，适合各类网页格式 |
| 游戏截图/UI 图片 | **Picture** 模式 | 图片 + OCR + 视觉描述 三路并行索引 |
| 视频转录文字（GDC 视频） | **One** 模式（整体摘要）+ **General**（分段） | 先生成全文摘要，再按段落分块双路检索 |

---

## 四、高召回率 RAG 配置

### 4.1 RAGFlow 检索设置

```yaml
# RAGFlow Dataset 配置（通过 UI 或 API 设置）

embedding_model: BAAI/bge-m3          # 中英双语，本地部署
chunk_method: paper                    # 针对 GDC PDF 的模式
parser_config:
  layout_recognize: true               # 启用版面识别（关键！）
  table_detect: true                   # 表格检测
  ocr: true                            # 图表 OCR
  vision_model: gpt-4o-mini            # 图表理解模型

retrieval_config:
  top_k: 8                             # 最终返回文档数
  similarity_threshold: 0.2            # 低于此分数过滤
  vector_similarity_weight: 0.3        # 向量权重
  keyword_similarity_weight: 0.7       # 关键词权重（三消专有名词多，偏高）
  rerank_model: BAAI/bge-reranker-v2-m3  # 本地精排模型
```

### 4.2 Multi-Query 增强（RAGFlow Agentic 模式）

```text
# RAGFlow Agent 配置（system_prompt）

你是三消游戏行业知识库助手。

回答前，请先将用户问题扩展为 3 个不同角度的查询：
1. 原始问题
2. 使用行业专有名词的表述（如"消除连击"→"Cascade mechanic"）
3. 从设计者视角重述（关注设计意图而非玩法描述）

用这 3 个查询分别检索，合并去重后再生成答案。

回答时必须：
- 引用具体来源（文件名 + 相关段落）
- 标注数据时间（如"据 Sensor Tower 2024 报告"）
- 不知道的内容标注"待补充"，不得编造
```

### 4.3 CRAG Web 搜索兜底

```text
# RAGFlow Agent 工具配置

工具：Google Search（RAGFlow 内置）
触发条件：检索到的文档相关度平均分 < 0.3
执行逻辑：
  1. 用精炼后的关键词（去除停用词）进行 Web 搜索
  2. 抓取 Top 3 结果页面内容
  3. 合并到知识库检索结果中一起生成答案
  4. 在答案末尾标注"（来源：Web 搜索，{日期}）"
```

---

## 五、多模态摄入 Pipeline

### 5.1 PDF 摄入（RAGFlow DeepDoc 全自动）

📥 **上传 PDF → RAGFlow 自动处理**

通过 RAGFlow UI 上传，或 API `POST /api/v1/dataset/{id}/document`，选择 `parser_id: paper` 或 `presentation`

🔍 **DeepDoc 深度解析**

版面分析 → 文本提取 → 表格检测（保留行列结构）→ 图片区域定位 → OCR 识别

🖼️ **图表理解（可选 Vision 模型）**

检测到图表时调用 GPT-4o-mini 生成描述文字，与原图一起存入多模态索引

✂️ **智能分块 + 双路向量化**

按解析模式分块 → bge-m3 密集向量（语义）+ 稀疏向量（BM25 关键词）双路入库 Infinity

✅ **可在 RAGFlow UI 预览分块结果**

可视化查看每个分块，手动调整错误识别的表格边界，修改后立即更新索引

### 5.2 图片摄入（截图/游戏 UI）

```bash
# 通过 RAGFlow API 摄入图片

POST /api/v1/dataset/{dataset_id}/document
Content-Type: multipart/form-data

file: [screenshot.png]
parser_id: picture          # Picture 模式
chunk_method: picture       # 整图作为一个 chunk

# RAGFlow 自动：
# 1. OCR 提取图片中的文字
# 2. CLIP 向量化（跨模态检索）
# 3. 可选：GPT-4o-mini 生成图片描述
# 检索时：文字查询可以找到截图中包含的文字内容
```

---

## 六、Obsidian + RAGFlow 联动方案

### 6.1 同步策略

| 目录 | 同步方向 | 同步方式 | 触发时机 |
|---|---|---|---|
| `wiki/` Markdown 页面 | Obsidian → RAGFlow | Git Webhook → Python 脚本调用 RAGFlow API | 每次 git push（变动文件） |
| `raw/` 原始资料 | Obsidian → RAGFlow | 同上，自动选择对应 parser_id | 新文件出现时 |
| RAGFlow 问答历史 | RAGFlow → Obsidian | 定时脚本拉取，存入 `qa-log/` | 每周汇总 |

### 6.2 同步脚本

```python
# sync_to_ragflow.py（由 Git Hook 或 GitHub Actions 触发）

import ragflow_sdk
from pathlib import Path

client = ragflow_sdk.RAGFlow(api_key=API_KEY, base_url=RAGFLOW_URL)

def get_parser_id(file_path: str) -> str:
    """Select RAGFlow parser based on file location and type."""
    if "raw/gdc" in file_path and file_path.endswith(".pdf"):
        return "presentation"
    if "raw/reports" in file_path and file_path.endswith(".pdf"):
        return "paper"
    if file_path.endswith((".png", ".jpg", ".jpeg")):
        return "picture"
    if "wiki/" in file_path and file_path.endswith(".md"):
        return "general"
    return "general"

for changed_file in get_git_changed_files():
    dataset = client.get_dataset(name="match3-wiki")
    dataset.upload_document(
        file_path=changed_file,
        parser_id=get_parser_id(changed_file),
        # Auto-start parsing
        run=True
    )
    print(f"Uploaded: {changed_file} → parser: {get_parser_id(changed_file)}")
```

---

## 七、多用户方案

### 7.1 RAGFlow 内置团队功能

| 功能 | 说明 |
|---|---|
| 团队邀请 | Admin 通过邮件邀请成员，分配角色 |
| 知识库权限 | 每个 Dataset 可设置可见范围（私有/团队/公开） |
| API Key 管理 | 为不同系统（Docusaurus 嵌入、内部工具）生成独立 Key |
| 对话历史 | 每个用户的问答记录独立存储，Admin 可审查 |

### 7.2 权限分层设计

```text
RAGFlow 角色 → 对应操作权限：

SuperAdmin
  └── 管理所有 Dataset、用户、API Key、系统配置

Team Admin（主编）
  └── 创建/编辑/删除 Dataset
  └── 上传/删除文档
  └── 管理成员
  └── 访问全部 Chat 历史

Member（编辑/贡献者）
  └── 上传文档到被授权的 Dataset（需 Admin 审核解析结果）
  └── 使用 Chat（问答）
  └── 只能看自己的 Chat 历史

API User（外部集成）
  └── 通过 API Key 只能调用 Chat API
  └── 对应 Docusaurus Wiki 嵌入的只读访问
```

---

## 八、与方案 B (Dify) 的关键差异

### RAGFlow 更强的地方

- PDF 深度解析（表格/图表/版面）开箱即用
- 分块结果可视化预览 + 手动调整
- 内置 Infinity 向量数据库，专为 RAG 优化
- 稀疏向量（BM25）+ 密集向量原生双路检索
- Agentic RAG 模式（工具调用）内置
- 文档引用 UI 展示效果更好（高亮原文）

### Dify 更强的地方

- Workflow 可视化编排更灵活
- 多用户权限系统更完善
- 支持更多 LLM 接入（含本地模型）
- 社区生态更大，插件/模板更多
- 前端嵌入方案（iframe SDK）更成熟
- Adaptive RAG 路由实现更直观

> **决策建议：**
> 如果你的原始资料以 **PDF 为主**（GDC 演讲、市场报告），优先选方案 C；
> 如果需要更多 **Workflow 定制**（复杂的多 Agent 逻辑），选方案 B；
> 两者可以 **并存使用**：RAGFlow 处理 PDF 原始资料，Dify 处理 Wiki Markdown 和对外 Q&A。

---

## 九、部署 + 费用

### 9.1 Docker Compose

```bash
# RAGFlow 官方 Docker Compose（一键启动）
git clone https://github.com/infiniflow/ragflow
cd ragflow/docker
docker compose up -d

# 包含服务：
#   ragflow-server:   主服务（文档解析 + API + Web UI）
#   infinity:         向量数据库（RAGFlow 专用）
#   elasticsearch:    全文检索（BM25）
#   mysql:            元数据存储
#   redis:            缓存
#   minio:            对象存储

# 可选：本地 Embedding 服务
docker run -d \
  --name bge-m3 \
  -p 8080:80 \
  ghcr.io/huggingface/text-embeddings-inference:cpu-1.5 \
  --model-id BAAI/bge-m3

# 在 RAGFlow Settings → Model Provider → OpenAI-compatible API
# 指向 http://bge-m3:8080 即可使用本地模型
```

### 9.2 费用估算

| 项目 | 方案 | 月费用 |
|---|---|---|
| VPS（RAGFlow 主机） | 8核16G（RAGFlow DeepDoc 吃内存） | $50-80 |
| LLM API | Claude / GPT-4o（按量） | $20-50 |
| Embedding | bge-m3 本地部署 | $0 |
| Vision 模型（PDF 图表） | GPT-4o-mini（解析时用，一次性） | $5-20 |
| Docusaurus 托管 | Vercel | $0 |
| **合计** | | **$75-150/月** |

> ⚠️ **注意：** RAGFlow 的 DeepDoc 引擎（PDF 深度解析）对 CPU/内存要求较高，建议至少 8G 内存，
> 大量 PDF 处理时 16G 更稳定。相比方案 B，VPS 配置需求更高。

---

## 十、实施步骤（4-6 周）

| 周次 | 任务 | 交付物 |
|---|---|---|
| 第 1 周 | RAGFlow 部署 + 基础配置 | RAGFlow 运行；bge-m3 本地 Embedding；上传 5 份种子 PDF 测试解析效果 |
| 第 2 周 | Dataset 建立 + 分块模式优化 | 5 个 Dataset 创建；各类型资料分块效果验证；Hybrid Search 参数调优 |
| 第 3 周 | Agentic RAG 配置 | Multi-Query 扩展 System Prompt；CRAG 兜底工具；来源引用格式 |
| 第 4 周 | Obsidian 联动 + Git 同步 | sync_to_ragflow.py 脚本；GitHub Actions 自动同步；Obsidian 插件配置 |
| 第 5 周 | Docusaurus 发布 + Chat 嵌入 | Wiki 站点上线；RAGFlow Chat Widget 嵌入；Algolia 搜索配置 |
| 第 6 周 | 多用户 + 多模态完善 | 团队权限配置；图片/截图摄入测试；正式上线 |

---

[← 返回总览](overview.md) · [方案 D: 轻量栈 →](solution-d-lightweight.md)
