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
// 唯一性约束（同时自动创建索引）
CREATE CONSTRAINT entity_id_workspace IF NOT EXISTS
  FOR (e:Entity) REQUIRE (e.id, e.workspace_id) IS UNIQUE;

CREATE CONSTRAINT chunk_id IF NOT EXISTS
  FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

// 额外索引，用于常见查询模式
CREATE INDEX entity_name_workspace IF NOT EXISTS
  FOR (e:Entity) ON (e.name, e.workspace_id);

CREATE INDEX entity_type IF NOT EXISTS
  FOR (e:Entity) ON (e.type);
```

---

## Python 中的图 Schema

```python
# app/storage/graph_store.py
from __future__ import annotations
from typing import Any, Optional
from neo4j import GraphDatabase, Driver, Session as Neo4jSession


class GraphStore:
    """
    GraphRAG 实体/关系操作的 Neo4j 封装类。

    所有写操作均按工作区范围隔离。查询在每个 MATCH 子句中过滤 workspace_id，
    确保多租户数据不会跨工作区泄漏。
    """

    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    # ------------------------------------------------------------------
    # 实体写入
    # ------------------------------------------------------------------

    def upsert_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        workspace_id: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        按 (id, workspace_id) MERGE 实体。
        CREATE 时设置所有属性；MATCH 时更新 name 和 type。
        """
        extra = properties or {}
        with self._driver.session() as session:
            session.run(
                """
                MERGE (e:Entity {id: $id, workspace_id: $workspace_id})
                ON CREATE SET
                    e.name = $name,
                    e.type = $type,
                    e += $extra
                ON MATCH SET
                    e.name = $name,
                    e.type = $type
                """,
                id=entity_id,
                workspace_id=workspace_id,
                name=name,
                type=entity_type,
                extra=extra,
            )

    def upsert_entities_batch(
        self,
        rows: list[dict[str, Any]],
        workspace_id: str,
    ) -> None:
        """
        使用 UNWIND 批量写入实体以提升性能。

        每行格式：{id, name, type, **extra_props}
        """
        with self._driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (e:Entity {id: row.id, workspace_id: $workspace_id})
                ON CREATE SET e += row, e.workspace_id = $workspace_id
                ON MATCH SET e.name = row.name, e.type = row.type
                """,
                rows=rows,
                workspace_id=workspace_id,
            )

    # ------------------------------------------------------------------
    # 文本块节点
    # ------------------------------------------------------------------

    def upsert_chunk_node(
        self,
        chunk_id: str,
        workspace_id: str,
        raw_file_id: str,
    ) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (c:Chunk {id: $id})
                ON CREATE SET c.workspace_id = $workspace_id,
                              c.raw_file_id = $raw_file_id
                """,
                id=chunk_id,
                workspace_id=workspace_id,
                raw_file_id=raw_file_id,
            )

    # ------------------------------------------------------------------
    # 关系
    # ------------------------------------------------------------------

    def upsert_mentions(
        self,
        chunk_id: str,
        entity_id: str,
        workspace_id: str,
        score: float = 1.0,
    ) -> None:
        """建立文本块与其提及的实体之间的连接。"""
        with self._driver.session() as session:
            session.run(
                """
                MATCH (c:Chunk {id: $chunk_id})
                MATCH (e:Entity {id: $entity_id, workspace_id: $workspace_id})
                MERGE (c)-[r:MENTIONS]->(e)
                ON CREATE SET r.score = $score
                ON MATCH SET  r.score = $score
                """,
                chunk_id=chunk_id,
                entity_id=entity_id,
                workspace_id=workspace_id,
                score=score,
            )

    def upsert_relation(
        self,
        from_entity_id: str,
        to_entity_id: str,
        workspace_id: str,
        relation: str,
        weight: float = 1.0,
    ) -> None:
        """在两个实体之间写入 RELATED_TO 边。"""
        with self._driver.session() as session:
            session.run(
                """
                MATCH (a:Entity {id: $from_id, workspace_id: $workspace_id})
                MATCH (b:Entity {id: $to_id,   workspace_id: $workspace_id})
                MERGE (a)-[r:RELATED_TO {relation: $relation}]->(b)
                ON CREATE SET r.weight = $weight
                ON MATCH SET  r.weight = r.weight + $weight
                """,
                from_id=from_entity_id,
                to_id=to_entity_id,
                workspace_id=workspace_id,
                relation=relation,
                weight=weight,
            )

    def upsert_relations_batch(
        self,
        rows: list[dict[str, Any]],
        workspace_id: str,
    ) -> None:
        """
        批量写入关系。

        每行格式：{from_id, to_id, relation, weight}
        """
        with self._driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (a:Entity {id: row.from_id, workspace_id: $workspace_id})
                MATCH (b:Entity {id: row.to_id,   workspace_id: $workspace_id})
                MERGE (a)-[r:RELATED_TO {relation: row.relation}]->(b)
                ON CREATE SET r.weight = row.weight
                ON MATCH SET  r.weight = r.weight + row.weight
                """,
                rows=rows,
                workspace_id=workspace_id,
            )

    # ------------------------------------------------------------------
    # 查询：实体邻域
    # ------------------------------------------------------------------

    def find_entity_by_name(
        self,
        name: str,
        workspace_id: str,
        entity_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        按名称查找实体（不区分大小写的子串匹配）。
        作为 GraphRAG 的第一步，将查询锚定到图节点。
        """
        type_clause = "AND e.type = $type" if entity_type else ""
        with self._driver.session() as session:
            result = session.run(
                f"""
                MATCH (e:Entity)
                WHERE e.workspace_id = $workspace_id
                  AND toLower(e.name) CONTAINS toLower($name)
                  {type_clause}
                RETURN e.id AS id, e.name AS name, e.type AS type
                LIMIT 10
                """,
                workspace_id=workspace_id,
                name=name,
                type=entity_type or "",
            )
            return [dict(record) for record in result]

    def get_entity_neighbourhood(
        self,
        entity_ids: list[str],
        workspace_id: str,
        hops: int = 2,
    ) -> dict[str, Any]:
        """
        返回从种子实体出发，在 `hops` 跳范围内可达的所有节点和边。

        返回格式：
            {
              "nodes": [{"id": ..., "name": ..., "type": ...}, ...],
              "edges": [{"from": ..., "to": ..., "relation": ..., "weight": ...}, ...],
            }

        该子图在 GraphRAG 中作为结构化上下文传递给 LLM。
        """
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH path = (seed:Entity)-[*1..$hops]-(neighbor:Entity)
                WHERE seed.id IN $entity_ids
                  AND seed.workspace_id = $workspace_id
                  AND neighbor.workspace_id = $workspace_id
                WITH nodes(path) AS ns, relationships(path) AS rels
                UNWIND ns AS n
                WITH COLLECT(DISTINCT {id: n.id, name: n.name, type: n.type}) AS nodes,
                     rels
                UNWIND rels AS r
                RETURN nodes,
                       COLLECT(DISTINCT {
                         from: startNode(r).id,
                         to:   endNode(r).id,
                         relation: r.relation,
                         weight: r.weight
                       }) AS edges
                """,
                entity_ids=entity_ids,
                workspace_id=workspace_id,
                hops=hops,
            )
            record = result.single()
            if not record:
                return {"nodes": [], "edges": []}
            return {"nodes": record["nodes"], "edges": record["edges"]}

    def get_chunks_for_entities(
        self,
        entity_ids: list[str],
        workspace_id: str,
        top_k: int = 20,
    ) -> list[str]:
        """
        返回提及了给定实体中任意一个的文本块 ID。
        在邻域扩展后用于获取源文本。
        """
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (c:Chunk)-[r:MENTIONS]->(e:Entity)
                WHERE e.id IN $entity_ids
                  AND e.workspace_id = $workspace_id
                  AND c.workspace_id = $workspace_id
                RETURN c.id AS chunk_id, SUM(r.score) AS relevance
                ORDER BY relevance DESC
                LIMIT $top_k
                """,
                entity_ids=entity_ids,
                workspace_id=workspace_id,
                top_k=top_k,
            )
            return [record["chunk_id"] for record in result]

    # ------------------------------------------------------------------
    # 删除（文件移除时）
    # ------------------------------------------------------------------

    def delete_chunk_and_mentions(
        self,
        chunk_id: str,
        workspace_id: str,
    ) -> None:
        """删除一个 Chunk 节点及其所有 MENTIONS 边。"""
        with self._driver.session() as session:
            session.run(
                """
                MATCH (c:Chunk {id: $chunk_id, workspace_id: $workspace_id})
                DETACH DELETE c
                """,
                chunk_id=chunk_id,
                workspace_id=workspace_id,
            )

    def delete_by_raw_file_id(self, raw_file_id: str, workspace_id: str) -> None:
        """删除某个文件的所有 Chunk 节点（及其 MENTIONS 关系）。"""
        with self._driver.session() as session:
            session.run(
                """
                MATCH (c:Chunk {raw_file_id: $raw_file_id, workspace_id: $workspace_id})
                DETACH DELETE c
                """,
                raw_file_id=raw_file_id,
                workspace_id=workspace_id,
            )
```

---

## GraphRAG 提取（导入侧）

在 `graph` Celery 任务中（在 `embed` 完成后运行）：

```python
# app/workers/tasks/graph_task.py  (relevant excerpt)

_EXTRACT_PROMPT = """\
Extract named entities and relationships from the text below.
Return JSON with two keys:
- "entities": list of {{"id": "<slug>", "name": "<name>", "type": "<type>"}}
- "relations": list of {{"from": "<slug>", "to": "<slug>", "relation": "<label>", "weight": 1.0}}

