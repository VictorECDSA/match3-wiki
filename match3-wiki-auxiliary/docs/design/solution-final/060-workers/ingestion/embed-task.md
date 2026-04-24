# Embed Task

## 职责

`embed_chunks` 是导入流水线的**第二阶段**，由 `ingest_file` 通过 `chain` 自动触发。它从 PostgreSQL 读取某个原始文件的所有 `TextChunk`，分批生成稠密向量（`text-embedding-3-small`）和稀疏向量（BGE-M3 BM25），然后同时写入 Milvus 和 Elasticsearch。

---

## 队列与并发

| 属性 | 值 |
|------|----|
| 队列名 | `constants.QUEUE_EMBED` (`"embed"`) |
| 推荐并发 | 4 |
| max_retries | 3 |
| 重试间隔 | 30 s（OpenAI 速率限制退避） |
| 硬超时 | 无 |

---

## 执行步骤

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 查询 chunks | `chunk_repo.find_by_raw_file_id(raw_file_id)`；无 chunk 则直接推进 DONE |
| 2 | 分批处理 | `BATCH = 32`，循环直至全部处理完 |
| 3 | 生成向量 | `embedder.embed_both(texts)` → `(dense_vecs, sparse_vecs)`；`embedder` 在任务内部实例化 |
| 4 | Milvus upsert | `milvus_store.upsert_chunks(rows)`，以 chunk_id 为主键幂等覆盖写 |
| 5 | ES index | `es_store.index_chunks(rows)`，以 chunk_id 为 `_id` 幂等覆盖写 |
| 6 | 状态推进 `DONE` | 全部批次写完后更新 `t_raw_files.f_status` |

---

## 状态机流转

```
PROCESSING  (written by ingest_task)
  │  embed_chunks starts
  │  all batches written successfully
  ▼
DONE  ──→  graph_task continues
  │
  │  any exception (including max_retries exceeded)
  ▼
FAILED
```

---

## 幂等性

- **Milvus**：`upsert` 语义，同一 chunk_id 重复写入会覆盖，不会产生重复向量。
- **Elasticsearch**：`PUT /<index>/_doc/<chunk_id>`，HTTP PUT 幂等。
- 任意批次失败时整个任务重试，已成功的批次会被幂等重写（无副作用）。

---

## 跨存储字段对齐

写入 Milvus 和 ES 时，以下字段必须与 PostgreSQL 保持一致：

| 字段 | PostgreSQL | Milvus | ES |
|------|-----------|--------|----|
| 块唯一标识 | `f_chunk_id` | `id` (primary key) | `_id` |
| 工作区 | `f_workspace_id` | `workspace_id` (scalar) | `workspace_id` |
| 话题标签 | `f_topic_tags TEXT[]` | `topic_tags` (VARCHAR, 逗号拼接) | `topic_tags` (keyword array) |
| 块类型 | `f_chunk_type` | `chunk_type` (scalar) | `chunk_type` |

---

## 核心实现

**文件**：`app/workers/tasks/embed_task.py`

```python
@celery_app.task(name="…embed_chunks", bind=True, max_retries=3, default_retry_delay=30)
def embed_chunks(self, raw_file_id: str) -> str:

    chunks = chunk_repo.find_by_raw_file_id(raw_file_id)
    if not chunks:
        raw_file.status = DONE; raw_file_repo.update(raw_file); return raw_file_id

    try:
        from app.intelligence.embedder import OpenAIEmbedder
        embedder = OpenAIEmbedder(api_key=rt.env.OPENAI_API_KEY, model=rt.config.embed.model)

        BATCH = 32
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            dense_vecs, sparse_vecs = embedder.embed_both([c.content for c in batch])

            rows = [{"id": c.id, "workspace_id": c.workspace_id, "raw_file_id": c.raw_file_id,
                     "chunk_type": c.chunk_type, "topic_tags": ",".join(c.topic_tags),
                     "dense_vector": dense, "sparse_vector": sparse, "content": c.content}
                    for c, dense, sparse in zip(batch, dense_vecs, sparse_vecs)]

            rt.vector_db.upsert_chunks(rows)
            rt.search.index_chunks(rows)

        raw_file.status = DONE
        raw_file_repo.update(raw_file)

    except Exception as exc:
        raw_file.status = FAILED; raw_file.error = str(exc)
        raw_file_repo.update(raw_file)
        raise self.retry(exc=exc)

    return raw_file_id
```
