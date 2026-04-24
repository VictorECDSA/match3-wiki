# Neo4j 图存储

仅由 **GraphRAG** 路径使用。所有其他 RAG 路径均不访问 Neo4j。

---

## 节点类型

| 标签 | 核心属性 | 描述 |
|------|---------|------|
| `Entity` | `id`, `name`, `type`, `workspace_id` | 从文本块中提取的命名实体 |
| `Chunk` | `id`, `workspace_id`, `raw_file_id` | PostgreSQL `t_text_chunks.f_id` 的镜像（不存储内容） |

---

## 关系类型

| 类型 | 起点 → 终点 | 属性 | 描述 |
|------|-----------|------|------|
| `MENTIONS` | `Chunk → Entity` | `score: float` | 文本块提及了该实体 |
| `RELATED_TO` | `Entity → Entity` | `weight: float`, `relation: str` | 实体共现或语义相关 |
| `BELONGS_TO` | `Entity → Entity` | — | 子实体层级关系（例如特性 → 游戏） |

---

## Cypher DDL（约束与索引）

在初始化时运行一次：

```cypher
CREATE CONSTRAINT entity_id_workspace IF NOT EXISTS
  FOR (e:Entity) REQUIRE (e.id, e.workspace_id) IS UNIQUE;

CREATE CONSTRAINT chunk_id IF NOT EXISTS
  FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

CREATE INDEX entity_name_workspace IF NOT EXISTS
  FOR (e:Entity) ON (e.name, e.workspace_id);

CREATE INDEX entity_type IF NOT EXISTS
  FOR (e:Entity) ON (e.type);
```

---

## GraphStore API

实现于 `app/storage/graph_store.py`。所有写操作按 `workspace_id` 隔离；查询在每个 `MATCH` 子句中过滤 `workspace_id`。

### 写操作

| 方法 | Cypher 操作 | 说明 |
|------|------------|------|
| `upsert_entity(entity_id, name, type, workspace_id, props?)` | `MERGE (e:Entity {id, workspace_id}) ON CREATE SET … ON MATCH SET name, type` | 单个实体 upsert |
| `upsert_entities_batch(rows, workspace_id)` | `UNWIND $rows … MERGE … ON CREATE SET e += row` | 批量实体，`UNWIND` 单次 Cypher |
| `upsert_chunk_node(chunk_id, workspace_id, raw_file_id)` | `MERGE (c:Chunk {id}) ON CREATE SET workspace_id, raw_file_id` | 为 chunk 在图中占位（不存内容） |
| `upsert_mentions(chunk_id, entity_id, workspace_id, score=1.0)` | `MATCH c, e … MERGE (c)-[r:MENTIONS]->(e) … SET r.score` | 文本块 → 实体边 |
| `upsert_relation(from_id, to_id, workspace_id, relation, weight=1.0)` | `MATCH a, b … MERGE (a)-[r:RELATED_TO {relation}]->(b) … r.weight += weight` | 实体间关系；权重累加 |
| `upsert_relations_batch(rows, workspace_id)` | `UNWIND $rows … MERGE … ON MATCH SET r.weight += row.weight` | 批量关系，`UNWIND` 单次 Cypher |

### 查询

| 方法 | 返回 | 说明 |
|------|------|------|
| `find_entity_by_name(name, workspace_id, type?)` | `list[{id, name, type}]` | 不区分大小写子串匹配，`LIMIT 10` |
| `get_entity_neighbourhood(entity_ids, workspace_id, hops=2)` | `{nodes: […], edges: […]}` | `MATCH path = (seed)-[*1..hops]-(neighbor)` APOC 路径展开 |
| `get_chunks_for_entities(entity_ids, workspace_id, top_k=20)` | `list[chunk_id]` | `MATCH (c)-[:MENTIONS]->(e) … ORDER BY SUM(r.score) DESC` |

### 删除

| 方法 | Cypher 操作 |
|------|------------|
| `delete_chunk_and_mentions(chunk_id, workspace_id)` | `MATCH (c:Chunk {id, workspace_id}) DETACH DELETE c` |
| `delete_by_raw_file_id(raw_file_id, workspace_id)` | `MATCH (c:Chunk {raw_file_id, workspace_id}) DETACH DELETE c` |

---

## GraphRAG 提取（导入侧）

在 `graph` Celery 任务中运行（`embed` 完成后触发）：

**LLM 提示词**：

```
Extract named entities and relationships from the text below.
Return JSON with two keys:
- "entities": list of {"id": "<slug>", "name": "<name>", "type": "<type>"}
- "relations": list of {"from": "<slug>", "to": "<slug>", "relation": "<label>", "weight": 1.0}

Entity types: GAME, COMPANY, FEATURE, MECHANIC, MARKET, METRIC, PERSON
Relationship labels: MADE_BY, HAS_FEATURE, COMPETES_WITH, BELONGS_TO, RELATED_TO

Text: {text[:3000]}
```

**写入流程**（`app/workers/tasks/graph_task.py`）：

```python
data = json.loads(llm.complete(prompt, response_format="json_object"))

# Prefix entity IDs with workspace_id for tenant isolation
for e in data["entities"]:
    e["id"] = f"{workspace_id}:{e['id']}"

graph.upsert_chunk_node(chunk_id, workspace_id, raw_file_id)
graph.upsert_entities_batch(data["entities"], workspace_id)

# Wire chunk → entity MENTIONS edges (one per relation "from")
for rel in data["relations"]:
    graph.upsert_mentions(chunk_id, f"{workspace_id}:{rel['from']}", workspace_id)

# Wire entity → entity RELATED_TO edges
graph.upsert_relations_batch([
    {"from_id": f"{workspace_id}:{r['from']}",
     "to_id":   f"{workspace_id}:{r['to']}",
     "relation": r["relation"],
     "weight":   float(r.get("weight", 1.0))}
    for r in data["relations"]
], workspace_id)
```

---

## GraphRAG 查询（RAG 侧）

详见 `030-rag/processing/chunking.md`（图谱建索引）和 `030-rag/retrieval/hybrid-search.md`（Graph 通道检索）。流程概要：

```
entities   = llm.extract_entities(query)           # → list[str]
anchors    = graph.find_entity_by_name(e, ws)      # fuzzy match per entity
subgraph   = graph.get_entity_neighbourhood(anchors, ws, hops=2)
chunk_ids  = graph.get_chunks_for_entities(subgraph.nodes, ws)
chunks     = pg.find_by_ids(chunk_ids[:top_k])
→ feed subgraph text + chunk content to LLM
```

若图中找不到锚点实体，回退到密集向量搜索。

---

## 环境变量

| 变量 | 示例 | 描述 |
|------|------|------|
| `NEO4J_URI` | `bolt://localhost:7687` | Bolt 端点 |
| `NEO4J_USER` | `neo4j` | 用户名 |
| `NEO4J_PASSWORD` | `password` | 密码 |

驱动构建：`GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))`
