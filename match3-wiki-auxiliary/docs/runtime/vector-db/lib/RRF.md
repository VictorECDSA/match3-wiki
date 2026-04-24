# RRF（倒数排名融合）

**RRF（Reciprocal Rank Fusion，倒数排名融合）** 是一种将多个排序列表合并为单一排序的算法，由 Cormack 等人于 2009 年提出。它不依赖各列表的原始分数，只关注排名位置，因此天然适合融合量纲不同的检索结果（如向量相似度分 vs BM25 相关性分）。

## 计算公式

$$\text{RRF}(d) = \sum_{i=1}^{n} \frac{1}{k + r_i(d)}$$

其中：
- $d$ 为文档
- $r_i(d)$ 为文档 $d$ 在第 $i$ 个列表中的排名（从 1 开始）
- $k$ 为平滑常数，通常取 60
- 文档在某列表中不存在时，视为排名无穷大，贡献为 0

```python
def rrf_merge(result_lists: list[list[str]], k: int = 60) -> list[str]:
    """Merge multiple ranked ID lists using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    for ranked_list in result_lists:
        for rank, doc_id in enumerate(ranked_list, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda x: scores[x], reverse=True)
```

## 为什么用 RRF 而不直接加权求和

- **无需归一化**：Milvus 余弦相似度范围 [-1, 1]，BM25 分数范围可达数十，直接相加意义不明
- **鲁棒性强**：任一单路检索失效（如某查询无 BM25 命中），RRF 自动退化为其他路的结果，不崩溃
- **简单有效**：无超参数调优负担，k=60 在绝大多数场景表现良好

## 在本项目中的应用

混合检索（Hybrid Search）中，稠密向量（Dense）、稀疏向量（Sparse）、BM25 三路并行检索后，用 RRF 合并：

```python
all_ranked = rrf_merge([dense_ids, sparse_ids, bm25_ids], k=60)
top_50_ids = all_ranked[:50]
```

融合后取 top-50，再交给 Reranker 精排到 top-8，作为 LLM 生成的上下文。
