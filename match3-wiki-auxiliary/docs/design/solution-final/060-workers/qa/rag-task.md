# RAG Task

## 职责

`rag_task` 提供多智能体 RAG 的**异步 Celery chord 执行路径**。它将查询分发给多个并行的领域子智能体（`domain_agent_task`），各子智能体独立检索并回答，最终由 `multi_agent_verify_task` 汇总验证所有答案，合成最终响应。

> **默认路径**：Q&A 端点通常使用 `030-rag/multi-agent.md` 中描述的**同步路径**（在单个请求生命周期内并发执行子智能体），无需 Celery。本任务仅在需要将多智能体 RAG 异步化（例如任务队列化、断点续跑）时使用。

---

## 队列与并发

| 属性 | 值 |
|------|----|
| 队列名 | `constants.QUEUE_RAG` (`"rag"`) |
| 推荐并发 | 4 |
| `domain_agent_task` max_retries | 2 |
| `domain_agent_task` 硬超时 | 60 s |
| `multi_agent_verify_task` max_retries | 1 |
| `multi_agent_verify_task` 硬超时 | 120 s |

---

## 执行结构（Celery Chord）

```
launch_multi_agent_chord(query, workspace_id, domains)
  │
  ├─ domain_agent_task("entities", query, workspace_id)  ─┐
  ├─ domain_agent_task("market",   query, workspace_id)  ─┤  并行
  ├─ domain_agent_task("mechanics",query, workspace_id)  ─┤
  └─ domain_agent_task("growth",   query, workspace_id)  ─┘
                                                          │  所有完成后
                                            multi_agent_verify_task(
                                              domain_results, query, workspace_id
                                            )
                                              │
                                              ▼
                                          final_answer (str)
```

`chord` 保证所有 header 任务完成后才触发 callback，并将所有 header 的返回值列表作为第一个参数传入 callback。

---

## 任务说明

### `domain_agent_task`

每个领域智能体接收同一个用户查询，但只检索与其领域相关的内容（通过 `topic_tags` 或语义过滤），返回 `{"domain": str, "answer": str}` 字典。

默认四个领域：

| 领域 | 检索侧重 |
|------|---------|
| `entities` | 游戏名、公司名、角色等命名实体相关内容 |
| `market` | 市场数据、下载量、收入、趋势 |
| `mechanics` | 游戏机制、关卡设计、玩法特性 |
| `growth` | 买量素材、UA 策略、增长数据 |

### `multi_agent_verify_task`

接收所有领域答案列表，调用 LLM 执行交叉验证和答案合成，返回最终字符串响应。对矛盾信息进行标注，对低置信度内容降权。

---

## 调用方式

```python
from app.workers.tasks.rag_task import launch_multi_agent_chord

task_id = launch_multi_agent_chord(
    query="Royal Match 的核心留存机制是什么？",
    workspace_id="ws_abc123",
    domains=["entities", "market", "mechanics", "growth"],
)
# 返回 Celery task_id，调用方通过 GET /api/v1/qa/tasks/{task_id} 轮询结果
```

---

## 源码

```python
# app/workers/tasks/rag_task.py
from __future__ import annotations
from celery import chord
from app.workers.celery_app import celery_app
from app.workers.worker_runtime import get_runtime
from app.common.exceptions import Match3Exception
from app.services.rag.multi_agent import _run_domain_agent, _verify_answers


@celery_app.task(
    name="app.workers.tasks.rag_task.domain_agent_task",
    bind=True,
    max_retries=2,
    time_limit=60,
)
def domain_agent_task(self, domain: str, query: str, workspace_id: str) -> dict:
    """
    运行单个领域子智能体并以可 JSON 序列化的字典形式返回答案。
    作为多智能体 chord header 的一部分，所有领域并行执行。
    """
    rt = get_runtime()
    try:
        answer = _run_domain_agent(rt, domain, query, workspace_id)
    except Exception as e:
        raise Match3Exception.of("failed to _run_domain_agent").ctx(
            domain=domain,
            workspace_id=workspace_id,
        ).as_ex(e)
    return {"domain": domain, "answer": answer}


@celery_app.task(
    name="app.workers.tasks.rag_task.multi_agent_verify_task",
    bind=True,
    max_retries=1,
    time_limit=120,
)
def multi_agent_verify_task(
    self, domain_results: list[dict], query: str, workspace_id: str
) -> str:
    """
    对所有领域答案进行交叉验证并合成最终响应（chord callback）。
    Celery chord 会自动将 domain_results 作为第一个参数传入。
    """
    rt = get_runtime()
    try:
        final_answer = _verify_answers(rt, domain_results, query)
    except Exception as e:
        raise Match3Exception.of("failed to _verify_answers").ctx(
            workspace_id=workspace_id,
        ).as_ex(e)
    return final_answer


def launch_multi_agent_chord(
    query: str,
    workspace_id: str,
    domains: list[str] = ("entities", "market", "mechanics", "growth"),
) -> str:
    """
    通过 Celery chord 并行启动所有领域子智能体。
    返回验证回调任务的 Celery task ID。
    调用方通过 GET /api/v1/qa/tasks/{task_id} 轮询最终答案。
    """
    header = [
        domain_agent_task.si(domain, query, workspace_id)
        for domain in domains
    ]
    callback = multi_agent_verify_task.s(query, workspace_id)
    result = chord(header)(callback)
    return result.id
```
