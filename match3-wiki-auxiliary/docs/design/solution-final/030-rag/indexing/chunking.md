# 索引流程：文档切块与建索引

## 概述

本文件描述 hybrid-search 路径的**离线索引流程**，在文档导入时执行，为在线检索奠定基础。

---

## 整体流程

```
原始文档（PDF / DOCX / HTML / MD / TXT）
    │
    ▼
[步骤 1] 格式转 Markdown
    │ pymupdf4llm / mammoth / markdownify / 直接跳过
    ▼
[步骤 2] 切块策略（二选一）
    │ markdown_header：按标题切（首选，零成本）
    │ fixed_size：RecursiveCharacterTextSplitter
    ▼
[步骤 3] Parent-Child 索引层（必须应用）
    │ parent（1500 字）+ child（300 字，携带 parent_id）
    │ 向量索引只存 child，查询命中 child → 返回 parent 上下文
    ▼
[步骤 4] 三路并行建索引
    ├── Dense + Sparse Embedding → Milvus
    ├── 原文 + metadata → Elasticsearch（BM25）
    └── LLM 实体抽取 → Neo4j（可选）
```

---

## 步骤 1：文档转 Markdown

切块之前先把各种格式的原始文档统一转成 Markdown。Markdown 的标题层级天然提供切块边界，可做到**零 LLM 调用的结构化切块**；转换后剔除了 PDF/DOCX 的格式噪声，chunk 质量更高。

| 来源格式 | 推荐库 | 说明 |
|---------|--------|------|
| PDF | `pymupdf4llm` | 输出 Markdown，保留标题/表格/列表结构，比 pdfplumber 对 LLM 更友好 |
| DOCX | `mammoth` | Word → Markdown/HTML，结构保留好 |
| HTML | `markdownify` | HTML → Markdown，一行代码 |
| 已是 MD | 直接跳过 | wiki 场景大量文档本身就是 MD |
| 纯 TXT | 直接跳过 | 无结构，走 fixed_size 切块 |

---

## 步骤 2：切块策略

切块完全不需要调用 LLM 或 embedding 模型。

### markdown_header（标题切块）—— 优先推荐

对已有 MD 结构的文档，按 `#`/`##`/`###` 标题切块。LangChain 的 `MarkdownHeaderTextSplitter` 直接实现这个逻辑，每个 chunk 自动携带其所属标题层级 metadata，不调 embedding，不调 LLM，速度极快，适合绝大多数结构化文档。

### fixed_size（固定切块）

每 N 字切一刀，相邻块保留 M 字重叠（避免关键信息被截断）。适合无结构纯文本，或标题切块后某节内容仍过长需要二次切分。LangChain 的 `RecursiveCharacterTextSplitter` 先按 `\n\n`、再按 `\n`、最后按字符递归切，比硬切字数更合理。

**选择决策：**

```
文档来源是什么？
  ├─ 已有清晰 MD 标题结构 ──────────► markdown_header（首选，零成本）
  └─ 无结构纯文本 / 标题切后节过长 ──► fixed_size（RecursiveCharacter）
```

**实现文件**：`app/rag/chunker.py`

---

## 步骤 3：Parent-Child 索引层（必须应用）

`parent_child` 不是切块方法的一个选项，而是叠加在切块结果之上的**索引与存储策略**，必须应用。

### 为什么必须用 parent_child？

| 直接切块方案 | 问题 |
|------------|------|
| 小块（300 字）建索引 | 向量更精准，但上下文不完整，LLM 理解困难 |
| 大块（1500 字）建索引 | 上下文完整，但向量失焦，检索精度下降 |
| Parent-Child | **用小块精准检索，用大块提供上下文** |

### 实现方式

把步骤 2 产生的 chunks 当作 parent，对每个 parent 再用 fixed_size 切出更小的 child。向量索引只存 child，每个 child 携带 `parent_id`。检索时命中 child，返回时取对应 parent（parent_splitter: 1500 字，child_splitter: 300 字）。

```
文档
  │ parent_splitter（1500 字）
  ▼
[parent_1]       [parent_2]       [parent_3]
  │ child_splitter（300 字）
  ▼
[c1-1][c1-2][c1-3]  [c2-1][c2-2]  [c3-1][c3-2][c3-3]
  │ 向量索引存 child，携带 parent_id
  ▼
查询时：child 精准匹配 → 取 parent_id → 返回完整 parent 上下文
```

如果某个 parent 本身已经很短（如标题切块后的短节），可跳过 child 拆分，直接以 parent 同时充当 child 入索引。

---

## 步骤 4：三路并行建索引

切块 + Parent-Child 处理完成后，三路索引并发写入：

| 目标存储 | 写入内容 | 必须/可选 |
|---------|---------|---------|
| Milvus | Dense 向量（text-embedding-3-large）+ Sparse 向量（BGE-M3 SPLADE） | 必须 |
| Elasticsearch | 原文 text + metadata（workspace_id, file_type, topic_tag） | 必须 |
| Neo4j | LLM 抽取的实体节点 + 关系边，关联到 chunk_id | 可选（`graph=True` 场景才需要）|

Neo4j 实体抽取成本较高（每个 chunk 调用一次 LLM），**默认关闭**，只在明确需要多跳推理的工作区开启。

---

## 索引侧与查询侧的对应关系

| 索引侧决策 | 查询侧影响 |
|-----------|-----------|
| parent_child 必须应用 | 查询返回大块上下文，减少截断损失 |
| 建了 sparse 索引 | 查询侧才能开 `sparse=True` |
| 建了 Neo4j 图谱 | 查询侧才能开 `graph=True` |

查询侧的五阶段流水线详见 `030-rag/retrieval/hybrid-search.md`。
