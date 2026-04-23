# Graph Database Implementation — Neo4j

## 概述

Match3 使用 **Neo4j** 作为知识图谱数据库，存储从文档中提取的实体和关系：

- **实体节点**：游戏、公司、指标、日期、机制
- **关系边**：开发、发布、使用、关联

## 适配器实现

### Neo4jAdapter

```python
# app/intelligence/graph_db/neo4j_adapter.py
from neo4j import Driver, GraphDatabase
from app.runtime import Match3Runtime


class Neo4jAdapter:
    """Neo4j 适配器，实现 GraphDB Protocol。"""

    def __init__(self, rt: Match3Runtime):
        self.driver: Driver = rt.neo4j
        self.logger = rt.logger

    def create_node(
        self,
        label: str,
        properties: dict,
        workspace_id: int,
    ) -> int:
        """创建节点，返回节点 ID。"""
        with self.driver.session() as session:
            result = session.run(
                f"""
                CREATE (n:{label} $props)
                SET n.workspace_id = $workspace_id
                RETURN id(n) AS node_id
                """,
                props=properties,
                workspace_id=workspace_id,
            )
            node_id = result.single()["node_id"]
            self.logger.debug(f"Created {label} node: {node_id}")
            return node_id

    def create_relationship(
        self,
        from_node_id: int,
        to_node_id: int,
        rel_type: str,
        properties: dict | None = None,
    ):
        """创建关系。"""
        with self.driver.session() as session:
            session.run(
                f"""
                MATCH (a), (b)
                WHERE id(a) = $from_id AND id(b) = $to_id
                CREATE (a)-[r:{rel_type} $props]->(b)
                RETURN r
                """,
                from_id=from_node_id,
                to_id=to_node_id,
                props=properties or {},
            )
            self.logger.debug(f"Created relationship: {rel_type}")

    def find_neighbors(
        self,
        node_id: int,
        rel_type: str | None = None,
        direction: str = "both",
        max_hops: int = 1,
    ) -> list[dict]:
        """查找邻居节点。
        
        Args:
            node_id: 起始节点 ID
            rel_type: 关系类型（None 表示所有类型）
            direction: "outgoing" | "incoming" | "both"
            max_hops: 最大跳数
        """
        direction_pattern = {
            "outgoing": "->",
            "incoming": "<-",
            "both": "-",
        }[direction]
        
        rel_pattern = f"[r:{rel_type}]" if rel_type else "[r]"
        pattern = f"(start){direction_pattern}{rel_pattern}{direction_pattern}(neighbor)"
        
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH path = (start){direction_pattern}{rel_pattern * max_hops}{direction_pattern}(neighbor)
                WHERE id(start) = $node_id
                RETURN DISTINCT
                  id(neighbor) AS neighbor_id,
                  labels(neighbor) AS labels,
                  properties(neighbor) AS properties,
                  type(r) AS rel_type
                """,
                node_id=node_id,
            )
            
            return [
                {
                    "id": record["neighbor_id"],
                    "labels": record["labels"],
                    "properties": dict(record["properties"]),
                    "rel_type": record["rel_type"],
                }
                for record in result
            ]

    def cypher_query(self, query: str, params: dict | None = None) -> list[dict]:
        """执行 Cypher 查询。"""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]

    def get_subgraph(
        self,
        entity_name: str,
        workspace_id: int,
        max_depth: int = 2,
    ) -> dict:
        """获取实体的子图。"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (start)
                WHERE start.name = $entity_name
                  AND start.workspace_id = $workspace_id
                MATCH path = (start)-[*1..$max_depth]-(connected)
                WHERE connected.workspace_id = $workspace_id
                RETURN
                  collect(DISTINCT nodes(path)) AS nodes,
                  collect(DISTINCT relationships(path)) AS rels
                """,
                entity_name=entity_name,
                workspace_id=workspace_id,
                max_depth=max_depth,
            )
            
            record = result.single()
            if not record:
                return {"nodes": [], "relationships": []}
            
            nodes = [self._node_to_dict(n) for n in record["nodes"][0]]
            rels = [self._rel_to_dict(r) for r in record["rels"][0]]
            
            return {"nodes": nodes, "relationships": rels}

    def _node_to_dict(self, node) -> dict:
        """将 Neo4j 节点转为字典。"""
        return {
            "id": node.id,
            "labels": list(node.labels),
            "properties": dict(node),
        }

    def _rel_to_dict(self, rel) -> dict:
        """将 Neo4j 关系转为字典。"""
        return {
            "id": rel.id,
            "type": rel.type,
            "start_node_id": rel.start_node.id,
            "end_node_id": rel.end_node.id,
            "properties": dict(rel),
        }
```

## Runtime 集成

```python
# app/runtime.py (build_runtime 部分)
from neo4j import GraphDatabase
from app.intelligence.graph_db.neo4j_adapter import Neo4jAdapter

def build_runtime(config: Config, env: Env, logger: Logger) -> Match3Runtime:
    """构建 Runtime 实例"""
    
    neo4j_driver = GraphDatabase.driver(
        env.NEO4J_URI,
        auth=(env.NEO4J_USER, env.NEO4J_PASSWORD),
        max_connection_lifetime=config.neo4j.max_connection_lifetime,
        max_connection_pool_size=config.neo4j.max_connection_pool_size,
    )
    
    neo4j_adapter = Neo4jAdapter(
        driver=neo4j_driver,
        logger=logger,
    )
    
    logger.info("Neo4j adapter initialized")

    return Match3Runtime(
        # ...
        neo4j=neo4j_adapter,
        # ...
    )
```

