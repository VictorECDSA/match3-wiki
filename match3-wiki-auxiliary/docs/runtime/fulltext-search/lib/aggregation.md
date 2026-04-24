# 聚合（Aggregation）

**聚合（Aggregation）** 是 Elasticsearch 对搜索结果进行统计分析的查询类型，类似于 SQL 中的 `GROUP BY` + 聚合函数。聚合可以嵌套，在桶（Bucket）内再做指标（Metric）计算，实现多维度数据分析。

## 两大类聚合

### 桶聚合（Bucket Aggregation）

将文档按某个字段的值分组，每组形成一个"桶"：

```json
{
  "aggs": {
    "by_workspace": {
      "terms": {
        "field": "workspace_id",
        "size": 10
      }
    }
  }
}
```

常用桶聚合：`terms`（按值分组）、`date_histogram`（按时间区间分组）、`range`（按数值范围分组）。

### 指标聚合（Metric Aggregation）

对文档集合计算统计指标（不分组，或在桶内计算）：

```json
{
  "aggs": {
    "avg_chunk_length": {
      "avg": { "field": "content_length" }
    }
  }
}
```

常用指标聚合：`count`、`sum`、`avg`、`min`、`max`、`cardinality`（去重计数）。

## 聚合与查询组合

聚合可以与 `query` 组合，只对匹配文档做统计：

```json
{
  "query": {
    "term": { "workspace_id": "ws-123" }
  },
  "aggs": {
    "file_type_dist": {
      "terms": { "field": "chunk_type" }
    }
  },
  "size": 0   // return only aggregation results, no hits
}
```

`size: 0` 表示只要聚合结果，不返回文档列表，节省传输带宽。

## 在本项目中的应用

聚合主要用于管理后台的数据统计（如各工作区的文档块数量分布、文件类型占比），不参与核心检索流程。
