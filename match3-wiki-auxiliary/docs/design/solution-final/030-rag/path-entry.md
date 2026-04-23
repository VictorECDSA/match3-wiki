# wiki-lookup：Wiki 编译流水线

## 概述

wiki-lookup 负责 Wiki 页面的编译与查找。它实现了带有并行子智能体的 OpenKB 五步编译流水线。

Wiki 页面是"一次编译"的产物——由 LLM 智能体从原始素材生成，随后以结构化 Markdown 文件形式存储。当用户查询某个 Wiki 条目时，系统直接返回已编译好的页面（速度快，无需检索）。若页面已过期（源文件比编译时间更新），则触发重新编译。

---

## OpenKB 五步编译流水线

```
主题原始素材
        │
  第一步：Context A
  ┌─────▼────────────────────────────────────────────────────┐
  │ 收集所有标记到该主题的原始文件                            │
  │ 通过 hybrid_search 检索 top-50 相关块                    │
  │ 构建"Context A"——完整原始素材                            │
  └─────┬────────────────────────────────────────────────────┘
        │
  第二步：摘要
  ┌─────▼────────────────────────────────────────────────────┐
  │ LLM 将 Context A 浓缩为结构化摘要                        │
  │ （约 500 字，保留所有事实与数据）                        │
  └─────┬────────────────────────────────────────────────────┘
        │
  第三步：概念规划
  ┌─────▼────────────────────────────────────────────────────┐
  │ LLM 列出所有需要覆盖的概念/子章节                        │
  │ 基于摘要 + 主题 Schema 提示（见下表）                    │
  └─────┬────────────────────────────────────────────────────┘
        │
  第四步：并行概念生成（共享前缀缓存）
  ┌─────▼────────────────────────────────────────────────────┐
  │ 启动 N 个 Celery 子任务（每个概念一个）                   │
  │ 每个子任务：使用 Context A 编写一个章节                   │
  │ 共享系统提示前缀 → LLM 提供商缓存该部分                  │
  │ chord() 收集所有结果                                     │
  └─────┬────────────────────────────────────────────────────┘
        │
  第五步：交叉链接
  ┌─────▼────────────────────────────────────────────────────┐
  │ LLM 向其他 Wiki 条目插入 [[wikilinks]]                    │
  │ 添加 YAML frontmatter（topic, tags, compiled_date）       │
  │ 组装最终 Markdown 页面，保存到 PostgreSQL + MinIO         │
  └─────────────────────────────────────────────────────────┘
```

---

## 主题 Schema 提示

`_get_topic_schema_hint(topic)` 根据前缀返回必填章节列表：

| 主题前缀 | 必填章节 |
|----------|---------|
| `entities/` | Overview, Developer Info, Revenue & Downloads, Core Mechanics, UA Strategy, Retention Data, Key Milestones |
| `market/` | Market Size, Top Products, Regional Breakdown, Revenue Tiers, Year-over-Year Trends |
| `mechanics/` | Mechanic Description, Games Using It, Player Psychology, Implementation Variants, Metrics Impact |
| `growth/` | Creative Format Description, Platform (Meta/TikTok/Google), Hook Analysis, Performance Data, Examples |

---

## WikiCompileService

**文件**：`app/services/wiki_compile_service.py`

| 方法 | 说明 |
|------|------|
| `compile(topic, workspace_id, force=False) → task_id` | 检查页面是否存在且未过期（`compiled_at < latest_raw.created_at`），若过期或不存在则 `compile_task.apply_async(queue=QUEUE_COMPILE)`；已是最新则返回 `"wiki_page:{id}:already_up_to_date"` |
| `get_page(topic, workspace_id) → WikiPage?` | `wiki_repo.find_by_topic(topic, workspace_id)` |
| `list_pages(workspace_id, category?) → list[WikiPage]` | `wiki_repo.find_all(workspace_id, category=category)` |

---

## 编译任务（Celery Worker）

**文件**：`app/workers/tasks/compile_task.py`

```python
@celery_app.task(name="…compile_topic", bind=True, max_retries=1,
                 time_limit=300, soft_time_limit=240)
def compile_task(self, topic: str, workspace_id: str) -> None:

    # upsert WikiPage with status=COMPILING
    page = wiki_repo.find_by_topic(topic, workspace_id) or wiki_repo.insert(WikiPage(...))
    wiki_repo.update_status(page.id, COMPILING)

    try:
        result = _run_pipeline(rt, topic, workspace_id, page.id)
    except Exception as e:
        wiki_repo.update_status(page.id, FAILED, error=str(e)); raise

    wiki_repo.update_content(page.id, content=result["content"], status=PUBLISHED)
```

### _run_pipeline() — 五步顺序执行

```
context_a = _gather_context_a(rt, topic, workspace_id)
    # tagged raw files (top 20, top 10 chunks each) + hybrid_search top-50

summary   = llm("Summarize … preserve all facts … 400-600 words\n\n{context_a[:12000]}")

concepts  = json.loads(llm(
    "List main concepts … {schema_hint} … Return JSON: {concepts: [...]}\n\n{summary}",
    response_format=json_object
))["concepts"]

system_prefix = "You are a wiki writer … Topic: {topic}\nSummary: …\nContext: {context_a[:8000]}"
# shared across all section subtasks → LLM provider caches this prefix

sections  = [llm(system_prefix + "Write section for '{concept}' … 200-500 words.")
             for concept in concepts]

final     = llm("Add [[wikilinks]] from {all_topics[:50]} … add YAML frontmatter …\n\n{assembled}")
return {"content": final}
```

---

## 条目查找

**文件**：`app/rag/entry/entry_lookup.py`

```
lookup_or_trigger_compile(rt, query, workspace_id) → WikiPage | None

1. wiki_repo.find_by_topic(query, workspace_id)  → exact match
2. es.search(ES_INDEX_WIKI, multi_match on title^3 + content, filter workspace_id, size=3)
   → return wiki_repo.find_by_id(hits[0]["_id"])
3. return None  (caller triggers compile)
```
