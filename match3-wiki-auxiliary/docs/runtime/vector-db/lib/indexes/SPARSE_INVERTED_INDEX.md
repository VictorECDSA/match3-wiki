# SPARSE_INVERTED_INDEX 索引

**SPARSE_INVERTED_INDEX（稀疏倒排索引）** 是 Milvus 为稀疏向量（Sparse Vector）专门设计的索引类型，基于传统倒排索引原理，仅对非零维度建立索引，从而高效处理高维稀疏数据。

## 为什么稀疏向量需要专用索引

稠密向量（Dense Vector）每个维度都有值，适合 HNSW、IVF_FLAT 等基于欧氏距离图结构的索引。稀疏向量（如 BM42、BM25 生成的词频向量）维度可达数万，但绝大多数维度为 0，只有少数词汇对应的维度有非零权重。若用 HNSW 处理稀疏向量，会在大量零值上浪费计算；SPARSE_INVERTED_INDEX 只存储和计算非零维度，与倒排索引对文档词汇的处理方式一致。

## 工作原理

```
维度（词汇ID） → 文档列表（仅记录该维度非零的向量）

dim_42  → [(vec_1, 0.3), (vec_5, 0.8), (vec_9, 0.1)]
dim_137 → [(vec_2, 0.5), (vec_5, 0.2)]
...
```

查询时，取查询向量中的非零维度集合，查对应的倒排列表，累加内积（Inner Product）分数，返回 top-k。

## 参数说明

| 参数 | 含义 | 典型值 |
|------|------|--------|
| `drop_ratio_build` | 构建索引时丢弃权重最小的维度比例，减少索引体积 | `0.2`（丢弃最低 20% 的维度） |
| `drop_ratio_search` | 搜索时丢弃查询向量中权重最小的维度比例，加速查询 | `0.1` |

```python
client.create_index(
    collection_name="match3_hybrid",
    field_name="sparse_vector",
    index_type="SPARSE_INVERTED_INDEX",
    metric_type="IP",                        # must be Inner Product for sparse
    params={
        "drop_ratio_build": 0.2,
        "drop_ratio_search": 0.1,
    },
)
```

## 为什么必须配合 IP 度量

稀疏向量的相似度语义是词汇权重的内积（Inner Product），即两个向量中共同非零维度权重之积的总和。COSINE（余弦相似度）在稀疏场景下意义退化，L2 距离对零值的差距惩罚与稀疏语义不符，因此 SPARSE_INVERTED_INDEX 只支持 IP 度量。

## 与 HNSW 的对比

| 特性 | SPARSE_INVERTED_INDEX | HNSW |
|------|-----------------------|------|
| 适用向量类型 | 稀疏向量 | 稠密向量 |
| 零值处理 | 跳过（只索引非零维度） | 不适用 |
| 支持度量 | IP 仅 | COSINE / L2 / IP |
| 典型场景 | BM42/BM25 稀疏词频向量 | text-embedding 稠密向量 |

## 在本项目中的位置

混合检索（Hybrid Search）中，`sparse_vector` 字段固定使用 SPARSE_INVERTED_INDEX，`dense_vector` 字段固定使用 HNSW，两路检索结果由 RRF 或加权融合（Weighted Reranker）合并。详见 [../RRF.md](../RRF.md) 与 [../weighted-reranker.md](../weighted-reranker.md)。
