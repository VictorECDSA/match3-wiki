# Ingest Task

## 职责

`ingest_file` 是导入流水线的**第一阶段**。它从 MinIO 下载原始文件，解析为文本页面，切分为带重叠的文本块，将所有 `TextChunk` 持久化到 PostgreSQL，然后触发后续的嵌入和图谱提取任务。

整个流水线的状态机由本任务负责推进 `PENDING → PROCESSING`，成功后推进到 `DONE`，失败时写入 `FAILED`。

---

## 队列与并发

| 属性 | 值 |
|------|----|
| 队列名 | `constants.QUEUE_INGEST` (`"ingest"`) |
| 推荐并发 | 4 |
| max_retries | 3 |
| 重试间隔 | 10 s |
| 硬超时 | 无 |

---

## 执行步骤

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 查询 `RawFile` | 通过 `raw_file_id` 从 PostgreSQL 加载文件元数据；若不存在则抛 `RAW_FILE_NOT_FOUND` |
| 2 | 状态推进 `PROCESSING` | 立即写库，防止并发重复执行同一文件 |
| 3 | 从 MinIO 下载 | 按 `f_object_key` 拉取原始字节 |
| 4 | 解析文件 | `parse_file()` 根据 `file_type` 分发到对应解析器，返回页面文本列表 |
| 5 | 文本分块 | `chunk_text()` 对每页文本滑窗切分（`chunk_size=512, overlap=64`），生成 `TextChunk` 对象 |
| 6 | 批量写入 PostgreSQL | `chunk_repo.bulk_insert(all_chunks)` |
| 7 | 状态推进 `DONE` | 同时写入 `f_chunk_count` |
| 8 | 链式触发 | `chain(embed_chunks.si(raw_file_id), extract_graph.si(raw_file_id)).delay()` |

---

## 状态机流转

```
PENDING
  │  ingest_file 开始执行
  ▼
PROCESSING
  │  bulk_insert 成功
  ▼
DONE  ──→  embed_task 继续
  │
  │  任何异常（含超过 max_retries）
  ▼
FAILED
```

---

## 幂等性

- `TextChunkRepository.bulk_insert` 使用 `INSERT … ON CONFLICT (f_chunk_id) DO UPDATE`，重试时不会产生重复行。
- 状态从 `PROCESSING` 推进到 `DONE` 发生在 `bulk_insert` 之后；如果 Worker 在 `bulk_insert` 成功后、状态更新前崩溃，重试时 PG 中的 chunk 会被幂等覆盖写，状态最终正确更新。

---

## 源码

```python
# app/workers/tasks/ingest_task.py
from __future__ import annotations
from celery import chain
from app.workers.celery_app import celery_app
from app.workers.worker_runtime import get_runtime
from app.common.exceptions import Match3Exception
from app.storage.repositories.raw_file_repo import RawFileRepository
from app.storage.repositories.text_chunk_repo import TextChunkRepository
from app.storage.entities.raw_file import RawFileStatus
from app.storage.entities.text_chunk import TextChunk
from app.ingest.file_parser import parse_file
from app.ingest.chunker import chunk_text
from app.common.constants import constants
import app.common.constants.codes as codes
from uuid import uuid4
from datetime import datetime, timezone


@celery_app.task(
    name="app.workers.tasks.ingest_task.ingest_file",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def ingest_file(self, raw_file_id: str) -> str:
    """
    将原始文件解析为 PostgreSQL 中的 TextChunk 记录。

    推进 t_raw_files.f_status：
      PENDING -> PROCESSING -> DONE   （成功）
      PROCESSING -> FAILED            （出错）

    成功后，为同一 raw_file_id 链式触发 embed_chunks -> extract_graph。
    返回 raw_file_id 供下游任务使用。
    """
    rt = get_runtime()
    raw_file_repo = RawFileRepository(rt.db_engine)
    chunk_repo = TextChunkRepository(rt.db_engine)

    raw_file = raw_file_repo.find_by_id(raw_file_id)
    if not raw_file:
        raise Match3Exception.of_code(
            codes.RAW_FILE_NOT_FOUND,
            "raw file not found",
        ).ctx(raw_file_id=raw_file_id)

    # 推进到 PROCESSING，防止并发重试重复执行同一文件
    raw_file.status = RawFileStatus.PROCESSING
    raw_file_repo.update(raw_file)

    try:
        # 步骤 1：从 MinIO 下载
        try:
            file_bytes = rt.storage.get_object(raw_file.object_key)
        except Exception as e:
            raise Match3Exception.of("failed to get_object").ctx(
                object_key=raw_file.object_key
            ).as_ex(e)

        # 步骤 2：解析为页面列表
        try:
            pages = parse_file(
                file_bytes=file_bytes,
                filename=raw_file.filename,
                file_type=raw_file.file_type,
                llm=rt.llm,
                image_embedder=rt.image_embedder,
                transcriber=rt.transcriber,
            )
        except Exception as e:
            raise Match3Exception.of("failed to parse_file").ctx(
                raw_file_id=raw_file_id,
                file_type=raw_file.file_type,
            ).as_ex(e)

        # 步骤 3：对每页文本进行分块
        all_chunks: list[TextChunk] = []
        for page_idx, page_text in enumerate(pages):
            segments = chunk_text(page_text, chunk_size=512, overlap=64)
            for seg_idx, segment in enumerate(segments):
                chunk = TextChunk(
                    id=str(uuid4()),
                    workspace_id=raw_file.workspace_id,
                    raw_file_id=raw_file_id,
                    parent_chunk_id=None,
                    chunk_index=page_idx * 1000 + seg_idx,
                    chunk_type=constants.CHUNK_TYPE_TEXT,
                    content=segment,
                    token_count=len(segment.split()),
                    topic_tags=list(raw_file.tags),
                    created_at=datetime.now(timezone.utc),
                )
                all_chunks.append(chunk)

        # 步骤 4：持久化到 PostgreSQL
        chunk_repo.bulk_insert(all_chunks)

        # 步骤 5：推进状态到 DONE
        raw_file.status = RawFileStatus.DONE
        raw_file.chunk_count = len(all_chunks)
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

    # 步骤 6：链式触发 embed + graph 任务
    from app.workers.tasks.embed_task import embed_chunks
    from app.workers.tasks.graph_task import extract_graph

    chain(
        embed_chunks.si(raw_file_id),
        extract_graph.si(raw_file_id),
    ).delay()

    return raw_file_id
```
