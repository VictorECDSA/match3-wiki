# hybrid-search：五阶段检索流水线

## 查询流程概览

```
raw query → query expansion → parallel multi-channel retrieval → RRF fusion → reranking → validation → generation
```

五个阶段均独立可配置，通过 `RetrievalConfig` 声明式组合。

> 本文件仅覆盖**在线查询侧**。离线索引侧（文档转 Markdown、切块、Parent-Child、三路建索引）详见 `030-rag/processing/chunking.md`。

---

## 1. 五阶段流水线

```
raw query
    │
    ▼
[Stage 1] Query expansion (two independent switches, can both be enabled)
    multi_query: LLM rewrites query into N variants, each retrieved separately then merged
    hyde:        LLM generates a hypothetical answer first, use its vector for retrieval; stackable with multi_query
    (both off → use raw query directly)
    │
    ▼
[Stage 2] Parallel multi-channel retrieval (choose which channels to enable)
    ├── Dense  → Milvus ANN (semantic vector)
    ├── Sparse → Milvus BM42/SPLADE (sparse vector)
    ├── BM25   → Elasticsearch (exact keyword)
    ├── Graph  → Neo4j entity-relation multi-hop traversal
    └── SQL    → PostgreSQL structured aggregate query
    │
    ▼
[Stage 3] Fusion (merge multi-channel results)
    RRF: Reciprocal Rank Fusion
    │
    ▼
[Stage 4] Reranking (optional, increasing cost)
    none:          no rerank, directly truncate top-K
    lightweight:   lightweight reranker initial filter (BGE-reranker-base)
    cross_encoder: Cross-Encoder precise rerank (BGE-reranker-large)
    llm_judge:     LLM per-item scoring (high cost, high precision)
    │
    ▼
[Stage 5] Validation (optional, high-accuracy scenarios)
    none:     no validation, generate directly
    crag:     LLM relevance check; trigger web search fallback if insufficient
    self_rag: generate draft then LLM self-check for document grounding; regenerate if insufficient
```

---

## 2. HybridSearchEngine 实现

```python
# app/rag/hybrid_search_engine.py
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
            queries = await hyde_expand(self._rt, query)
        if cfg.multi_query:
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

## 3. RetrievalConfig：声明式组合

```python
# app/rag/retrieval_config.py
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
                                  #   hyde runs first, then multi_query expands each hyde result

    # --- retrieval channels ---
    dense:  bool = True    # Milvus ANN (text-embedding-3-large, 3072d)
    sparse: bool = True    # Milvus BM42 / BGE-M3 SPLADE
    bm25:   bool = True    # Elasticsearch keyword
    graph:  bool = False   # Neo4j entity-relation traversal
    sql:    bool = False   # PostgreSQL structured query (text2sql)

    # --- graph traversal params (only when graph=True) ---
    graph_hops: int = 2            # max relationship hops
    graph_anchor_top_k: int = 5    # anchor entities from dense results

    # --- domain filter (multi-agent RAG) ---
    domain_filter: str | None = None   # restrict to chunks with matching topic_tags prefix

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

## 4. 效率优化：缩小比对范围

### 4.1 向量检索（Dense / Sparse）：分区 + 预过滤

Milvus 以 `workspace_id` 作为分区键（`partition_key_field`），ANN 搜索天然只在当前工作区的向量空间内比对，无需遍历其他工作区的向量。

```
Full vector space (millions of entries)
  │ partition_key = workspace_id
  ▼
Current workspace vector partition (typically tens of thousands to hundreds of thousands)
  │ scalar pre-filter: file_type / topic_tag / date_range
  ▼
Filtered candidate set (typically thousands)
  │ ANN search (HNSW / IVF_SQ8), ef=64
  ▼
top-50 candidates
```

标量预过滤比 ANN 后过滤效率高：先过滤再向量搜索，候选集小时 HNSW 速度可提升 5-10x。

