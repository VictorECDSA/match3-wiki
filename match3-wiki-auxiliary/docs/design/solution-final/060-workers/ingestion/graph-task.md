# Graph Task

## 职责

`extract_graph` 是导入流水线的**第三阶段（最后阶段）**，由 `embed_chunks` 通过 `chain` 自动触发。它从 PostgreSQL 读取文本块，逐块调用 LLM 提取命名实体和关系，将结果通过 `MERGE` 写入 Neo4j，最终将 `t_raw_files.f_status` 推进到 `DONE`。

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

并发设为 2 而非更高，因为每个 chunk 都需要一次同步 LLM 调用，过高并发会超出 API 速率限制。

---

## 执行步骤

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 加载 chunks | 查询该 `raw_file_id` 下所有 `chunk_type == "text"` 且 `len(content) >= 50` 的块 |
| 2 | LLM 实体提取 | 对每个 chunk 发送结构化提取 prompt，要求返回 JSON（`entities` + `relations`） |
| 3 | 解析 JSON | `json.loads(content)` 提取 entities 和 relations |
| 4 | 写入实体节点 | `graph.upsert_entities_batch(entities, workspace_id)`，Neo4j `MERGE` 语义 |
| 5 | 写入 Chunk 节点 | `graph.upsert_chunk_node(chunk_id, workspace_id, raw_file_id)` |
| 6 | 写入 MENTIONS 关系 | 记录 chunk 提及了哪些实体，支持图谱 RAG 中的"从实体反查原始依据" |
| 7 | 写入实体间关系 | `graph.upsert_relations_batch(rel_rows, workspace_id)` |
| 8 | 状态推进 `DONE` | 所有 chunk 处理完成后更新 `t_raw_files.f_status` |

---

## 状态机流转

```
PROCESSING  (由 embed_task 写入)
  │  extract_graph 开始执行
  │  所有 chunk 图谱写入成功
  ▼
DONE  ← 文件完全可用
  │
  │  任何异常（含超过 max_retries）
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

LLM 调用使用 `response_format={"type": "json_object"}` 和 `temperature=0` 保证输出可解析。

---

## 幂等性

Neo4j 所有写入均使用 `MERGE`：节点和关系已存在时跳过创建，仅更新属性。重试时不会产生重复节点或悬空关系。

---

## 工作区隔离

实体 ID 前缀为 `{workspace_id}:`（例如 `ws_abc123:royal-match`），确保不同工作区的同名实体不会合并。

---

## 源码

```python
# app/workers/tasks/graph_task.py
from __future__ import annotations
import json
from app.workers.celery_app import celery_app
from app.workers.worker_runtime import get_runtime
from app.common.exceptions import Match3Exception
from app.storage.repositories.raw_file_repo import RawFileRepository
from app.storage.repositories.text_chunk_repo import TextChunkRepository
from app.storage.graph_store import GraphStore
from app.storage.entities.raw_file import RawFileStatus
from app.common.constants import constants
import app.common.constants.codes as codes


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


@celery_app.task(
    name="app.workers.tasks.graph_task.extract_graph",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def extract_graph(self, raw_file_id: str) -> str:
    """
    从文本块中提取命名实体和关系，并写入 Neo4j。

    推进 t_raw_files.f_status：PROCESSING -> DONE（成功）/ FAILED（出错）。
    跳过内容少于 50 个字符的块（无有效实体）。
    所有 Neo4j 写入均使用 MERGE，可安全重试。
    返回 raw_file_id。
    """
    rt = get_runtime()
    raw_file_repo = RawFileRepository(rt.db_engine)
    chunk_repo = TextChunkRepository(rt.db_engine)
    graph = GraphStore(rt.neo4j_driver)

    raw_file = raw_file_repo.find_by_id(raw_file_id)
    if not raw_file:
        raise Match3Exception.of_code(
            codes.RAW_FILE_NOT_FOUND, "raw file not found"
        ).ctx(raw_file_id=raw_file_id)

    chunks = chunk_repo.find_by_raw_file_id(raw_file_id)
    text_chunks = [
        c for c in chunks
        if c.chunk_type == constants.CHUNK_TYPE_TEXT and len(c.content) >= 50
    ]

    try:
        for chunk in text_chunks:
            prompt = _EXTRACT_PROMPT.format(text=chunk.content[:3000])

            try:
                content = rt.llm.complete(
                    messages=[{"role": "user", "content": prompt}],
                    model=rt.config.llm.default_model,
                    temperature=0,
                    response_format={"type": "json_object"},
                )
            except Exception as e:
                raise Match3Exception.of("failed to extract entities from llm").ctx(
                    chunk_id=chunk.id
                ).as_ex(e)

            try:
                data = json.loads(content)
            except Exception as e:
                raise Match3Exception.of("failed to parse entity extraction json").ctx(
                    chunk_id=chunk.id
                ).as_ex(e)

            workspace_id = chunk.workspace_id
            entities = [
                {**ent, "id": f"{workspace_id}:{ent['id']}"}
                for ent in data.get("entities", [])
            ]

            try:
                graph.upsert_entities_batch(entities, workspace_id)
                graph.upsert_chunk_node(chunk.id, workspace_id, raw_file_id)
                for ent in entities:
                    graph.upsert_mentions(chunk.id, ent["id"], workspace_id)
                rel_rows = [
                    {
                        "from_id": f"{workspace_id}:{r['from']}",
                        "to_id":   f"{workspace_id}:{r['to']}",
                        "relation": r.get("relation", "RELATED_TO"),
                        "weight":   float(r.get("weight", 1.0)),
                    }
                    for r in data.get("relations", [])
                ]
                graph.upsert_relations_batch(rel_rows, workspace_id)
            except Exception as e:
                raise Match3Exception.of("failed to write graph").ctx(
                    chunk_id=chunk.id, workspace_id=workspace_id
                ).as_ex(e)

        raw_file.status = RawFileStatus.DONE
        raw_file_repo.update(raw_file)

    except Match3Exception as exc:
        raw_file.status = RawFileStatus.FAILED
        raw_file.error = str(exc)
        raw_file_repo.update(raw_file)
        raise

    except Exception as exc:
        raw_file.status = RawFileStatus.FAILED
        raw_file.error = str(exc)
        raw_file_repo.update(raw_file)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            raise

    return raw_file_id
```
