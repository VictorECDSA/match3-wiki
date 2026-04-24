# GraphDatabase Protocol

> **功能**: GraphRAG 知识图谱查询  
> **推荐实现**: Neo4j v2026.03.1 (2026-04-02)  
> **Runtime 接口**: `rt.graph_db: GraphDatabase` (Protocol)

## 📚 相关文档

- **上级文档**: [runtime.md](../runtime.md) - Runtime 系统总览和 Protocol 设计理念
- **实现方案**: [implementation.md](./implementation.md) - Neo4j 适配器实现和配置说明
- **版本技术文档**: [versions/](./versions/) - 具体实现库的详细 API 文档
  - [Neo4j v2026.03.1](./versions/neo4j-v2026.03.1.md) - 推荐实现

---

## Protocol 定义

### 接口说明

`GraphDatabase` 提供图查询能力,用于:
- **GraphRAG**: 知识图谱增强检索
- **关系查询**: 实体间关系的复杂查询
- **图算法**: PageRank、社区发现等图算法 (需扩展 Protocol)

### 主接口定义

```python
from typing import Protocol, ContextManager

class GraphDatabase(Protocol):
    """图数据库抽象接口 (不依赖任何图数据库驱动)"""
    
    def session(self, database: str | None = None) -> ContextManager[GraphSession]:
        """创建会话的上下文管理器
        
        Args:
            database: 数据库名称 (可选,默认使用默认数据库)
            
        Returns:
            会话上下文管理器
        """
        ...
    
    def close(self) -> None:
        """关闭驱动连接池"""
        ...
```

### 会话 Protocol

```python
from typing import Protocol, Any

class GraphSession(Protocol):
    """图数据库会话接口"""
    
    def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[GraphQueryResult]:
        """在自动提交模式下执行查询"""
        ...
    
    def begin_transaction(self) -> GraphTransaction:
        """开始显式事务"""
        ...
    
    def close(self) -> None:
        """关闭会话"""
        ...
```

### 事务 Protocol

```python
from typing import Protocol, Any

class GraphTransaction(Protocol):
    """图数据库事务接口"""
    
    def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[GraphQueryResult]:
        """执行 Cypher 查询
        
        Args:
            query: Cypher 查询语句
            parameters: 查询参数 (可选)
            
        Returns:
            查询结果列表
        """
        ...
    
    def commit(self) -> None:
        """提交事务"""
        ...
    
    def rollback(self) -> None:
        """回滚事务"""
        ...
```

### 查询结果 Protocol

```python
from typing import Protocol, Any

class GraphQueryResult(Protocol):
    """图查询结果 (单条记录)"""
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取字段值"""
        ...
    
    def data(self) -> dict[str, Any]:
        """获取所有字段的字典"""
        ...
```

---

## 使用示例

### 业务代码 (自动提交)

```python
from runtime import Runtime

def find_related_entities(
    rt: Runtime,
    entity_name: str,
    relationship_type: str,
) -> list[str]:
    """查找相关实体 (不知道底层是 Neo4j 还是其他图数据库)"""
    
    with rt.graph_db.session() as session:
        query = """
        MATCH (e:Entity {name: $name})-[r:RELATES_TO]->(related:Entity)
        WHERE type(r) = $rel_type
        RETURN related.name AS name
        """
        
        results = session.run(
            query,
            parameters={"name": entity_name, "rel_type": relationship_type},
        )
        
        return [r.get("name") for r in results]
```

### 业务代码 (显式事务)

```python
def create_knowledge_graph(
    rt: Runtime,
    entities: list[dict],
    relationships: list[dict],
) -> None:
    """创建知识图谱 (事务中批量创建)"""
    
    with rt.graph_db.session() as session:
        tx = session.begin_transaction()
        
        try:
            # 创建实体
            for entity in entities:
                tx.run(
                    """
                    MERGE (e:Entity {name: $name})
                    SET e.type = $type, e.properties = $props
                    """,
                    parameters=entity,
                )
            
            # 创建关系
            for rel in relationships:
                tx.run(
                    """
                    MATCH (a:Entity {name: $from})
                    MATCH (b:Entity {name: $to})
                    MERGE (a)-[r:RELATES_TO {type: $type}]->(b)
                    """,
                    parameters=rel,
                )
            
            tx.commit()
        except Exception:
            tx.rollback()
            raise
```

