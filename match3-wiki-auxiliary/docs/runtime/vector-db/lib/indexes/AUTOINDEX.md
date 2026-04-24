# AUTOINDEX

**AUTOINDEX** 是 Milvus 的自动索引选择机制：用户无需手动指定索引类型和参数，Milvus 根据向量维度、数据规模和硬件资源自动选择最优索引类型（通常为 HNSW 变体）并配置参数。

## 工作方式

```python
client.create_index(
    collection_name="match3_dense",
    field_name="dense_vector",
    index_type="AUTOINDEX",     # let Milvus decide
    metric_type="COSINE",
)
```

Milvus 服务端在接收到 `AUTOINDEX` 请求后，综合以下因素决定实际索引类型：

- 向量维度（低维 vs 高维）
- 当前数据量（小集合可能用 FLAT，中大集合用 HNSW 或 DiskANN）
- 可用内存与磁盘资源
- Milvus 版本内置的推荐策略

## 优缺点

| 优点 | 缺点 |
|------|------|
| 开箱即用，无需调参经验 | 实际使用何种索引对用户不透明 |
| 随 Milvus 升级自动获得更优默认值 | 无法精细控制 `M`、`efConstruction` 等参数 |
| 适合快速原型和不确定数据规模的早期阶段 | 生产环境难以预测性能边界 |

## 与显式指定索引的对比

| 场景 | 推荐做法 |
|------|----------|
| 开发/原型阶段，数据量未定 | AUTOINDEX |
| 生产环境，数据量已知，需要精确控制性能 | 显式指定 HNSW / DiskANN / IVF_SQ8 |
| 稀疏向量 | 必须显式指定 SPARSE_INVERTED_INDEX（AUTOINDEX 不支持稀疏向量） |

## 在本项目中的位置

性能优化文档（`milvus-v2.6.14.md` 索引选择表）将 AUTOINDEX 列为"自动选择（推荐）"选项。本项目在生产配置中对 `dense_vector` 字段显式使用 HNSW，对 `sparse_vector` 字段显式使用 SPARSE_INVERTED_INDEX，以确保参数可控。AUTOINDEX 在开发环境或 Collection 初始化阶段用作快捷方式。
