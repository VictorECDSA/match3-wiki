# 分片与副本（Shard & Replica）

Elasticsearch 通过分片和副本实现水平扩展与高可用，是分布式全文搜索的基础架构概念。

## 分片（Shard）

**主分片（Primary Shard）** 是 Elasticsearch 索引水平切分的基本单位。一个索引被拆分为 N 个主分片，每个分片是一个完整的 Lucene 实例，包含完整的倒排索引结构。

- 分片数在索引创建时确定，**之后不可更改**（除非重建索引）
- 查询时所有分片并行执行，协调节点（Coordinating Node）汇总结果
- 单节点部署时多个分片分配在同一机器，不带来分布式收益但为后续扩容预留空间

```json
{
  "settings": {
    "number_of_shards": 1,      // single-node deployment, no need to split
    "number_of_replicas": 0
  }
}
```

## 副本（Replica）

**副本分片（Replica Shard）** 是主分片的完整拷贝，提供两个作用：

1. **高可用**：主分片所在节点宕机时，副本自动提升为主分片
2. **读扩展**：查询可以路由到副本，分散读压力

副本数可在运行时动态调整。单节点部署时副本无法分配到不同节点（副本不能与对应主分片在同一节点），因此设为 0。

## 本项目的配置

本项目单节点部署，`text_chunks` 索引配置为 1 分片 0 副本，最大化写入性能：

```python
index_settings = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "1s",
    }
}
```

若未来扩展为多节点集群，可增加副本数实现高可用，无需修改业务代码。
