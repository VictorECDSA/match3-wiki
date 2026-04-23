# hybrid-search 设计

## 1. 设计动机

原始 hybrid-search 路径把 16 种 RAG 方法平铺并列，但这 16 种方法之间存在大量重叠与嵌套关系：

| 分组 | 方法 | 本质 |
|------|------|------|
| 查询扩展 | Multi-Query、HyDE | 检索前的 query 变换策略，不是独立方法 |
| 索引层 | Parent-Child | 离线建索引方式（强制应用），与在线检索正交 |
| 验证机制 | CRAG、Self-RAG | 检索/生成后的质检策略，可叠加 |
| 智能体调度 | Agentic RAG、Multi-Agent RAG | 编排层，不是检索通道本身 |
| 生成优化 | Speculative RAG | 主要影响生成并发，非检索逻辑 |
| 检索通道 | Naive、Hybrid、GraphRAG、Text2SQL | 真正的差异化检索源 |

**结论**：hybrid-search 路径的核心差异在于"开了哪些检索通道 + 用什么策略扩展查询 + 用什么精度做精排"，而不是 16 条并列的独立 pipeline。

新设计将其抽象为**可配置的 5 阶段流水线**，每个阶段独立可选，通过 `RetrievalConfig` 声明式组合。

---

## 2. 两条流程概览

hybrid-search 涉及两条完全独立的流程，必须都设计清楚：

```
【索引流程】（离线，文档导入时执行）

原始文档
    │
    ▼
[步骤 1] 文档转 Markdown（pymupdf4llm / mammoth / markdownify）
    │
    ▼
[步骤 2] 切块（二选一）
    markdown_header: 按 #/##/### 标题切，零 LLM/embedding，首选
    fixed_size:      RecursiveCharacterTextSplitter，按字数固定切
    │
    ▼
[步骤 3] Parent-Child 索引层（必须应用）
    切块结果 → 大块（parent）+ 细分小块（child）
    向量索引只存 child，每个 child 携带 parent_id
    查询命中 child → 取 parent_id → 返回完整 parent 上下文
    │
    ▼
[步骤 4] 并行三路建索引
    ├── Dense + Sparse Embedding → Milvus（向量索引）
    ├── 原文 → Elasticsearch（BM25 倒排索引）
    └── 实体/关系抽取 → Neo4j（知识图谱，可选）
```

```
【查询流程】（在线，用户提问时执行）

原始 query → 查询扩展 → 多通道并行检索 → RRF 融合 → 精排 → 验证 → 生成
```

两条流程的核心对应关系：

| 索引侧决策 | 查询侧影响 |
|-----------|-----------|
| parent_child 必须应用 | 查询返回大块上下文，减少截断损失 |
| 建了 sparse 索引 | 查询侧才能开 `sparse=True` |
| 建了 Neo4j 图谱 | 查询侧才能开 `graph=True` |

---

## 3. 索引流程详解

### 3.1 步骤一：文档转 Markdown

切块之前必须先把各种格式的原始文档统一转成 Markdown，原因是：

- Markdown 的标题层级（`#` / `##` / `###`）天然提供切块边界，可以做到**零 LLM 调用的结构化切块**
- 转换后剔除了 PDF/DOCX 的格式噪声（页眉页脚、排版标记），chunk 质量更高

各格式推荐工具：

| 来源格式 | 推荐库 | 说明 |
|---------|--------|------|
| PDF | `pymupdf4llm` | 基于 PyMuPDF，输出 Markdown，保留标题/表格/列表结构，比 pdfplumber 对 LLM 更友好 |
| DOCX | `mammoth` | Word → Markdown/HTML，结构保留好；或 `python-docx` 自行遍历段落 |
| HTML | `markdownify` | HTML → Markdown，一行代码 |
| 已是 MD | 直接跳过 | wiki 场景大量文档本身就是 MD |
| 纯 TXT | 直接跳过 | 无结构，走 fixed_size 切块 |

转换后输出标准 Markdown 字符串，进入切块阶段。

---

### 3.2 步骤二：切块策略（二选一）

切块完全不需要调用 LLM 或 embedding 模型。

**markdown_header（标题切块）—— 优先推荐**