## 数据模型

### 节点类型

| 标签 | 属性 | 说明 |
|------|------|------|
| `Game` | `name`, `genre`, `platform` | 游戏实体 |
| `Company` | `name`, `country` | 公司实体 |
| `Metric` | `name`, `value`, `unit` | 指标实体 |
| `Date` | `year`, `month`, `day` | 日期实体 |
| `Mechanism` | `name`, `description` | 游戏机制 |

所有节点都有 `workspace_id` 属性用于多租户隔离。

### 关系类型

| 关系类型 | 起始节点 | 结束节点 | 说明 |
|---------|---------|---------|------|
| `DEVELOPED_BY` | `Game` | `Company` | 游戏开发商 |
| `PUBLISHED_BY` | `Game` | `Company` | 游戏发行商 |
| `RELEASED_ON` | `Game` | `Date` | 游戏发布日期 |
| `HAS_METRIC` | `Game` | `Metric` | 游戏指标 |
| `USES_MECHANISM` | `Game` | `Mechanism` | 游戏使用的机制 |

## 使用示例

### 创建实体和关系

```python
from app.intelligence.graph_db.neo4j_adapter import Neo4jAdapter

adapter = Neo4jAdapter(rt)

# 创建游戏节点
game_id = adapter.create_node(
    label="Game",
    properties={"name": "Candy Crush", "genre": "Puzzle"},
    workspace_id=1,
)

# 创建公司节点
company_id = adapter.create_node(
    label="Company",
    properties={"name": "King", "country": "Sweden"},
    workspace_id=1,
)

# 创建关系
adapter.create_relationship(
    from_node_id=game_id,
    to_node_id=company_id,
    rel_type="DEVELOPED_BY",
    properties={"year": 2012},
)
```

### 查找邻居节点

```python
neighbors = adapter.find_neighbors(
    node_id=game_id,
    rel_type="DEVELOPED_BY",
    direction="outgoing",
    max_hops=1,
)

for neighbor in neighbors:
    print(f"{neighbor['labels']}: {neighbor['properties']['name']}")
```

### 执行 Cypher 查询

```python
# 查找某个工作空间的所有游戏
results = adapter.cypher_query(
    """
    MATCH (g:Game)
    WHERE g.workspace_id = $workspace_id
    RETURN g.name AS name, g.genre AS genre
    ORDER BY g.name
    """,
    params={"workspace_id": 1},
)

for record in results:
    print(f"{record['name']} - {record['genre']}")
```

### 获取实体子图

```python
subgraph = adapter.get_subgraph(
    entity_name="Candy Crush",
    workspace_id=1,
    max_depth=2,
)

print(f"Nodes: {len(subgraph['nodes'])}")
print(f"Relationships: {len(subgraph['relationships'])}")
```

## 索引和约束

### 创建索引

```cypher
// 为节点 name 创建索引
CREATE INDEX game_name_idx FOR (g:Game) ON (g.name);
CREATE INDEX company_name_idx FOR (c:Company) ON (c.name);

// 为 workspace_id 创建索引（多租户隔离）
CREATE INDEX game_workspace_idx FOR (g:Game) ON (g.workspace_id);
CREATE INDEX company_workspace_idx FOR (c:Company) ON (c.workspace_id);
```

### 创建唯一约束

```cypher
// 防止重复实体
CREATE CONSTRAINT game_unique
FOR (g:Game) REQUIRE (g.name, g.workspace_id) IS UNIQUE;

CREATE CONSTRAINT company_unique
FOR (c:Company) REQUIRE (c.name, c.workspace_id) IS UNIQUE;
```

## 配置参数

### Config (config.yaml)

```yaml
neo4j:
  max_connection_lifetime: 3600    # 连接最大生命周期（秒）
  max_connection_pool_size: 50     # 连接池大小
```

### Env (.env)

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

## 性能优化

### 1. 批量创建

使用 `UNWIND` 批量创建节点和关系：

```python
data = [
    {"name": "Game1", "genre": "Action"},
    {"name": "Game2", "genre": "Puzzle"},
]

adapter.cypher_query(
    """
    UNWIND $data AS row
    CREATE (g:Game)
    SET g.name = row.name, g.genre = row.genre, g.workspace_id = $workspace_id
    """,
    params={"data": data, "workspace_id": 1},
)
```

### 2. 避免全图扫描

始终在 `MATCH` 中使用 `workspace_id` 过滤：

```cypher
// ✅ 正确
MATCH (g:Game)
WHERE g.workspace_id = 1
RETURN g

// ❌ 错误（全图扫描）
MATCH (g:Game)
RETURN g
```

### 3. 使用 APOC

安装 APOC 插件以使用高级功能：

```cypher
// 批量更新
CALL apoc.periodic.iterate(
  "MATCH (g:Game) WHERE g.workspace_id = 1 RETURN g",
  "SET g.updated_at = timestamp()",
  {batchSize: 1000}
)
```

## 相关文档

- **[protocol.md](./protocol.md)** — GraphDB Protocol 定义
- **[../../design/solution-final/030-rag/](../../design/solution-final/030-rag/)** — 知识图谱 RAG 路径
