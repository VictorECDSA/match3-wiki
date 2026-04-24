# 相似度度量（Similarity Metrics）

向量检索需要一种度量方式来量化两个向量之间的"距离"或"相似度"。Milvus 支持三种主流度量，选择时需与向量的生成方式匹配。

## 三种度量对比

| 度量 | 全称 | 含义 | 返回值语义 |
|------|------|------|------------|
| `COSINE` | Cosine Similarity，余弦相似度 | 两向量夹角的余弦值 | 值越大越相似（范围 -1 到 1） |
| `L2` | L2 Distance，欧氏距离 | 两向量在空间中的直线距离 | 值越小越相似（≥0） |
| `IP` | Inner Product，内积 | 两向量的点积 | 值越大越相似（若向量已归一化，等价于 COSINE） |

## COSINE

余弦相似度只关注方向，不受向量模长影响，是文本嵌入的首选度量：

```python
# cosine similarity formula
cos_sim = dot(a, b) / (norm(a) * norm(b))
```

`text-embedding-3-small` 的输出向量已归一化，此时 COSINE 与 IP 数值等价，但语义更直观。

## L2

欧氏距离同时考虑方向和模长，适合未归一化的向量（如某些图像嵌入）：

```python
l2_dist = sqrt(sum((a_i - b_i) ** 2 for i in range(dim)))
```

## IP

内积计算速度最快（无需归一化除法），若模型输出已单位归一化，可用 IP 替代 COSINE 获得相同结果但更低延迟：

```python
ip = sum(a_i * b_i for i in range(dim))
```

## 本项目的选择

- **文本稠密向量**（`match3_chunks.dense_vector`）：使用 `COSINE`
- **稀疏向量**（`match3_chunks.sparse_vector`）：使用 `IP`
- **图片 CLIP 向量**（`image_chunks.dense_vector`）：使用 `COSINE`