对已有 MD 结构的文档，按 `#`/`##`/`###` 标题切块。LangChain 的 `MarkdownHeaderTextSplitter` 直接实现这个逻辑，每个 chunk 自动携带其所属的标题层级 metadata（可用于 ES 过滤）。不调 embedding，不调 LLM，速度极快，适合绝大多数结构化文档（技术报告、wiki、产品文档）。

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter

splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#",  "h1"),
        ("##", "h2"),
        ("###","h3"),
    ],
    strip_headers=False,
)
chunks = splitter.split_text(markdown_text)
# chunks[i].metadata = {"h1": "...", "h2": "...", "h3": "..."}
```

**fixed_size（固定切块）**

每 N 字切一刀，相邻块之间保留 M 字重叠（避免关键信息被截断）。适合无结构纯文本、或标题切块后某节内容仍过长需要二次切分。LangChain 的 `RecursiveCharacterTextSplitter` 先按 `\n\n`、再按 `\n`、最后按字符递归切，比硬切字数更合理。

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "！", "？", " ", ""],
)
chunks = splitter.split_text(text)
```

**选择决策：**

```
文档来源是什么？
  ├─ 已有清晰 MD 标题结构 ──────────► markdown_header（首选，零成本）
  └─ 无结构纯文本 / 标题切后节过长 ──► fixed_size（RecursiveCharacter）
```

---

### 3.3 步骤三：Parent-Child 索引层（必须应用）

`parent_child` 不是切块方法的一个选项，而是叠加在切块结果之上的**索引与存储策略**，必须应用。

**为什么必须用 parent_child？**

切块后的 chunk 若直接建索引，精准匹配和完整上下文之间存在矛盾：
- 小块（300 字）向量更精准，但上下文不完整，LLM 理解困难
- 大块（1500 字）上下文完整，但向量失焦，检索精度下降

parent_child 同时解决两个问题：**用小块精准检索，用大块提供上下文**。

**实现方式：**

把步骤二产生的 chunks 当作 parent，对每个 parent 再用 fixed_size 切出更小的 child。向量索引只存 child，但每个 child 携带 `parent_id`。检索时命中 child，返回时取对应 parent。

```python
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=0)
child_splitter  = RecursiveCharacterTextSplitter(chunk_size=300,  chunk_overlap=30)

for parent in parent_splitter.split_text(text):
    parent_id = store_parent(parent)          # 存大块，不建向量
    for child in child_splitter.split_text(parent):
        store_child(child, parent_id=parent_id)  # 向量索引只存 child
```

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

### 3.4 步骤四：并行三路建索引

切块+parent_child 处理完成后，三路索引并发写入：

```python
async def index_chunks(chunks: list[Chunk], workspace_id: str, rt: Match3Runtime):
    await asyncio.gather(
        write_milvus(chunks, workspace_id, rt),   # Dense + Sparse vectors
        write_es(chunks, workspace_id, rt),        # BM25 inverted index
        write_neo4j(chunks, workspace_id, rt),     # entity/relation graph (optional)
    )
```

| 目标存储 | 写入内容 | 必须/可选 |
|---------|---------|---------|
| Milvus | Dense 向量（text-embedding-3-large）+ Sparse 向量（BGE-M3 SPLADE） | 必须 |
| Elasticsearch | 原文 text + metadata（workspace_id, file_type, topic_tag） | 必须 |
| Neo4j | LLM 抽取的实体节点 + 关系边，关联到 chunk_id | 可选（`graph=True` 场景才需要）|

Neo4j 实体抽取成本较高（每个 chunk 调用一次 LLM），**默认关闭**，只在明确需要多跳推理的工作区开启。

---

## 4. 查询流程：五阶段流水线

```
原始 query
    │
    ▼
[阶段 1] 查询扩展（两个独立开关，可同时开启）
    multi_query: LLM 将 query 改写成 N 种不同表述，分别检索后合并
    hyde:        LLM 先生成假答案，用假答案向量检索；与 multi_query 可叠加
    （两者都关闭则直接用原始 query）
    │
    ▼
[阶段 2] 多通道并行检索（选开哪些通道）
    ├── Dense  → Milvus ANN（语义向量）
    ├── Sparse → Milvus BM42/SPLADE（稀疏向量）
    ├── BM25   → Elasticsearch（精确关键词）
    ├── Graph  → Neo4j 实体关系多跳遍历
    └── SQL    → PostgreSQL 结构化聚合查询
    │
    ▼
[阶段 3] 融合（多通道结果合并）
    RRF: Reciprocal Rank Fusion 倒数排序融合
    │
    ▼
[阶段 4] 精排（可选，成本递增）
    none:          不精排，直接截取 top-K
    lightweight:   轻量 reranker 初筛（BGE-reranker-base）
    cross_encoder: Cross-Encoder 精排（BGE-reranker-large）
    llm_judge:     LLM 逐条打分（高成本，高精度）
    │
    ▼
[阶段 5] 验证（可选，高准确率场景）
    none:     不验证，直接生成
    crag:     LLM 判断相关性；不足时触发 web 搜索兜底
    self_rag: 生成初稿后 LLM 自检是否有文档依据；不足则重生成
```

