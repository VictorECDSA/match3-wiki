# PageRank 算法

**PageRank** 是 Google 创始人 Larry Page 于 1998 年提出的图算法，用于衡量网络中节点的"重要性"——一个节点被越多重要节点指向，其 PageRank 值越高。在知识图谱中，PageRank 用于识别核心实体（被大量其他实体引用的概念）。

## 基本思想

把图中的每条有向边视为一次"投票"，节点的重要性由投票者的重要性决定：

$$PR(u) = \frac{1-d}{N} + d \sum_{v \in \text{in}(u)} \frac{PR(v)}{|\text{out}(v)|}$$

其中：
- $d$ 为阻尼系数（Damping Factor），通常取 0.85
- $N$ 为节点总数
- $\text{in}(u)$ 为指向 $u$ 的节点集合
- $|\text{out}(v)|$ 为节点 $v$ 的出度

## 在 Neo4j 中的使用（GDS 插件）

PageRank 由图数据科学插件（GDS，Graph Data Science）提供：

```cypher
// Project graph into GDS catalog
CALL gds.graph.project(
    'entityGraph',
    'Entity',
    'RELATION'
)

// Run PageRank
CALL gds.pageRank.stream('entityGraph', {
    maxIterations: 20,
    dampingFactor: 0.85
})
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS entity, score
ORDER BY score DESC
LIMIT 20
```

## 应用场景

在本项目知识图谱中，PageRank 可用于：
- 识别被大量文档引用的核心三消游戏概念
- 为 GraphRAG 查询提供节点重要性权重，优先返回高影响力实体
- 可视化知识图谱时突出核心节点

PageRank 属于离线分析任务，不在实时检索链路中执行，通常作为定期批处理运行。详见 [GDS 文档](./GDS.md)。