### 4.2 BM25（Elasticsearch）：倒排索引 + filter 前置

ES 的倒排索引本身已经是"只比对含目标词的文档"，`filter` 子句（`workspace_id`、`file_type`）在 BM25 打分前执行，命中文档数大幅收窄。

### 4.3 图谱检索（Neo4j）：锚点驱动

纯图谱遍历从所有节点出发复杂度爆炸。正确策略：

```
1. Use Dense/Sparse to find top-K anchor chunks first (already narrowed scope)
2. Extract entity_ids from anchor chunks
3. Traverse N hops starting only from these entity_ids:

   MATCH (e)-[*1..2]-(n) WHERE e.id IN $anchor_ids
   // Neo4j builds a composite index on (workspace_id, entity_id)

4. Re-embed-match the subgraph from traversal results
```

`graph_hops` 默认 2，3 跳以上性能急剧下降，通常无必要。

### 4.4 全通道并发

所有启用的检索通道并发执行（`asyncio.gather`），互不阻塞。实测：Dense + Sparse + BM25 三通道并发耗时 ≈ 单通道最慢者（通常 Dense），而非三者之和。

---

## 5. 查询扩展策略

### 5.1 Multi-Query

LLM 将原始 query 改写为 N 个不同表述（换角度、换术语），分别走各通道检索后合并去重再 RRF 融合。

**适用**：用户表述口语化、术语不规范的场景。不适用于专业领域术语已很精准的查询（改写可能带偏）。

### 5.2 HyDE（假设文档嵌入）

LLM 先生成一个假设答案（100-200 字），用假答案向量检索（假答案文体与文档更接近，向量空间距离更近），检索结果再结合原始 query 生成最终答案。

**适用**：技术类问答，用户短问题 vs 文档长段落的 embedding 空间失配。不适用：冷门领域（LLM 可能生成错误假答案把检索带偏）。

---

## 6. 预设 Profile

路由器不再直接映射到某种"方法"，而是映射到一个 `RetrievalConfig` Profile。

```python
# app/rag/retrieval_profiles.py

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

# Complex: deep analysis, graph relationships
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

| 路由器判断 | 映射 Profile | 检索通道 | 精排 |
|-----------|-------------|---------|------|
| `simple` | PROFILE_SIMPLE | Dense + Sparse + BM25 | lightweight |
| `moderate` | PROFILE_MODERATE | Dense + Sparse + BM25，multi_query | cross_encoder |
| `complex` | PROFILE_COMPLEX | Dense + Sparse + BM25 + Graph，hyde | cross_encoder |
| `analytical` | PROFILE_ANALYTICAL | SQL only | none |
| `uncertain` | PROFILE_UNCERTAIN | Dense + Sparse + BM25，CRAG + web | cross_encoder |

---

## 7. 精排层次

```
Candidate set (fusion_top_k = 150)
    │
    │ rerank = lightweight
    ▼
BGE-reranker-base initial filter → top-20
    │
    │ rerank = cross_encoder
    ▼
BGE-reranker-large precise rerank → top-5
    │
    │ rerank = llm_judge (high cost, use sparingly)
    ▼
LLM per-item (query, doc) relevance scoring → top-3
```

生产建议：默认使用 `lightweight`，复杂查询升级到 `cross_encoder`，不建议常规场景使用 `llm_judge`。

---

## 8. 验证机制

### 8.1 CRAG

```
Reranked results
    │
    ▼
LLM judgment: are these documents relevant to the query?
    ├─ relevant     → generate normally
    ├─ partially    → merge web search results then generate
    └─ not relevant → LLM rewrites query → web search fallback → generate
```

**启用条件**：`validation=CRAG, web_fallback=True`，适合时效性强或内部知识库覆盖不全的场景。

### 8.2 Self-RAG

```
Reranked results → LLM generates draft
    │
    ▼
