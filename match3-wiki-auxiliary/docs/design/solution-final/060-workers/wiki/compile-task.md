# Compile Task

## 职责

`compile_topic` 负责为某个用户定义的话题编译一篇 Wiki 页面。它通过 OpenKB 五步流水线（分解 → 并行检索 → 事实抽取 → 起草 → 自我反思）从工作区的全部语料中合成结构化知识页面，写入 `t_wiki_pages`。

本任务由 `POST /api/v1/wiki/compile` 端点触发，与导入流水线完全独立。

---

## 队列与并发

| 属性 | 值 |
|------|----|
| 队列名 | `constants.QUEUE_COMPILE` (`"compile"`) |
| 推荐并发 | 2 |
| max_retries | 2 |
| 重试间隔 | 30 s |
| 硬超时 | 300 s（5 分钟）|
| 软超时 | 270 s |

并发设为 2 是因为每次编译涉及多轮 LLM 调用，单任务耗时较长（通常 30–120 s），太高并发会导致 LLM API 费用激增。

---

## 执行步骤

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 创建/更新 WikiPage 记录 | `find_by_topic` 若存在则复用，否则新建；状态设为 `COMPILING` |
| 2 | 运行五步流水线 | `run_compile_pipeline(rt, topic, workspace_id)` — 详见 `030-rag/wiki-lookup.md` |
| 3 | 写回结果 | `page.status = PUBLISHED`，写入 `title / category / content / source_chunk_ids / compiled_at` |
| 4 | 失败回写 | `Match3Exception`：`FAILED` + `raise`（不重试）；其他异常：`FAILED` + `retry()`（最多 2 次）|

---

## 状态机流转

```
(无记录 / PUBLISHED / FAILED)
  │  compile_topic 触发
  ▼
QUEUED  ← API 层写入，任务入队时
  │  Worker 开始执行
  ▼
COMPILING
  │  run_compile_pipeline 返回
  ▼
PUBLISHED  ← 前端可读取
  │
  │  任何异常（含超过 max_retries）
  ▼
FAILED
```

---

## 重新编译行为

对同一 `(topic, workspace_id)` 重复触发编译时：
- 复用已有的 `WikiPage` 行（`find_by_topic` 命中）
- 重置 `status = COMPILING`、`error = None`
- 编译完成后覆盖写 `content / title / category / source_chunk_ids / compiled_at`

这意味着旧版本在编译期间暂时不可读（`status = COMPILING`），前端需根据状态展示"正在更新"提示。

---

## 核心实现

**文件**：`app/workers/tasks/compile_task.py`

```python
@celery_app.task(name="…compile_topic", bind=True, max_retries=2, default_retry_delay=30,
                 time_limit=300, soft_time_limit=270)
def compile_topic(self, topic: str, workspace_id: str) -> str:
    wiki_repo = WikiPageRepository(rt.db_engine)

    # upsert: create new or reuse existing WikiPage row, set status=COMPILING
    page = wiki_repo.find_by_topic(topic, workspace_id)
    if not page:
        page = WikiPage(id=str(uuid4()), workspace_id=workspace_id, topic=topic,
                        title=topic,  # placeholder; pipeline will set real title
                        status=WikiPageStatus.COMPILING, created_at=now, updated_at=now)
        wiki_repo.insert(page)
    else:
        page.status = WikiPageStatus.COMPILING; page.error = None
        wiki_repo.update(page)

    try:
        content, title, category, source_chunk_ids = run_compile_pipeline(rt, topic, workspace_id)
    except Match3Exception as exc:
        page.status = WikiPageStatus.FAILED; page.error = str(exc)
        wiki_repo.update(page); raise   # business error: no retry
    except Exception as exc:
        page.status = WikiPageStatus.FAILED; page.error = str(exc)
        wiki_repo.update(page)
        raise self.retry(exc=exc)       # MaxRetriesExceededError propagates naturally

    page.status = WikiPageStatus.PUBLISHED; page.title = title; page.category = category
    page.content = content; page.source_chunk_ids = source_chunk_ids
    page.compiled_at = datetime.now(timezone.utc)
    wiki_repo.update(page)
    return page.id
```
