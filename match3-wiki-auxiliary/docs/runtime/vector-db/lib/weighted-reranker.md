# 加权融合重排序（Weighted Reranker）

**加权融合重排序（Weighted Reranker）** 是混合检索中将多路检索结果合并为单一排序的方法之一：为每路检索结果赋予显式权重，按加权分数排序，最终输出 top-k 结果。

## 与 RRF 的对比

Milvus 混合检索（Hybrid Search）支持两种重排策略：

| 特性 | RRF（倒数排名融合） | Weighted Reranker（加权融合） |
|------|---------------------|-------------------------------|
| 依据 | 排名位置 | 原始相似度分数 |
| 需要归一化 | 否 | 是（各路分数量纲必须可比） |
| 超参数 | `k`（平滑常数，默认 60） | `weights`（每路权重列表） |
| 适用场景 | 多路分数量纲不同；鲁棒性优先 | 对某路检索有明确偏好；分数量纲已归一化 |

## 使用方式

```python
results = client.hybrid_search(
    collection_name="match3_hybrid",
    data=[{"dense": dense_vec[0], "sparse": sparse_vec[0]}],
    limit=20,
    reranker="weighted",
    reranker_params={"weights": [0.7, 0.3]},   # 70% dense + 30% sparse
    output_fields=["text"],
)
```

`weights` 列表的顺序与 `data` 中向量字段的顺序对应：第一个权重对应 `dense_vector`，第二个对应 `sparse_vector`。权重不必加和为 1，Milvus 内部会归一化。

## 何时选择加权融合而非 RRF

- 经过实验，确认稠密向量对特定查询类型明显优于稀疏向量（或反之），需要通过权重放大优势路
- 所有检索路的分数已通过归一化处理，量纲相同，可以直接加权
- 业务上希望显式控制语义理解（dense）与关键词匹配（sparse）的相对重要性

本项目默认使用 RRF（无需调参、对量纲不敏感），加权融合作为可选配置，在特定场景下通过实验调整 `weights` 参数以提升召回质量。RRF 详见 [./RRF.md](./RRF.md)。