**HybridSearchEngine 实现：**

```python
# app/rag/hybrid_search_engine.py
from __future__ import annotations
import asyncio
from dataclasses import asdict
from app.runtime import Match3Runtime
from app.rag.retrieval_config import RetrievalConfig, RerankLevel, ValidationMode
from app.rag.fusion import rrf_fuse
from app.rag.channels.dense_channel import dense_search
from app.rag.channels.bm25_channel import bm25_search
from app.rag.channels.graph_channel import graph_search
from app.rag.channels.sql_channel import sql_search
from app.rag.reranker import rerank
from app.rag.validator import crag_validate, self_rag_validate
from app.rag.expander import multi_query_expand, hyde_expand


class HybridSearchEngine:
    """Config-driven retrieval engine.

    Executes a 5-stage pipeline:
      1. Query expansion (optional)
      2. Parallel multi-channel retrieval
      3. RRF fusion
      4. Reranking (optional)
      5. Validation (optional)
    """

    def __init__(self, rt: Match3Runtime):
        self._rt = rt

    async def search(
        self,
        query: str,
        workspace_id: str,
        cfg: RetrievalConfig,
    ) -> list[dict]:
        # --- stage 1: query expansion (independent switches) ---
        queries = [query]
        if cfg.hyde:
            # hyde: replace original query with hypothetical-answer vector
            queries = await hyde_expand(self._rt, query)
        if cfg.multi_query:
            # multi_query: expand each current query into N variants
            expanded = []
            for q in queries:
                expanded.extend(await multi_query_expand(self._rt, q, n=cfg.multi_query_n))
            queries = expanded

        # --- stage 2: parallel multi-channel retrieval ---
        all_channel_results: list[list[dict]] = []
        for q in queries:
            channel_tasks = []
            if cfg.dense or cfg.sparse:
                channel_tasks.append(dense_search(self._rt, q, workspace_id, cfg))
            if cfg.bm25:
                channel_tasks.append(bm25_search(self._rt, q, workspace_id, cfg))
            if cfg.graph:
                channel_tasks.append(graph_search(self._rt, q, workspace_id, cfg))
            if cfg.sql:
                channel_tasks.append(sql_search(self._rt, q, workspace_id, cfg))
            results = await asyncio.gather(*channel_tasks)
            all_channel_results.extend(results)

        # --- stage 3: RRF fusion ---
        fused = rrf_fuse(all_channel_results, top_k=cfg.fusion_top_k)

        # --- stage 4: reranking ---
        if cfg.rerank != RerankLevel.NONE:
            fused = await rerank(self._rt, query, fused, level=cfg.rerank, top_k=cfg.final_top_k)
        else:
            fused = fused[:cfg.final_top_k]

        # --- stage 5: validation ---
        if cfg.validation == ValidationMode.CRAG:
            fused = await crag_validate(self._rt, query, fused, web_fallback=cfg.web_fallback)
        elif cfg.validation == ValidationMode.SELF_RAG:
            fused = await self_rag_validate(self._rt, query, fused)

        return fused
```

---

## 5. RetrievalConfig：声明式组合

