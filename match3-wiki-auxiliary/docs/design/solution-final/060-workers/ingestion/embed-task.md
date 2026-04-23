# Embed Task

## 职责

`embed_chunks` 是导入流水线的**第二阶段**，由 `ingest_file` 通过 `chain` 自动触发。它从 PostgreSQL 读取某个原始文件的所有 `TextChunk`，分批生成稠密向量（`text-embedding-3-small`）和稀疏向量（BM25），然后同时写入 Milvus 和 Elasticsearch。

成功后将 `t_raw_files.f_status` 推进到 `DONE`，失败时写入 `FAILED`。

---

## 队列与并发

| 属性 | 值 |
|------|----|
| 队列名 | `constants.QUEUE_EMBED` (`"embed"`) |
| 推荐并发 | 4 |
| max_retries | 3 |
| 重试间隔 | 30 s（较长，因为 OpenAI 速率限制需要退避） |
| 硬超时 | 无 |

---

## 执行步骤

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 查询 chunks | 通过 `raw_file_id` 从 PostgreSQL 加载全部 `TextChunk` |
| 2 | 分批处理 | 每批 32 条，避免触发 OpenAI 速率限制 |
| 3 | 生成向量 | `rt.embedder.embed_both(texts)` 同时返回 dense + sparse 向量 |
| 4 | Milvus upsert | `milvus_store.upsert_chunks(rows)`，以 `f_chunk_id` 为主键幂等覆盖写 |
| 5 | ES index | `es_store.index_chunks(rows)`，以 `f_chunk_id` 为 `_id` 幂等覆盖写 |
| 6 | 状态推进 `DONE` | 全部批次写完后更新 `t_raw_files.f_status` |

---

## 状态机流转

```
PROCESSING  (由 ingest_task 写入)
  │  embed_chunks 开始执行
  │  全部批次写入成功
  ▼
DONE  ──→  graph_task 继续
  │
  │  任何异常（含超过 max_retries）
  ▼
FAILED
```

---

## 幂等性

- **Milvus**：`upsert` 语义，同一 `f_chunk_id` 重复写入会覆盖，不会产生重复向量。
- **Elasticsearch**：`PUT /<index>/_doc/<f_chunk_id>`，HTTP PUT 幂等。
- 任意批次失败时整个任务重试，已成功的批次会被幂等重写（无副作用）。

---

## 跨存储字段对齐

写入 Milvus 和 ES 时，以下字段必须与 PostgreSQL 保持一致：

| 字段 | PostgreSQL | Milvus | ES |
|------|-----------|--------|----|
| 块唯一标识 | `f_chunk_id` | `id` (primary key) | `_id` |
| 工作区 | `f_workspace_id` | `workspace_id` (scalar) | `workspace_id` |
| 话题标签 | `f_topic_tags TEXT[]` | `topic_tags` (VARCHAR, 逗号分隔) | `topic_tags` (keyword array) |
| 块类型 | `f_chunk_type` | `chunk_type` (scalar) | `chunk_type` |

---

## 源码

```python
# app/workers/tasks/embed_task.py
from __future__ import annotations
from app.workers.celery_app import celery_app
from app.workers.worker_runtime import get_runtime
from app.common.exceptions import Match3Exception
from app.storage.repositories.raw_file_repo import RawFileRepository
from app.storage.repositories.text_chunk_repo import TextChunkRepository
from app.storage.milvus_store import MilvusStore
from app.storage.es_store import ESStore
from app.storage.entities.raw_file import RawFileStatus
import app.common.constants.codes as codes


@celery_app.task(
    name="app.workers.tasks.embed_task.embed_chunks",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def embed_chunks(self, raw_file_id: str) -> str:
    """
    为某个原始文件的所有文本块生成稠密 + 稀疏向量，
    并写入 Milvus（upsert）和 Elasticsearch（index）。

    推进 t_raw_files.f_status：PROCESSING -> DONE（成功）/ FAILED（出错）。
    每批处理 32 条，避免触发 OpenAI 速率限制。
    返回 raw_file_id 供下游 graph_task 使用。
    """
    rt = get_runtime()
    raw_file_repo = RawFileRepository(rt.db_engine)
    chunk_repo = TextChunkRepository(rt.db_engine)
    milvus = MilvusStore(rt.milvus_client)
    es = ESStore(rt.es_client)

    raw_file = raw_file_repo.find_by_id(raw_file_id)
    if not raw_file:
        raise Match3Exception.of_code(
            codes.RAW_FILE_NOT_FOUND, "raw file not found"
        ).ctx(raw_file_id=raw_file_id)

    chunks = chunk_repo.find_by_raw_file_id(raw_file_id)
    if not chunks:
        raw_file.status = RawFileStatus.DONE
        raw_file_repo.update(raw_file)
        return raw_file_id

    try:
        BATCH = 32
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            texts = [c.content for c in batch]

            try:
                dense_vecs, sparse_vecs = rt.embedder.embed_both(texts)
            except Exception as e:
                raise Match3Exception.of("failed to embed_both").ctx(
                    raw_file_id=raw_file_id,
                    batch_start=i,
                    batch_size=len(batch),
                ).as_ex(e)

            rows = [
                {
                    "id": c.id,
                    "workspace_id": c.workspace_id,
                    "raw_file_id": c.raw_file_id,
                    "chunk_type": c.chunk_type,
                    "topic_tags": ",".join(c.topic_tags),
                    "dense_vector": dense,
                    "sparse_vector": sparse,
                    "content": c.content,
                }
                for c, dense, sparse in zip(batch, dense_vecs, sparse_vecs)
            ]

            try:
                milvus.upsert_chunks(rows)
            except Exception as e:
                raise Match3Exception.of("failed to milvus upsert_chunks").ctx(
                    raw_file_id=raw_file_id, batch_start=i
                ).as_ex(e)

            try:
                es.index_chunks(rows)
            except Exception as e:
                raise Match3Exception.of("failed to es index_chunks").ctx(
                    raw_file_id=raw_file_id, batch_start=i
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
