# Cypher 查询语言

**Cypher** 是 Neo4j 的声明式图查询语言，语法借鉴了 SQL 的可读性，用 ASCII 艺术风格直观表达图模式（Pattern）：节点用 `()` 表示，关系用 `-->` 或 `-[]->`表示。

## 基本语法结构

```cypher
MATCH (n:Entity {name: "match3"})
-[:RELATED_TO]->(m:Entity)
RETURN n.name, m.name, m.type
LIMIT 10
```

主要子句：

| 子句 | 用途 |
|------|------|
| `MATCH` | 在图中查找满足模式的路径 |
| `WHERE` | 过滤条件 |
| `RETURN` | 指定返回字段 |
| `CREATE` | 创建节点或关系 |
| `MERGE` | 存在则匹配，不存在则创建（见 [MERGE 模式](./MERGE.md)） |
| `SET` | 更新属性 |
| `DELETE` / `DETACH DELETE` | 删除节点或关系 |
| `WITH` | 管道：将上一步的结果传入下一步 |

## 路径模式

```cypher
// simple relationship
(a)-[:KNOWS]->(b)

// variable-length path (1 to 3 hops)
(a)-[:RELATED_TO*1..3]->(b)

// named relationship
(a)-[r:WORKS_FOR]->(b)
WHERE r.since > 2020
```

## 在本项目中的使用

实体抽取后用 Cypher 写入知识图谱：

```python
query = """
MERGE (e1:Entity {name: $name1, type: $type1})
MERGE (e2:Entity {name: $name2, type: $type2})
MERGE (e1)-[r:RELATION {type: $rel_type}]->(e2)
ON CREATE SET r.source_chunk_id = $chunk_id
"""
session.run(query, name1=..., type1=..., name2=..., type2=..., rel_type=..., chunk_id=...)
```

查询时使用 `execute_read`（只读事务）和 `execute_write`（写事务），由 Neo4j Python 驱动自动处理重试。
