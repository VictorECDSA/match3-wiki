# Graph Task

## 职责

`extract_graph` 是导入流水线的**第三阶段（最后阶段）**，由 `embed_chunks` 通过 `chain` 自动触发。它从 PostgreSQL 读取文本块，逐块调用 LLM 提取命名实体和关系，将结果通过 `MERGE` 写入 Neo4j。

本任务完成后，该文件的全部数据（PostgreSQL + Milvus + ES + Neo4j）均已就绪，可参与 RAG 检索。

---

## 队列与并发

| 属性 | 值 |
|------|----|
| 队列名 | `constants.QUEUE_GRAPH` (`"graph"`) |
| 推荐并发 | 2 |
| max_retries | 2 |
| 重试间隔 | 15 s |
| 硬超时 | 无 |

并发设为 2：每个 chunk 需要一次同步 LLM 调用，过高并发会超出 API 速率限制。

---

## 执行步骤

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 过滤 chunks | 仅处理 `chunk_type == "text"` 且 `len(content) >= 50` 的块 |
| 2 | LLM 提取 | 逐块调用 LLM（`temperature=0, response_format=json_object`），返回 `entities` + `relations` |
| 3 | 前缀实体 ID | `entity["id"] = f"{workspace_id}:{slug}"` — 工作区隔离 |
| 4 | 写入实体节点 | `graph.upsert_entities_batch(entities, workspace_id)` |
| 5 | 写入 Chunk 节点 | `graph.upsert_chunk_node(chunk.id, workspace_id, raw_file_id)` |
| 6 | 写入 MENTIONS | 每个 entity 写一条 `chunk → entity` 边 |
| 7 | 写入实体关系 | `graph.upsert_relations_batch(rel_rows, workspace_id)` |
| 8 | 状态推进 `DONE` | 所有 chunk 处理完成后更新 `t_raw_files.f_status` |

---

## 状态机流转

```
PROCESSING  (written by embed_task)
  │  extract_graph starts
  │  all chunk graph writes succeed
  ▼
DONE  ← file fully available
  │
  │  any exception (including max_retries exceeded)
  ▼
FAILED
```

---

## 实体提取 Prompt

```
Extract named entities and relationships from the text below.
Return JSON with two keys:
- "entities": list of {"id": "<slug>", "name": "<name>", "type": "<type>"}
- "relations": list of {"from": "<slug>", "to": "<slug>", "relation": "<label>", "weight": 1.0}

Entity types: GAME, COMPANY, FEATURE, MECHANIC, MARKET, METRIC, PERSON
Relationship labels: MADE_BY, HAS_FEATURE, COMPETES_WITH, BELONGS_TO, RELATED_TO

Text:
{text}
```

---

## 幂等性

Neo4j 所有写入均使用 `MERGE`：节点和关系已存在时跳过创建，仅更新属性。重试时不会产生重复节点或悬空关系。

---

## 核心实现

**文件**：`app/workers/tasks/graph_task.py`

```python
@celery_app.task(name="…extract_graph", bind=True, max_retries=2, default_retry_delay=15)
def extract_graph(self, raw_file_id: str) -> str:

    text_chunks = [c for c in chunk_repo.find_by_raw_file_id(raw_file_id)
                   if c.chunk_type == CHUNK_TYPE_TEXT and len(c.content) >= 50]

    try:
        from app.intelligence.llm import OpenAILLMCaller
        llm = OpenAILLMCaller(api_key=rt.env.OPENAI_API_KEY, model=rt.config.llm.default_model)

        for chunk in text_chunks:
            data = json.loads(llm.complete(
                messages=[{"role": "user", "content": EXTRACT_PROMPT.format(text=chunk.content[:3000])}],
                temperature=0, response_format={"type": "json_object"},
            ))

            ws = chunk.workspace_id
            entities = [{**e, "id": f"{ws}:{e['id']}"} for e in data.get("entities", [])]

            graph.upsert_entities_batch(entities, ws)
            graph.upsert_chunk_node(chunk.id, ws, raw_file_id)
            for ent in entities:
                graph.upsert_mentions(chunk.id, ent["id"], ws)
            graph.upsert_relations_batch([
                {"from_id": f"{ws}:{r['from']}", "to_id": f"{ws}:{r['to']}",
                 "relation": r.get("relation", "RELATED_TO"), "weight": float(r.get("weight", 1.0))}
                for r in data.get("relations", [])
            ], ws)

        raw_file.status = DONE
        raw_file_repo.update(raw_file)

    except Exception as exc:
        raw_file.status = FAILED; raw_file.error = str(exc)
        raw_file_repo.update(raw_file)
        raise self.retry(exc=exc)

    return raw_file_id
```
