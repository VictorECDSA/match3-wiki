# IVF_SQ8 索引

**IVF_SQ8（Inverted File Index with Scalar Quantization 8-bit，倒排文件索引-标量量化8位）** 是 IVF_FLAT 的压缩变体：在 IVF 聚类分区的基础上，将每个向量的每个维度从 float32（4 字节）压缩为 int8（1 字节），内存占用降至 IVF_FLAT 的约 1/4。

## 标量量化（Scalar Quantization）原理

标量量化（SQ）将每个维度的浮点值线性映射到 \[−128, 127\] 的整数区间：

```
int8_val = round((float_val - min_val) / (max_val - min_val) * 255 - 128)
```

查询时用 int8 整数近似计算距离，速度比 float32 更快（SIMD 指令对整数运算更高效），但精度有轻微损失。

## 参数说明

IVF_SQ8 的建索引参数与 IVF_FLAT 完全一致，只是量化精度已固定为 8 位：

| 参数 | 含义 | 典型值 |
|------|------|--------|
| `nlist` | 聚类数量，建议为 `sqrt(N)` | 1024 |
| `nprobe` | 查询时搜索的聚类数（搜索参数） | 16 |

```python
index_params = {
    "metric_type": "COSINE",
    "index_type": "IVF_SQ8",
    "params": {"nlist": 1024},
}
search_params = {"nprobe": 16}
```

## 与 IVF_FLAT / HNSW 对比

| 特性 | HNSW | IVF_FLAT | IVF_SQ8 |
|------|------|----------|---------|
| 内存占用 | 高（float32 + 图结构） | 中（float32） | 低（int8，约 1/4） |
| 查询精度 | 最高 | 高 | 略低（量化误差） |
| 查询速度 | 极快 | 快 | 中等 |
| 适用场景 | 默认推荐 | 平衡场景 | 内存受限的大数据集 |

## 何时选择 IVF_SQ8

- 向量数据量超过百万条，内存无法容纳 HNSW 所需的 float32 全量存储
- 对查询延迟要求不苛刻，可接受轻微精度损失（通常召回率下降 1%–3%）
- DiskANN 因磁盘 I/O 延迟过高时，IVF_SQ8 是纯内存场景下的备选

本项目默认使用 HNSW；在数据量增长导致内存压力时，可将 `dense_vector` 字段的索引切换为 IVF_SQ8 或 [DiskANN](./DiskANN.md)。