LLM self-check: does every claim in the answer have document support?
    ├─ pass    → output draft
    └─ fail    → regenerate with added instruction "strictly based on references"
```

**启用条件**：`validation=SELF_RAG`，适合准确率要求极高、不能容忍幻觉的场景（如法规、合规类查询）。

---

## 9. Agentic RAG 与 Speculative RAG

### 9.1 Agentic RAG：ReAct 循环

核心是 **ReAct 循环**（Reasoning + Acting）：Agent 每轮先推理再行动，根据当前已知信息决定下一步用哪个工具（`vector_search` / `graph_traverse` / `sql_query` / `web_search`），直到信息足够为止。

**适用**：多数据源混合场景；查询复杂度不可预测时。当前 `PROFILE_COMPLEX` + `graph=True` 可覆盖大多数复杂场景，Agentic 模式作为超复杂场景的扩展点。

### 9.2 Speculative RAG

把检索到的文档拆成多个子集，多个小模型**并行**生成候选草稿，最后由大模型一次验证选最优，整体耗时 ≈ 单个小模型生成时间。

```
Retrieved candidate set (k=15)
    │ split into N subsets
    ▼
[subset_1] [subset_2] [subset_3] [subset_4] [subset_5]
    │           │           │           │           │
 small_LM   small_LM   small_LM   small_LM   small_LM (parallel)
    └───────────────────────┬───────────────────────┘
                            ▼
                      large_LM validates and selects best draft
                            │
                            ▼
                       final_answer
```

**适用**：延迟敏感、且有多个轻量模型可用的场景。当前版本以多通道并发检索压缩检索延迟为主；生成侧 Speculative 模式作为后续扩展点（需要部署小模型 endpoint）。

---

## 10. 评估：RAGAS 框架

| 指标 | 含义 | 对应调优方向 |
|------|------|------------|
| **忠实度**（Faithfulness） | 答案有没有编造文档中没有的内容（幻觉检测） | 精排质量↑ 或开启 self_rag 验证 |
| **答案相关性**（Answer Relevancy） | 回答是否切题，有没有答非所问 | 查询扩展策略选择 |
| **上下文精确率**（Context Precision） | 检索回来的文档中，真正有用的占比 | 精排层 rerank 级别↑ |
| **上下文召回率**（Context Recall） | 应该搜到的关键文档是否都搜到了 | channel_top_k / fusion_top_k↑，或开 graph 通道 |

评估建议：先跑 PROFILE_SIMPLE 基线，发现哪个指标低再针对性调整 Profile 参数，不要一上来就堆满所有通道。

---

## 11. 方法溯源对照

原 16 种方法在新设计中的归属：

| 原方法 | 新设计中的位置 |
|--------|-------------|
| Naive RAG | `dense=True` only，`rerank=none` |
| Multi-Query | `multi_query=True`，见第 5.1 节 |
| HyDE | `hyde=True`，见第 5.2 节 |
| Hybrid Search | `dense=True, sparse=True, bm25=True`（核心默认配置）|
| Parent-Child Retrieval | 索引层强制应用，见 `030-rag/processing/chunking.md` 步骤 3 |
| Reranking | `rerank=lightweight / cross_encoder`，见第 7 节 |
| Corrective RAG | `validation=crag, web_fallback=True`，见第 8.1 节 |
| Self-RAG | `validation=self_rag`，见第 8.2 节 |
| Adaptive RAG | 路由器层已实现，见 `030-rag/retrieval/router.md` |
| GraphRAG | `graph=True`，见第 4.3 节 |
| Text-to-SQL | `sql=True`，PROFILE_ANALYTICAL |
| Agentic RAG | 见第 9.1 节，当前为扩展点 |
| Multi-Agent RAG | 见 `030-rag/retrieval/multi-agent.md` |
| Multimodal RAG | 当前 wiki 场景为纯文本，暂不实现 |
| Speculative RAG | 见第 9.2 节，生成侧当前为扩展点 |
