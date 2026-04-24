# DiskANN 索引

**DiskANN** 是微软研究院于 2019 年提出的基于磁盘的近似最近邻（ANN）索引，专为数据集规模超出内存容量的场景设计。其核心思路是将图结构持久化到 SSD，只将压缩后的量化向量留在内存，搜索时按需从磁盘读取原始向量完成精排。

## 工作原理

DiskANN 将向量存储分为两层：

- **内存层**：保存 PQ（Product Quantization，乘积量化）压缩后的低精度向量，用于快速粗筛
- **磁盘层**：保存完整的图结构和原始向量，用于最终精排

搜索流程：先用内存中的压缩向量定位候选节点，再从 SSD 读取这些节点的原始向量做精确距离计算。依赖现代 SSD 的随机读 IOPS，延迟通常在几十毫秒内。

## Milvus 中的配置

```python
index_params = {
    "metric_type": "COSINE",
    "index_type": "DISKANN",
    "params": {
        "search_list": 100,   # candidate list size during build, larger = better quality
    },
}
search_params = {
    "search_list": 100,       # candidate list size during search
}
```

## 适用场景

| 场景 | 推荐索引 |
|------|----------|
| 数据量 < 内存容量 | [HNSW](./HNSW.md) |
| 数据量 > 内存容量 | **DiskANN** |
| 极低内存 + 可接受较低召回率 | [IVF_FLAT](./IVF_FLAT.md) |

本项目默认使用 HNSW；若未来向量数据规模超出服务器内存，切换至 DiskANN 只需修改 `index_params`，业务代码无需改动。