```python
# app/rag/retrieval_config.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class RerankLevel(str, Enum):
    NONE          = "none"
    LIGHTWEIGHT   = "lightweight"   # fast reranker, top-150 → top-20
    CROSS_ENCODER = "cross_encoder" # cross-encoder, top-20 → top-5
    LLM_JUDGE     = "llm_judge"     # LLM relevance scoring, top-5 → top-3


class ValidationMode(str, Enum):
    NONE     = "none"
    CRAG     = "crag"      # post-retrieval relevance check + web fallback
    SELF_RAG = "self_rag"  # post-generation support check + regenerate


@dataclass
class RetrievalConfig:
    # --- query expansion (independent switches, can both be enabled) ---
    multi_query: bool = False     # LLM rewrites query into N variants; results merged before fusion
    multi_query_n: int = 3        # number of query variants
    hyde: bool = False            # LLM generates hypothetical answer; use its vector for retrieval
                                  # when both multi_query and hyde are True:
                                  #   multi_query variants are generated first, then each gets hyde expansion

    # --- retrieval channels ---
    dense:  bool = True    # Milvus ANN (text-embedding-3-large, 3072d)
    sparse: bool = True    # Milvus BM42 / BGE-M3 SPLADE
    bm25:   bool = True    # Elasticsearch keyword
    graph:  bool = False   # Neo4j entity-relation traversal
    sql:    bool = False   # PostgreSQL structured query (text2sql)

    # --- graph traversal params (only when graph=True) ---
    graph_hops: int = 2            # max relationship hops
    graph_anchor_top_k: int = 5    # anchor entities from dense results

    # --- candidate limits per channel ---
    channel_top_k: int = 50        # candidates per channel before fusion
    fusion_top_k:  int = 150       # candidates after RRF before rerank

    # --- reranking ---
    rerank: RerankLevel = RerankLevel.LIGHTWEIGHT

    # --- final top-K fed to LLM ---
    final_top_k: int = 8

    # --- validation ---
    validation: ValidationMode = ValidationMode.NONE
    web_fallback: bool = False     # used by crag when internal retrieval fails
```

---

## 6. 预设 Profile

路由器不再直接映射到某种"方法"，而是映射到一个 `RetrievalConfig` Profile。

```python
# app/rag/retrieval_profiles.py
from app.rag.retrieval_config import (
    RetrievalConfig, RerankLevel, ValidationMode
)

# Simple factual lookup: "What is X?"
PROFILE_SIMPLE = RetrievalConfig(
    dense=True, sparse=True, bm25=True,
    rerank=RerankLevel.LIGHTWEIGHT,
    final_top_k=5,
)

# Moderate: multi-hop comparison, "Compare X and Y"
PROFILE_MODERATE = RetrievalConfig(
    multi_query=True, multi_query_n=3,
    dense=True, sparse=True, bm25=True,
    rerank=RerankLevel.CROSS_ENCODER,
    final_top_k=8,
)

# Complex: deep analysis, graph relationships, "What games are related to X?"
PROFILE_COMPLEX = RetrievalConfig(
    hyde=True,
    dense=True, sparse=True, bm25=True, graph=True,
    graph_hops=2,
    rerank=RerankLevel.CROSS_ENCODER,
    final_top_k=10,
)

# Analytical: structured data, "Top 10 games by revenue"
PROFILE_ANALYTICAL = RetrievalConfig(
    dense=False, sparse=False, bm25=False, sql=True,
    rerank=RerankLevel.NONE,
    final_top_k=1,
)

# Uncertain: might need web search fallback
PROFILE_UNCERTAIN = RetrievalConfig(
    dense=True, sparse=True, bm25=True,
    rerank=RerankLevel.CROSS_ENCODER,
    validation=ValidationMode.CRAG,
    web_fallback=True,
    final_top_k=8,
)

# High-stakes: must not hallucinate
PROFILE_HIGH_ACCURACY = RetrievalConfig(
    multi_query=True,
    dense=True, sparse=True, bm25=True, graph=True,
    rerank=RerankLevel.CROSS_ENCODER,
    validation=ValidationMode.SELF_RAG,
    final_top_k=6,
)


PROFILE_MAP: dict[str, RetrievalConfig] = {
    "simple":        PROFILE_SIMPLE,
    "moderate":      PROFILE_MODERATE,
    "complex":       PROFILE_COMPLEX,
    "analytical":    PROFILE_ANALYTICAL,
    "uncertain":     PROFILE_UNCERTAIN,
    "high_accuracy": PROFILE_HIGH_ACCURACY,
}
```

---

## 7. 效率优化：缩小比对范围

搜索效率的核心问题是**避免全量扫描**。以下几个策略在不同阶段削减候选集规模：

### 7.1 向量检索（Dense / Sparse）：分区 + 预过滤

