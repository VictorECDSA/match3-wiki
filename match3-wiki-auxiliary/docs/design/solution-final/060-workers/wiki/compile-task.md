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
| 2 | 运行五步流水线 | `run_compile_pipeline(rt, topic, workspace_id)` — 详见 `030-rag/path-entry.md`（wiki-lookup 实现） |
| 3 | 写回结果 | `page.status = PUBLISHED`，写入 `title / category / content / f_source_chunk_ids / compiled_at` |
| 4 | 失败回写 | 任何异常：`page.status = FAILED`，写入 `page.error` |

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
- 编译完成后覆盖写 `content / title / category / f_source_chunk_ids / compiled_at`

这意味着旧版本在编译期间暂时不可读（`status = COMPILING`），前端需根据状态展示"正在更新"提示。

---

## 源码

```python
# app/workers/tasks/compile_task.py
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from app.workers.celery_app import celery_app
from app.workers.worker_runtime import get_runtime
from app.common.exceptions import Match3Exception
from app.storage.repositories.wiki_page_repo import WikiPageRepository
from app.storage.entities.wiki_page import WikiPage, WikiPageStatus
from app.services.wiki_compile_pipeline import run_compile_pipeline


@celery_app.task(
    name="app.workers.tasks.compile_task.compile_topic",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    time_limit=300,
    soft_time_limit=270,
)
def compile_topic(self, topic: str, workspace_id: str) -> str:
    """
    使用 OpenKB 五步流水线为指定话题编译 Wiki 页面。

    若 WikiPage 记录不存在则新建；若已存在则复用并覆盖写。
    状态流转：QUEUED -> COMPILING -> PUBLISHED（成功）/ FAILED（出错）。
    成功时返回 wiki_page_id。
    """
    rt = get_runtime()
    wiki_repo = WikiPageRepository(rt.db_engine)
    now = datetime.now(timezone.utc)

    # 创建或复用 WikiPage 行
    page = wiki_repo.find_by_topic(topic, workspace_id)
    if not page:
        page = WikiPage(
            id=str(uuid4()),
            workspace_id=workspace_id,
            topic=topic,
            title=topic,            # 占位符；流水线将设置真实 title
            status=WikiPageStatus.COMPILING,
            created_at=now,
            updated_at=now,
        )
        wiki_repo.insert(page)
    else:
        page.status = WikiPageStatus.COMPILING
        page.error = None
        page.updated_at = now
        wiki_repo.update(page)

    try:
        content, title, category, source_chunk_ids = run_compile_pipeline(
            rt, topic, workspace_id
        )
    except Match3Exception as exc:
        page.status = WikiPageStatus.FAILED
        page.error = str(exc)
        page.updated_at = datetime.now(timezone.utc)
        wiki_repo.update(page)
        raise
    except Exception as exc:
        page.status = WikiPageStatus.FAILED
        page.error = str(exc)
        page.updated_at = datetime.now(timezone.utc)
        wiki_repo.update(page)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            raise

    page.status = WikiPageStatus.PUBLISHED
    page.title = title
    page.category = category
    page.content = content
    page.source_chunk_ids = source_chunk_ids
    page.compiled_at = datetime.now(timezone.utc)
    page.updated_at = page.compiled_at
    wiki_repo.update(page)

    return page.id
```
