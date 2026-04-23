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
  │ 基于摘要 + CLAUDE.md 中的主题 Schema                     │
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
  │ 组装最终 Markdown 页面                                   │
  │ 保存到 PostgreSQL + MinIO                                │
  └─────────────────────────────────────────────────────────┘
```

---

## 实现

### WikiCompileService

```python
# app/services/wiki_compile_service.py
from __future__ import annotations
from app.runtime import Match3Runtime
from app.common.exceptions import Match3Exception
from app.storage.repositories.wiki_page_repo import WikiPageRepository
from app.storage.repositories.raw_file_repo import RawFileRepository
from app.workers.compile_task import compile_task


class WikiCompileService:

    def __init__(self, rt: Match3Runtime):
        self._rt = rt

    def compile(self, topic: str, workspace_id: str, force: bool = False) -> str:
        """触发指定主题的 Wiki 编译，返回 task_id。"""

        wiki_repo = WikiPageRepository(self._rt.db_engine)
        existing = wiki_repo.find_by_topic(topic, workspace_id)

        if existing and not force:
            # 检查是否已过期
            raw_file_repo = RawFileRepository(self._rt.db_engine)
            latest_raw = raw_file_repo.find_latest_by_topic_tag(topic, workspace_id)

            if latest_raw and existing.compiled_at < latest_raw.created_at:
                # 已过期：重新编译
                pass
            else:
                # 已是最新：无需操作
                return f"wiki_page:{existing.id}:already_up_to_date"

        from app.common.constants import constants
        task = compile_task.apply_async(
            args=[topic, workspace_id],
            queue=constants.QUEUE_COMPILE,
        )
        return task.id

    def get_page(self, topic: str, workspace_id: str) -> "WikiPage | None":
        """按主题 slug 查找已编译的 Wiki 页面。"""
        wiki_repo = WikiPageRepository(self._rt.db_engine)
        return wiki_repo.find_by_topic(topic, workspace_id)

    def list_pages(self, workspace_id: str, category: str | None = None) -> list["WikiPage"]:
        """列出所有 Wiki 页面，可按分类过滤。"""
        wiki_repo = WikiPageRepository(self._rt.db_engine)
        return wiki_repo.find_all(workspace_id, category=category)
```

### 编译任务（Celery Worker）

```python
# app/workers/compile_task.py
from celery import chord, group
from app.common.constants import constants


@celery_app.task(
    bind=True,
    max_retries=1,
    queue=constants.QUEUE_COMPILE,
    name="app.workers.tasks.compile_task.compile_topic",
    time_limit=300,
    soft_time_limit=240,
)
def compile_task(self, topic: str, workspace_id: str) -> None:
    """执行 Wiki 五步编译流水线。"""
    rt = get_worker_runtime()
    wiki_repo = WikiPageRepository(rt.db_engine)

    # 标记为编译中
    page = wiki_repo.find_by_topic(topic, workspace_id)
    if page:
        wiki_repo.update_status(page.id, WikiPageStatus.COMPILING)
    else:
        page = wiki_repo.insert(WikiPage(
            id=str(uuid4()),
            topic=topic,
            workspace_id=workspace_id,
            title=_topic_to_title(topic),
            status=WikiPageStatus.COMPILING,
        ))

    try:
        result = _run_pipeline(rt, topic, workspace_id, page.id)
    except Exception as e:
        wiki_repo.update_status(page.id, WikiPageStatus.FAILED, error=str(e))
        raise

    wiki_repo.update_content(
        page.id,
        content=result["content"],
        status=WikiPageStatus.PUBLISHED,
    )


