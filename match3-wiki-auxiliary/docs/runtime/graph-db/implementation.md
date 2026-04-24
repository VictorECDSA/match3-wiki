# Graph Database Implementation — Neo4j

## 概述

使用 **Neo4j** 实现 `GraphDatabase` Protocol，存储和查询知识图谱中的实体和关系。

---

## 工厂函数

```python
# backend/runtime_impl/implements/graph_db/graph_db.py
from neo4j import GraphDatabase
from backend.config import Config, Env
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.graph_db import GraphDatabase as GraphDatabaseProtocol
from .impl_neo4j.neo4j_adapter import Neo4jAdapter

def create_graph_database(config: Config, env: Env, logger: Logger) -> GraphDatabaseProtocol:
    """创建 GraphDatabase 实例
    
    Args:
        config: 配置对象
        env: 环境变量
        logger: 日志记录器
    
    Returns:
        实现了 GraphDatabase Protocol 的 Neo4jAdapter 实例
    
    Raises:
        ValueError: provider 不支持时抛出
    """
    provider = config.runtime.graph_db.provider
    
    if provider == "neo4j":
        neo4j_driver = GraphDatabase.driver(
            env.NEO4J_URI,
            auth=(env.NEO4J_USER, env.NEO4J_PASSWORD),
            max_connection_lifetime=config.runtime.graph_db.implementations.neo4j.max_connection_lifetime,
            max_connection_pool_size=config.runtime.graph_db.implementations.neo4j.max_connection_pool_size,
        )
        
        logger.info("Neo4j driver initialized")
        return Neo4jAdapter(neo4j_driver, logger)
    else:
        raise ValueError(f"Unsupported graph_db provider: {provider}")
```

---

## 适配器实现

```python
# backend/runtime_impl/implements/graph_db/impl_neo4j/neo4j_adapter.py
from neo4j import Driver
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.graph_db import GraphDatabase

class Neo4jAdapter:
    """Neo4j 适配器，实现 GraphDatabase Protocol"""
    
    def __init__(self, driver: Driver, logger: Logger):
        self.driver = driver
        self.logger = logger
    
    def create_node(
        self,
        label: str,
        properties: dict,
        workspace_id: int,
    ) -> int:
        """创建节点，返回节点 ID"""
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
        """创建关系"""
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
        """查找邻居节点"""
        direction_pattern = {
            "outgoing": "->",
            "incoming": "<-",
            "both": "-",
        }[direction]
        
        rel_pattern = f"[r:{rel_type}]" if rel_type else "[r]"
        
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
        """执行 Cypher 查询"""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]
    
    def get_subgraph(
        self,
        entity_name: str,
        workspace_id: int,
        max_depth: int = 2,
    ) -> dict:
        """获取实体的子图"""
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
        """将 Neo4j 节点转为字典"""
        return {
            "id": node.id,
            "labels": list(node.labels),
            "properties": dict(node),
        }
    
    def _rel_to_dict(self, rel) -> dict:
        """将 Neo4j 关系转为字典"""
        return {
            "id": rel.id,
            "type": rel.type,
            "start_node_id": rel.start_node.id,
            "end_node_id": rel.end_node.id,
            "properties": dict(rel),
        }
```

---

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  graph_db:
    provider: neo4j
    implementations:
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

---

## 相关文档

- **[protocol.md](./protocol.md)** — GraphDatabase Protocol 定义
- **[../../design/solution-final/030-rag/](../../design/solution-final/030-rag/)** — 知识图谱 RAG 路径
