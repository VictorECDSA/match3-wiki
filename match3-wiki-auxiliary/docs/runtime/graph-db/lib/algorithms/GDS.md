# GDS（图数据科学插件）

**GDS（Graph Data Science）** 是 Neo4j 官方提供的图算法插件，内置 65+ 种图算法（社区发现、中心性、相似度、路径等），支持在 Neo4j 数据库内直接对图数据执行大规模并行图计算。

## 工作模式

GDS 采用"内存图投影（In-Memory Graph Projection）"模式：先将 Neo4j 中的子图投影到内存中的优化格式，再在内存图上运行算法，最后将结果写回 Neo4j 或直接流式返回。

```cypher
-- Step 1: Project subgraph into GDS memory
CALL gds.graph.project(
    'myGraph',           -- graph name in GDS catalog
    'Entity',            -- node label(s)
    'RELATION'           -- relationship type(s)
)

-- Step 2: Run algorithm (stream mode: return results without writing back)
CALL gds.pageRank.stream('myGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name, score
ORDER BY score DESC

-- Step 3: Clean up
CALL gds.graph.drop('myGraph')
```

## 主要算法分类

| 类别 | 算法示例 |
|------|----------|
| 中心性（Centrality） | PageRank、Betweenness Centrality、Degree Centrality |
| 社区发现（Community Detection） | Louvain、Label Propagation、WCC |
| 相似度（Similarity） | Node Similarity、KNN |
| 路径（Path Finding） | Shortest Path（Dijkstra）、A* |

## 与 APOC 的区别

| 维度 | GDS | APOC |
|------|-----|------|
| 定位 | 图算法计算框架 | 通用工具函数库 |
| 典型用途 | PageRank、社区发现、相似度计算 | 字符串处理、批量导入、HTTP 调用 |
| 内存图投影 | ✓ | ✗ |

GDS 是图分析层的核心插件，APOC 是开发辅助工具（见 [APOC 文档](../plugins/APOC.md)）。