def _run_pipeline(rt: Match3Runtime, topic: str, workspace_id: str, page_id: str) -> dict:
    """在编译任务内同步执行第 1–5 步。"""
    import json

    # 第一步：Context A — 收集原始素材
    context_a = _gather_context_a(rt, topic, workspace_id)

    # 第二步：生成摘要
    summary = _generate_summary(rt, topic, context_a)

    # 第三步：概念规划
    concepts = _plan_concepts(rt, topic, summary)

    # 第四步：并行概念生成
    # 使用 Celery chord：N 个子任务 + 回调
    system_prefix = _build_shared_system_prefix(topic, context_a, summary)

    subtask_results = []
    for concept in concepts:
        section_text = _generate_section(rt, concept, context_a, system_prefix)
        subtask_results.append(section_text)

    # 第五步：交叉链接
    assembled = "\n\n".join(subtask_results)
    final_content = _crosslink(rt, topic, assembled, workspace_id)

    return {"content": final_content}


def _gather_context_a(rt: Match3Runtime, topic: str, workspace_id: str) -> str:
    """收集该主题所有相关原始内容。"""
    # 1. 标记到该主题的原始文件
    raw_file_repo = RawFileRepository(rt.db_engine)
    tagged_files = raw_file_repo.find_by_tag(topic, workspace_id)

    file_contents = []
    for rf in tagged_files[:20]:
        # 获取该文件的文本块
        chunk_repo = ChunkRepository(rt.db_engine)
        chunks = chunk_repo.find_by_raw_file_id(rf.id)
        file_contents.append(
            f"--- Source: {rf.filename} ---\n" +
            "\n".join(c.content for c in chunks[:10])
        )

    # 2. 语义搜索主题相关块
    from app.rag.chunk.hybrid_search import hybrid_search
    search_results = hybrid_search(rt, topic, workspace_id, top_k=50)

    search_content = "\n\n".join(
        f"[Chunk {i+1}]: {r['content']}"
        for i, r in enumerate(search_results)
    )

    return "\n\n".join(file_contents) + "\n\n" + search_content


def _generate_summary(rt: Match3Runtime, topic: str, context_a: str) -> str:
    try:
        resp = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": (
                    f"Summarize all the following information about '{topic}' "
                    f"for a match-3 game knowledge base. Preserve all specific facts, "
                    f"numbers, game names, and dates. Write 400-600 words.\n\n{context_a[:12000]}"
                ),
            }],
        )
    except Exception as e:
        raise Match3Exception.of("failed to generate wiki summary").ctx(topic=topic).as_ex(e)
    return resp


def _plan_concepts(rt: Match3Runtime, topic: str, summary: str) -> list[str]:
    """根据摘要生成 Wiki 页面需要覆盖的概念/章节列表。"""
    schema_hint = _get_topic_schema_hint(topic)

    try:
        resp = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": (
                    f"Based on this summary about '{topic}', list the main concepts "
                    f"and sections that should be covered in a wiki page.\n"
                    f"{schema_hint}\n"
                    f"Return JSON: {{\"concepts\": [\"concept1\", \"concept2\", ...]}}\n\n"
                    f"Summary:\n{summary}"
                ),
            }],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("failed to plan wiki concepts").ctx(topic=topic).as_ex(e)

    import json
    data = json.loads(resp)
    return data.get("concepts", [f"Overview of {topic}"])


def _get_topic_schema_hint(topic: str) -> str:
    """根据主题分类前缀返回 Schema 提示。"""
    if topic.startswith("entities/"):
        return (
            "Required sections: Overview, Developer Info, Revenue & Downloads, "
            "Core Mechanics, UA Strategy, Retention Data, Key Milestones"
        )
    elif topic.startswith("market/"):
        return (
            "Required sections: Market Size, Top Products, Regional Breakdown, "
            "Revenue Tiers, Year-over-Year Trends"
        )
    elif topic.startswith("mechanics/"):
        return (
            "Required sections: Mechanic Description, Games Using It, "
            "Player Psychology, Implementation Variants, Metrics Impact"
        )
    elif topic.startswith("growth/"):
        return (
            "Required sections: Creative Format Description, Platform (Meta/TikTok/Google), "
            "Hook Analysis, Performance Data, Examples"
        )
    return ""


