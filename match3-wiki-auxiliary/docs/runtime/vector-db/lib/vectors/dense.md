# 稠密向量（Dense Vector）

**稠密向量**是指每个维度都有非零数值的向量，由神经网络编码器（Encoder）将文本、图像等非结构化数据映射到固定维度的连续实数空间而来。

## 生成方式

文本稠密向量由双编码器模型（Bi-encoder）生成：输入一段文本，输出一个固定长度的浮点数组。本项目使用 OpenAI 的 `text-embedding-3-small`，维度为 1536。

```python
# Example: embed a text chunk
vector: list[float] = embedder.embed("match-3 game retention strategy")
# len(vector) == 1536, all values are non-zero floats
```

## 与稀疏向量的对比

| 特性 | 稠密向量 | 稀疏向量 |
|------|----------|----------|
| 维度 | 固定（如 1536） | 词表大小（数万维） |
| 非零值比例 | 接近 100% | 通常低于 0.1% |
| 捕获能力 | 语义相似度 | 关键词精确匹配 |
| 典型算法 | text-embedding-3-small、CLIP | BM25、BM42 |

## 在 Milvus 中的字段

```python
# dense_vector field in match3_chunks collection
FieldSchema(
    name="dense_vector",
    dtype=DataType.FLOAT_VECTOR,
    dim=1536,
)
```

搜索时使用余弦相似度（COSINE）或内积（IP）度量，配合 HNSW 索引实现近似最近邻（ANN）检索。
