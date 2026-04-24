# IVF_FLAT 索引

**IVF_FLAT（Inverted File Index with Flat quantization，倒排文件索引-平坦量化）** 是一种基于聚类的近似最近邻（ANN）索引，将向量空间划分为若干聚类区域，搜索时只在最近的几个聚类内精排，跳过远处聚类以加速查找。

## 工作原理

1. **构建阶段**：用 K-Means 将所有向量聚为 `nlist` 个簇，记录每个簇的质心（Centroid）
2. **搜索阶段**：
   - 计算查询向量与所有质心的距离，找出最近的 `nprobe` 个簇
   - 在这 `nprobe` 个簇内对原始向量（Flat，不做量化压缩）做精确距离计算
   - 返回全局 top-k 结果

```python
index_params = {
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 1024},   # number of clusters
}
search_params = {"nprobe": 16}   # clusters to search per query
```

## 关键参数

| 参数 | 含义 | 权衡 |
|------|------|------|
| `nlist` | 聚类数量，建议为 `sqrt(N)`（N 为向量总数） | 越大分区越细，构建越慢 |
| `nprobe` | 查询时搜索的聚类数 | 越大召回率越高，速度越慢 |

## 与 HNSW 对比

| 特性 | IVF_FLAT | HNSW |
|------|----------|------|
| 内存占用 | 较低（向量可分批加载） | 高（全量在内存） |
| 查询速度 | 较慢 | 较快 |
| 召回率 | 受 `nprobe` 影响大 | 稳定高 |
| 增量插入 | 需重建索引 | 支持 |

IVF_FLAT 适合数据量较大、内存有限、对查询延迟要求不苛刻的场景。Milvus 在数据量较少时会自动降级使用 `FLAT`（暴力搜索），无需手动干预。
