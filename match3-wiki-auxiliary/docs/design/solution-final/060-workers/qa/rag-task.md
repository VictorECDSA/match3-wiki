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
task_id = launch_multi_agent_chord(
    query="Royal Match 的核心留存机制是什么？",
    workspace_id="ws_abc123",
    domains=["entities", "market", "mechanics", "growth"],
)
# returns Celery task_id; caller polls GET /api/v1/qa/tasks/{task_id}
```

---

## 核心实现

**文件**：`app/workers/tasks/rag_task.py`

```python
@celery_app.task(name="…domain_agent_task", bind=True, max_retries=2, time_limit=60)
def domain_agent_task(self, domain: str, query: str, workspace_id: str) -> dict:
    answer = _run_domain_agent(rt, domain, query, workspace_id)
    return {"domain": domain, "answer": answer}


@celery_app.task(name="…multi_agent_verify_task", bind=True, max_retries=1, time_limit=120)
def multi_agent_verify_task(self, domain_results: list[dict], query: str, workspace_id: str) -> str:
    # domain_results is auto-injected by Celery chord as first argument
    return _verify_answers(rt, domain_results, query)


def launch_multi_agent_chord(query, workspace_id, domains=("entities","market","mechanics","growth")) -> str:
    header = [domain_agent_task.si(domain, query, workspace_id) for domain in domains]
    callback = multi_agent_verify_task.s(query, workspace_id)
    result = chord(header)(callback)
    return result.id  # caller polls this task_id for final_answer
```