### 单元测试

```python
from unittest.mock import MagicMock, Mock
from runtime import Runtime

def test_find_related_entities():
    # Mock 图数据库
    mock_result = Mock()
    mock_result.get.return_value = "Related Entity"
    
    mock_session = MagicMock()
    mock_session.run.return_value = [mock_result]
    
    mock_graph_db = MagicMock()
    mock_graph_db.session.return_value.__enter__.return_value = mock_session
    
    # 创建测试 Runtime
    rt = Runtime(
        cache=MagicMock(),
        queue=MagicMock(),
        vector_db=MagicMock(),
        graph_db=mock_graph_db,
        db=MagicMock(),
        search=MagicMock(),
        storage=MagicMock(),
    )
    
    # 测试
    results = find_related_entities(rt, "Entity A", "KNOWS")
    
    assert results == ["Related Entity"]
    mock_session.run.assert_called_once()
```

---

## 设计说明

### 查询语言的抽象

不同图数据库使用不同的查询语言:
- Neo4j: Cypher
- ArangoDB: AQL
- JanusGraph: Gremlin

**两种方案**:

#### 方案 1: 统一使用 Cypher (推荐)
```python
class GraphDatabase(Protocol):
    def run(self, cypher_query: str, ...) -> ...
```

适配器负责将 Cypher 转换为目标数据库的查询语言 (如果可能)。

#### 方案 2: 抽象为通用图操作
```python
class GraphDatabase(Protocol):
    def find_neighbors(self, node_id: str, ...) -> ...
    def shortest_path(self, start: str, end: str, ...) -> ...
```

但这会限制复杂查询的灵活性。

**推荐方案 1**: 大多数图数据库都支持 Cypher 或有转换工具。

### 事务模型

某些图数据库的事务模型不同:
- Neo4j: 显式事务 + 自动提交
- ArangoDB: 支持事务,但语法不同

适配器应该统一事务接口。

### 返回值类型

使用 Protocol 定义返回值:

```python
class GraphQueryResult(Protocol):
    def get(self, key: str) -> Any: ...
    def data(self) -> dict: ...
```

避免直接返回 `neo4j.Record`。

---

## 扩展性

### 切换到 ArangoDB

```python
from arango import ArangoClient

class ArangoDBAdapter:
    """ArangoDB 适配器 (实现 GraphDatabase Protocol)"""
    
    def __init__(self, client: ArangoClient, db_name: str):
        self._client = client
        self._db = client.db(db_name)
    
    @contextmanager
    def session(self, database: str | None = None) -> ContextManager[GraphSession]:
        # ArangoDB 使用不同的会话模型
        session = ArangoDBSession(self._db)
        try:
            yield session
        finally:
            pass  # ArangoDB 不需要显式关闭会话
    
    def close(self) -> None:
        self._client.close()
```

**无需修改 Runtime 或业务代码！**

### 支持图算法

如果需要支持图算法 (PageRank、社区发现等):

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class GraphAlgorithms(Protocol):
    """图算法接口 (可选)"""
    
    def page_rank(
        self,
        node_label: str,
        relationship_type: str,
        damping_factor: float = 0.85,
    ) -> dict[str, float]:
        """计算 PageRank"""
        ...
    
    def community_detection(
        self,
        node_label: str,
        relationship_type: str,
        algorithm: str = "louvain",
    ) -> dict[str, int]:
        """社区发现"""
        ...
```

使用 `@runtime_checkable` 检查是否支持:

```python
if isinstance(rt.graph_db, GraphAlgorithms):
    pagerank = rt.graph_db.page_rank("Entity", "RELATES_TO")
```

---

**创建时间**: 2026-04-23  
**最后更新**: 2026-04-23  
**版本**: 2.0
