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

## 核心实现

**文件**：`app/workers/tasks/ingest_task.py`

```python
@celery_app.task(name="…ingest_file", bind=True, max_retries=3, default_retry_delay=10)
def ingest_file(self, raw_file_id: str) -> str:

    raw_file = raw_file_repo.find_by_id(raw_file_id)   # raises RAW_FILE_NOT_FOUND if missing
    raw_file.status = PROCESSING
    raw_file_repo.update(raw_file)

    try:
        file_bytes = rt.storage.get_object(raw_file.object_key)
        pages      = parse_file(file_bytes, raw_file.filename, raw_file.file_type, rt.llm, ...)

        all_chunks = []
        for page_idx, page_text in enumerate(pages):
            for seg_idx, segment in enumerate(chunk_text(page_text, chunk_size=512, overlap=64)):
                all_chunks.append(TextChunk(
                    id=str(uuid4()), workspace_id=raw_file.workspace_id,
                    raw_file_id=raw_file_id, chunk_index=page_idx * 1000 + seg_idx,
                    chunk_type=CHUNK_TYPE_TEXT, content=segment,
                    topic_tags=list(raw_file.tags), ...
                ))

        chunk_repo.bulk_insert(all_chunks)
        raw_file.status = DONE
        raw_file.chunk_count = len(all_chunks)
        raw_file_repo.update(raw_file)

    except (Match3Exception, Exception) as exc:
        raw_file.status = FAILED
        raw_file.error  = str(exc)
        raw_file_repo.update(raw_file)
        raise self.retry(exc=exc)   # MaxRetriesExceededError propagates on final attempt

    chain(embed_chunks.si(raw_file_id), extract_graph.si(raw_file_id)).delay()
    return raw_file_id
```

> `parse_file()` 根据 `file_type` 分发：PDF → PyMuPDF，图片 → CLIP caption，音视频 → 转录器，文本 → 直接读取。
