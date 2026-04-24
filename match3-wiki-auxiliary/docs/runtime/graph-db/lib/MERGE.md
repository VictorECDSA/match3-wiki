# MERGE 模式（图上的 Upsert）

**MERGE** 是 Cypher 中的核心写操作，语义为"若图中已存在匹配该模式的节点或关系则直接返回，否则创建"——即图数据库的 Upsert（Update or Insert）。

## 与 CREATE 的区别

```cypher
// CREATE: always creates a new node, may cause duplicates
CREATE (e:Entity {name: "match3"})

// MERGE: idempotent, safe to call repeatedly
MERGE (e:Entity {name: "match3"})
```

对同一实体多次调用 `MERGE` 只产生一个节点，而 `CREATE` 会产生多个重复节点。在知识图谱写入中，MERGE 是防止重复节点的标准手段。

## ON CREATE / ON MATCH 子句

```cypher
MERGE (e:Entity {name: $name})
ON CREATE SET e.created_at = timestamp(), e.type = $type
ON MATCH  SET e.updated_at = timestamp()
```

- `ON CREATE SET`：仅在新建时执行的属性设置
- `ON MATCH SET`：仅在匹配到已有节点时执行的属性更新

## 关系的 MERGE

MERGE 作用于关系时，需要同时指定两端节点：

```cypher
MERGE (a:Entity {name: $name1})
MERGE (b:Entity {name: $name2})
MERGE (a)-[r:RELATION {type: $rel_type}]->(b)
ON CREATE SET r.source_chunk_id = $chunk_id
```

先 MERGE 两端节点（确保存在），再 MERGE 关系（确保不重复建边）。这是本项目知识图谱抽取写入的标准模式。

## 注意事项

MERGE 的匹配依赖**主键约束（Constraint）**提升性能。若 `name` 字段无唯一约束，MERGE 需要全图扫描，数据量大时会很慢：

```cypher
// Create constraint to speed up MERGE lookup
CREATE CONSTRAINT entity_name_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.name IS UNIQUE
```