Milvus 支持 `partition_key_field`，将 `workspace_id` 作为分区键，**ANN 搜索天然只在当前工作区的向量空间内比对**，无需遍历其他工作区的向量。

```
全量向量空间（数百万条）
  │ partition_key = workspace_id
  ▼
当前工作区向量分区（通常数万～数十万条）
  │ scalar pre-filter: file_type / topic_tag / date_range
  ▼
过滤后候选集（通常数千条）
  │ ANN search (HNSW / IVF_SQ8)
  ▼
top-50 candidates
```

关键参数：
- `nprobe`（IVF）或 `ef`（HNSW）控制 ANN 搜索精度，值越小越快但召回率降低；生产建议 `ef=64`
- 标量预过滤比 ANN 后过滤效率高：先过滤再向量搜索，候选集小时 HNSW 速度可提升 5-10x

### 7.2 BM25（Elasticsearch）：倒排索引 + 过滤

ES 的倒排索引本身已经是"只比对含目标词的文档"，再加上：

```json
{
  "query": {
    "bool": {
      "filter": [
        {"term": {"workspace_id": "ws_xxx"}},
        {"term": {"file_type": "report"}}
      ],
      "should": [
        {"match": {"content": "query_text"}}
      ]
    }
  }
}
```

`filter` 子句在 BM25 打分前执行，命中文档数大幅收窄。

### 7.3 图谱检索（Neo4j）：锚点驱动，不全图扫描

纯图谱遍历如果从所有节点出发，复杂度爆炸。正确策略：

```
1. 先用 Dense/Sparse 搜到 top-K anchor chunks（已缩小范围）
2. 从 anchor chunks 中提取实体 entity_ids（命名实体识别或预存映射）
3. 仅从这些 entity_ids 出发做 N 跳遍历：MATCH (e)-[*1..2]-(n) WHERE e.id IN $anchor_ids
4. 遍历结果的子图再二次 embedding 匹配
```

这样图谱遍历的起点集合非常小（通常 5-10 个锚点），而不是全图扫描。

额外效率手段：
- Neo4j 对 `entity_id`、`workspace_id` 建复合索引（`CREATE INDEX ON :Entity(workspace_id, entity_id)`）
- 遍历深度 `graph_hops` 默认 2，3 跳以上性能急剧下降，通常无必要

### 7.4 全通道并发

所有启用的检索通道并发执行，互不阻塞：

```python
import asyncio

async def retrieve_all_channels(cfg, query, workspace_id):
    tasks = []
    if cfg.dense or cfg.sparse:
        tasks.append(milvus_search(query, workspace_id, cfg))
    if cfg.bm25:
        tasks.append(es_search(query, workspace_id, cfg))
    if cfg.graph:
        tasks.append(graph_search(query, workspace_id, cfg))
    if cfg.sql:
        tasks.append(sql_search(query, workspace_id, cfg))
    results = await asyncio.gather(*tasks)
    return results
```

实测：Dense + Sparse + BM25 三通道并发耗时 ≈ 单通道最慢者（通常 Dense），而非三者之和。

---

## 8. 查询扩展策略

### 8.1 Multi-Query

```
原始 query: "三消游戏留存提升方法"
          │
          ▼
LLM 改写为 3 个变体:
  q1: "match-3 puzzle game day-1 retention strategies"
  q2: "三消手游玩家流失原因分析"
  q3: "关卡难度曲线对留存的影响"
          │
          ▼
3 个 query 分别走各通道检索 → 结果合并去重 → RRF 融合
```

**适用**：用户表述口语化、术语不规范的场景。不适用于专业领域术语已很精准的查询（改写可能带偏）。

### 8.2 HyDE

```
原始 query: "KV Cache 是什么？"
          │
          ▼
LLM 生成假答案:
  "KV Cache 是 Transformer 推理中缓存 Key/Value 矩阵的技术..."
          │
          ▼
用假答案向量检索（假答案文体与文档更接近，向量空间距离更近）
          │
          ▼
检索结果 + 原始 query → LLM 生成最终答案
```

**适用**：技术类问答，用户短问题 vs 文档长段落的 embedding 空间失配。不适用：冷门领域（LLM 可能生成错误假答案，把检索带偏）。

---

## 9. 精排层次

精排成本与精度递增，根据 `RetrievalConfig.rerank` 选择：