def _build_shared_system_prefix(topic: str, context_a: str, summary: str) -> str:
    """构建共享系统提示前缀。该块在所有章节子任务中保持静态，
    LLM 服务提供商（如 Anthropic cache_control）会对其进行缓存。"""
    return (
        f"You are a wiki writer for a match-3 game knowledge base.\n"
        f"Topic: {topic}\n\n"
        f"Summary of all available information:\n{summary}\n\n"
        f"Full source context (use for specific facts and citations):\n"
        f"{context_a[:8000]}"  # 截断以适应上下文窗口
    )


def _generate_section(
    rt: Match3Runtime,
    concept: str,
    context_a: str,
    system_prefix: str,
) -> str:
    """生成 Wiki 页面的一个章节。"""
    try:
        resp = rt.llm.complete(
            messages=[
                {"role": "system", "content": system_prefix},
                {"role": "user", "content": (
                    f"Write the wiki section for: '{concept}'\n"
                    f"Format: Markdown with ## heading. Be factual. "
                    f"Cite sources as (Source: filename). "
                    f"If data is unavailable, say 'Data not available' rather than speculating. "
                    f"Length: 200-500 words."
                )},
            ],
        )
    except Exception as e:
        raise Match3Exception.of("failed to generate wiki section").ctx(
            concept=concept,
        ).as_ex(e)
    return resp


def _crosslink(
    rt: Match3Runtime,
    topic: str,
    assembled: str,
    workspace_id: str,
) -> str:
    """向其他 Wiki 条目添加 [[wikilinks]] 并组装最终页面。"""
    wiki_repo = WikiPageRepository(rt.db_engine)
    all_topics = [p.topic for p in wiki_repo.find_all(workspace_id)]
    topics_list = ", ".join(all_topics[:50])

    try:
        resp = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": (
                    f"Add Obsidian [[wikilinks]] to the following wiki text. "
                    f"Link to these existing wiki topics where appropriate: {topics_list}\n"
                    f"Also add YAML frontmatter with topic, tags, and compiled_date.\n"
                    f"Return the complete final wiki page.\n\n{assembled}"
                ),
            }],
        )
    except Exception as e:
        raise Match3Exception.of("failed to crosslink wiki page").ctx(topic=topic).as_ex(e)

    return resp


def _topic_to_title(topic: str) -> str:
    """将 'entities/royal-match' 转换为 'Royal Match'。"""
    parts = topic.split("/")
    name = parts[-1] if parts else topic
    return name.replace("-", " ").title()
```

---

## 条目查找

```python
# app/rag/entry/entry_lookup.py
from app.common.constants import constants

def lookup_or_trigger_compile(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
) -> "WikiPage | None":
    """查找与查询最匹配的 Wiki 页面，若不存在则触发编译。"""
    wiki_repo = WikiPageRepository(rt.db_engine)

    # 先尝试精确主题匹配
    page = wiki_repo.find_by_topic(query, workspace_id)
    if page:
        return page

    # 在 Elasticsearch 中全文搜索 Wiki 页面
    try:
        resp = rt.es.search(
            index=constants.ES_INDEX_WIKI,
            body={
                "query": {
                    "bool": {
                        "must": {"multi_match": {
                            "query": query,
                            "fields": ["title^3", "content"],
                        }},
                        "filter": {"term": {"workspace_id": workspace_id}},
                    }
                },
                "size": 3,
            },
        )
    except Exception as e:
        raise Match3Exception.of("failed to es search wiki_pages").ctx(
            query=query, workspace_id=workspace_id,
        ).as_ex(e)

    hits = resp["hits"]["hits"]
    if hits:
        # 返回最匹配的页面
        best_id = hits[0]["_id"]
        return wiki_repo.find_by_id(best_id)

    return None
```