Entity types: GAME, COMPANY, FEATURE, MECHANIC, MARKET, METRIC, PERSON
Relationship labels: MADE_BY, HAS_FEATURE, COMPETES_WITH, BELONGS_TO, RELATED_TO

Text:
{text}
"""


def _extract_graph(rt: Match3Runtime, chunk_id: str, text: str, workspace_id: str) -> None:
    prompt = _EXTRACT_PROMPT.format(text=text[:3000])
    try:
        content = rt.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            model=rt.config.llm.default_model,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("failed to extract graph").ctx(chunk_id=chunk_id).as_ex(e)

    import json
    try:
        data = json.loads(content)
    except Exception as e:
        raise Match3Exception.of("failed to parse graph extraction json").ctx(chunk_id=chunk_id).as_ex(e)

    graph = GraphStore(rt.neo4j)
    entities = data.get("entities", [])
    relations = data.get("relations", [])

    # 为实体 ID 加上工作区前缀，确保租户隔离
    for ent in entities:
        ent["id"] = f"{workspace_id}:{ent['id']}"

    graph.upsert_chunk_node(chunk_id, workspace_id, raw_file_id="")
    graph.upsert_entities_batch(entities, workspace_id)

    for rel in relations:
        graph.upsert_mentions(
            chunk_id=chunk_id,
            entity_id=f"{workspace_id}:{rel['from']}",
            workspace_id=workspace_id,
        )

    rel_rows = [
        {
            "from_id": f"{workspace_id}:{r['from']}",
            "to_id":   f"{workspace_id}:{r['to']}",
            "relation": r["relation"],
            "weight":   float(r.get("weight", 1.0)),
        }
        for r in relations
    ]
    graph.upsert_relations_batch(rel_rows, workspace_id)
```

---

## GraphRAG 查询（RAG 侧）

```python
# app/services/rag/method_graph.py  (excerpt — full version in 030-rag/path-chunk.md)

def graph_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 10,
) -> Generator[str, None, None]:
    """
    GraphRAG：将查询锚定到实体图，扩展邻域，
    获取源文本块，然后生成答案。
    """
    graph = GraphStore(rt.neo4j)
    chunk_repo = TextChunkRepository(rt.db_engine)

    # 1. 提取查询中的实体（快速，尚不调用图数据库）
    query_entities = _extract_query_entities(rt, query)

    # 2. 在图中找到锚点实体
    anchor_ids: list[str] = []
    for name in query_entities:
        hits = graph.find_entity_by_name(name, workspace_id)
        anchor_ids.extend(h["id"] for h in hits)

    if not anchor_ids:
        # 若图中未找到锚点，回退到稠密向量搜索
        yield from _fallback_dense(rt, query, workspace_id, top_k)
        return

    # 3. 扩展邻域（2 跳）
    subgraph = graph.get_entity_neighbourhood(anchor_ids, workspace_id, hops=2)

    # 4. 检索提及了邻域实体的文本块
    all_entity_ids = [n["id"] for n in subgraph["nodes"]]
    chunk_ids = graph.get_chunks_for_entities(all_entity_ids, workspace_id, top_k=top_k * 2)
    chunks = chunk_repo.find_by_ids(chunk_ids[:top_k])

    # 5. 构建上下文：子图摘要 + 文本块内容
    graph_ctx = _format_subgraph(subgraph)
    chunk_ctx  = "\n\n".join(f"[Chunk {i+1}]\n{c.content}" for i, c in enumerate(chunks))

    prompt = _GRAPH_RAG_PROMPT.format(
        graph_context=graph_ctx,
        chunk_context=chunk_ctx,
        query=query,
    )
    yield from _stream_llm(rt, prompt)
```

---

## 环境变量

| 变量 | 示例 | 描述 |
|------|------|------|
| `NEO4J_URI` | `bolt://localhost:7687` | Bolt 端点 |
| `NEO4J_USER` | `neo4j` | 用户名 |
| `NEO4J_PASSWORD` | `password` | 密码 |

在 `Match3Runtime` 中的驱动构建：

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    env.NEO4J_URI,
    auth=(env.NEO4J_USER, env.NEO4J_PASSWORD),
)
```