```
候选集（fusion_top_k = 150）
    │
    │ rerank = lightweight
    ▼
BGE-reranker-base 初筛 → top-20
    │
    │ rerank = cross_encoder
    ▼
BGE-reranker-large 精排 → top-5
    │
    │ rerank = llm_judge（高成本，慎用）
    ▼
LLM 逐条 (query, doc) 打相关分 → top-3
```

生产建议：默认使用 `lightweight`，复杂查询升级到 `cross_encoder`，不建议常规场景使用 `llm_judge`。

---

## 10. 验证机制

验证是**可选后置阶段**，用于高准确率场景：

### 10.1 CRAG

```
精排结果
    │
    ▼
LLM 判断：这些文档与查询是否相关？
    ├─ 相关 → 正常生成
    ├─ 部分相关 → 合并 web 搜索结果后生成
    └─ 不相关 → LLM 改写 query → web 搜索兜底 → 生成
```

**启用条件**：`validation=CRAG, web_fallback=True`，适合时效性强或内部知识库覆盖不全的场景。

### 10.2 Self-RAG

```
精排结果 → LLM 生成初稿
    │
    ▼
LLM 自检：答案中每个论断是否都有文档支撑？
    ├─ 通过 → 输出初稿
    └─ 不通过 → 附加"请严格基于参考资料"指令重新生成
```

**启用条件**：`validation=SELF_RAG`，适合准确率要求极高、不能容忍幻觉的场景（如法规、合规类查询）。

---

## 11. Agentic RAG 与 Multi-Agent RAG

上面所有配置都是预定义 pipeline，流程固定。但有些查询场景需要动态决策：到底该搜向量库还是查数据库，搜一次够不够，要不要换关键词再搜一遍。这就是 Agentic / Multi-Agent 的价值所在。

### 11.1 Agentic RAG：ReAct 循环

核心是 **ReAct 循环**（Reasoning + Acting）：Agent 每轮先推理再行动，根据当前已知信息决定下一步用哪个工具，直到信息足够为止。

```
给 Agent 配备工具集：
  vector_search  → HybridSearchEngine.search()
  graph_traverse → Neo4j N-hop query
  sql_query      → PostgreSQL text2sql
  web_search     → 外部搜索引擎

进入 ReAct 循环：
  ┌─────────────────────────────────────────────┐
  │ Thought: 基于已知信息，我下一步需要什么？      │
  │          还是信息已经足够可以回答了？           │
  │                                             │
  │ Action:  选择工具 + 构造 tool_input           │
  │                                             │
  │ Observation: 执行工具，把结果追加到 context   │
  └─────────────────────────────────────────────┘
         │
         │ thought.action == "answer"
         ▼
  生成最终回答
```

**适用**：多数据源混合场景（同一问题可能既要查文档又要查数据库）；查询复杂度不可预测时。当前 `PROFILE_COMPLEX` + `graph=True` 可覆盖大多数复杂场景，Agentic 模式作为超复杂场景的扩展点。

### 11.2 Multi-Agent RAG：多专职 Agent 分工

单 Agent 同时兼顾理解意图、选择策略、验证质量、生成答案时，Prompt 过长导致决策质量下降。Multi-Agent 把职责拆分给多个专职 Agent：

```
用户 query
    │
    ▼
Router Agent（分发）
    │ 识别意图
    ├─ document_qa   ──► Doc Agent（向量/BM25检索 + 推理）
    ├─ data_analysis ──► SQL Agent（text2sql + 聚合）
    └─ graph_query   ──► Graph Agent（Neo4j 多跳遍历）
                              │
                              ▼ raw_answer
                    Verification Agent（质检）
                              │ 发现问题则提修改建议
                              ▼ verified_answer
                    Writer Agent（润色，统一输出风格）
                              │
                              ▼ final_answer
```

**适用**：数据源多、权限复杂、语言多样的企业级知识库。每个 Agent 可独立优化扩展，互不耦合。当前版本以单 `HybridSearchEngine` + 多通道并发代替，Multi-Agent 作为后续扩展点。

---

## 12. Speculative RAG

借鉴推测性解码（Speculative Decoding）思想，目标是**降低生成延迟**：把检索到的文档拆成多个子集，多个小模型**并行**生成候选草稿，最后由大模型一次验证选最优，整体耗时 ≈ 单个小模型生成时间，而非串行叠加。

