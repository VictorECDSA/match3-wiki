# 稀疏向量（Sparse Vector）

**稀疏向量**是指绝大多数维度为零、只有少数维度有值的向量。维度对应词表中的词项，非零值表示该词在文档中的权重。稀疏向量天然擅长精确关键词匹配，能弥补稠密向量在专有名词上的语义漂移问题。

## BM42 算法

本项目使用 **BM42** 生成稀疏向量。BM42 由 Qdrant 提出，将经典的 BM25（Best Match 25，见[BM25 文档](../../fulltext-search/lib/BM25.md)）词频统计与 Transformer 注意力权重结合：用注意力分数替换 BM25 的词频-逆文档频率（TF-IDF）计算，使稀疏向量兼具统计精确性和语义感知能力。

```python
# Milvus sparse vector field
FieldSchema(
    name="sparse_vector",
    dtype=DataType.SPARSE_FLOAT_VECTOR,  # variable-length, stored as {token_id: weight}
)
```

## 存储格式

稀疏向量在 Milvus 中以字典形式存储，键为词表中的词项 ID，值为浮点权重：

```python
# Example sparse vector (most dimensions omitted, they are 0)
{
    42891: 0.73,   # token id for "retention"
    18234: 0.61,   # token id for "match3"
    7102:  0.44,   # token id for "level"
}
```

## 与稠密向量配合使用

稀疏向量与稠密向量并行写入同一 Collection，查询时两路并行检索，再通过倒数排名融合（RRF）合并结果：

- 稠密向量：捕获"留存策略"与"用户粘性"的语义近似
- 稀疏向量：精确匹配"Day-1 留存"等专业术语

两者互补，构成混合检索（Hybrid Search）的基础。
