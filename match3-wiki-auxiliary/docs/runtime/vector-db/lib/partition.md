# Partition（分区）

**Partition（分区）** 是 Milvus Collection 内的逻辑子分组：同一 Collection 的数据被划分到多个 Partition，搜索时可以只扫描指定 Partition，从而跳过无关数据、降低延迟。

## 核心概念

每个 Collection 默认包含一个名为 `_default` 的 Partition。用户可追加自定义 Partition，每个 Partition 在物理上独立存储其向量和标量数据，但共享同一 Collection 的 Schema 和索引配置。

```python
# Create a partition for each workspace
client.create_partition(
    collection_name="match3_dense",
    partition_name="workspace_1",
)

# Insert into a specific partition
client.insert(
    collection_name="match3_dense",
    data=data,
    partition_name="workspace_1",
)

# Search only within a specific partition
results = client.search(
    collection_name="match3_dense",
    data=[query_vector],
    limit=10,
    partition_names=["workspace_1"],   # skip all other partitions
)
```

## 在本项目中的用途：工作区隔离

本项目将每个 `workspace_id` 映射到一个 Partition，实现工作区之间的搜索隔离：

- 用户查询时只在自己工作区的 Partition 内搜索，不会看到其他工作区的数据
- 删除工作区时，只需 `drop_partition(partition_name)` 即可批量清除该工作区的所有向量，无需逐条按 `filter` 删除

## 与"每工作区一个 Collection"的对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| 一个 Collection + Partition 隔离 | 资源开销低；跨工作区统计方便 | 单 Collection 的 Partition 数有上限（默认 4096） |
| 每工作区独立 Collection | 隔离最彻底 | Collection 数量多时管理复杂；内存开销大 |

本项目工作区数量有限，选择 Partition 方案；若工作区数量极大，可改为 Collection 方案或在 `filter` 字段上做逻辑隔离。

## 注意事项

- Partition 数量上限：Milvus 默认每个 Collection 最多 4096 个 Partition
- 索引在 Collection 级别统一管理，不能对不同 Partition 设置不同索引
- `partition_names` 为空列表时，Milvus 搜索所有 Partition（等同于不指定）