```
检索候选集（k=15）
    │ 拆成 N 个子集
    ▼
[subset_1] [subset_2] [subset_3] [subset_4] [subset_5]
    │           │           │           │           │
 small_LM   small_LM   small_LM   small_LM   small_LM（并行）
    │           │           │           │           │
 draft_1    draft_2    draft_3    draft_4    draft_5
    └───────────────────────┬───────────────────────┘
                            ▼
                      large_LM 验证并选最优草稿
                            │
                            ▼
                       final_answer
```

**适用**：延迟敏感、且有多个轻量模型可用的场景。当前版本以多通道并发检索压缩检索延迟为主；生成侧 Speculative 模式作为后续扩展点（需要部署小模型 endpoint）。

---

## 13. 与路由器集成

路由器 `AdaptiveRAGRouter` 输出的 `complexity` 字符串映射到 Profile：

```python
# app/rag/router.py  (updated mapping)
from app.rag.retrieval_profiles import PROFILE_MAP, RetrievalConfig

def method_to_profile(complexity: str) -> RetrievalConfig:
    return PROFILE_MAP.get(complexity, PROFILE_MAP["simple"])
```

路由器 prompt 中 `complexity` 字段取值与 Profile key 对齐：

| 路由器判断 | 映射 Profile | 检索通道 | 精排 |
|-----------|-------------|---------|------|
| `simple` | PROFILE_SIMPLE | Dense + Sparse + BM25 | lightweight |
| `moderate` | PROFILE_MODERATE | Dense + Sparse + BM25，multi_query | cross_encoder |
| `complex` | PROFILE_COMPLEX | Dense + Sparse + BM25 + Graph，hyde | cross_encoder |
| `analytical` | PROFILE_ANALYTICAL | SQL only | none |
| `uncertain` | PROFILE_UNCERTAIN | Dense + Sparse + BM25，CRAG + web | cross_encoder |

---

## 14. 评估：RAGAS 框架

怎么知道当前的 `RetrievalConfig` 配置组合效果好不好？用 **RAGAS** 评估框架，四个核心指标：

| 指标 | 含义 | 对应调优方向 |
|------|------|------------|
| **忠实度**（Faithfulness） | 答案有没有编造文档中没有的内容（幻觉检测） | 精排质量↑ 或开启 self_rag 验证 |
| **答案相关性**（Answer Relevancy） | 回答是否切题，有没有答非所问 | 查询扩展策略选择 |
| **上下文精确率**（Context Precision） | 检索回来的文档中，真正有用的占比 | 精排层 rerank 级别↑ |
| **上下文召回率**（Context Recall） | 应该搜到的关键文档是否都搜到了 | channel_top_k / fusion_top_k↑，或开 graph 通道 |

评估建议：先跑 PROFILE_SIMPLE 基线，发现哪个指标低再针对性调整 Profile 参数，不要一上来就堆满所有通道。

---

## 15. 方法溯源对照

原 16 种方法在新设计中的归属：

| 原方法 | 新设计中的位置 |
|--------|-------------|
| Naive RAG | `dense=True` only，`rerank=none`（等同 PROFILE_SIMPLE 关掉 sparse/bm25）|
| Multi-Query | `expansion=multi_query`，见第 8.1 节 |
| HyDE | `expansion=hyde`，见第 8.2 节 |
| Hybrid Search | `dense=True, sparse=True, bm25=True`（核心默认配置）|
| Parent-Child Retrieval | 索引层强制应用，见第 3.3 节 |
| Reranking | `rerank=lightweight / cross_encoder`，见第 9 节 |
| Corrective RAG | `validation=crag, web_fallback=True`，见第 10.1 节 |
| Self-RAG | `validation=self_rag`，见第 10.2 节 |
| Adaptive RAG | 路由器层已实现，见 `030-rag/overview.md` |
| GraphRAG | `graph=True`，见第 7.3 节 |
| Text-to-SQL | `sql=True`，PROFILE_ANALYTICAL |
| Agentic RAG | 见第 11.1 节，当前为扩展点 |
| Multi-Agent RAG | 见第 11.2 节，当前为扩展点 |
| Multimodal RAG | 当前 wiki 场景为纯文本，暂不实现 |
| Speculative RAG | 见第 12 节，生成侧当前为扩展点 |
