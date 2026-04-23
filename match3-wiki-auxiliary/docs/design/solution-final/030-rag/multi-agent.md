# 多智能体 RAG

## 架构

多智能体 RAG 将复杂查询分解为并行工作流，每条流由一个专域智能体负责处理。路由器分发子问题，各智能体独立检索，验证器交叉核查一致性，最终由写作器合成答案。

```
用户查询
    │
    ▼
┌──────────────────┐
│  Router Agent    │  将查询分解为 N 个子问题
│                  │  将每个子问题分配给对应域智能体
└────────┬─────────┘
         │  子问题
    ┌────▼──────────────────────────────────────────────────┐
    │  并行域智能体（Celery chord）                          │
    │                                                       │
    │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
    │  │ EntityAgent  │  │ MarketAgent  │  │ MechAgent  │  │
    │  │ entities/    │  │ market/      │  │ mechanics/ │  │
    │  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
    └─────────┼─────────────────┼─────────────────┼────────-┘
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │  各域局部答案
                    ┌───────────▼──────────┐
                    │  Verifier Agent      │  检查事实一致性
                    │                      │  标记矛盾之处
                    └───────────┬──────────┘
                                │  已验证答案
                    ┌───────────▼──────────┐
                    │  Writer Agent        │  合成最终答案
                    │                      │  流式输出给用户
                    └──────────────────────┘
```

---

## 实现

```python
# app/rag/multi_agent.py
from __future__ import annotations
import json
from typing import Generator
from app.runtime import Match3Runtime
from app.common.exceptions import Match3Exception


ROUTER_PROMPT = """You are decomposing a complex research question into sub-questions
for specialized agents in a match-3 game knowledge base.

Available agent domains:
- entity: Game titles, publishers, developer info (e.g. Royal Match, King, Playrix)
- market: Market data, revenue stats, download figures, regional breakdowns
- mechanics: Game mechanics, features, monetization patterns, UA strategies
- growth: Creative formats, ad hooks, performance marketing data

Query: {query}

Decompose into 2-4 focused sub-questions. Assign each to the best domain agent.
Return JSON only:
{{
  "sub_questions": [
    {{"agent": "entity|market|mechanics|growth", "question": "...", "focus": "one sentence why this agent"}},
    ...
  ]
}}"""


DOMAIN_SEARCH_PROMPT = """You are a specialized research agent for the {domain} domain
in a match-3 game knowledge base.

Your sub-question: {question}

Retrieved context:
{context}

Answer the sub-question concisely based only on the provided context.
If the context does not contain the answer, state: "No data found for: {question}"
Be specific — include numbers, names, dates when available."""


VERIFIER_PROMPT = """You are a fact-checker reviewing answers from multiple research agents
about match-3 games.

Original query: {query}

Agent answers:
{answers}

Check for:
1. Factual contradictions between answers
2. Missing critical information
3. Redundancy

Output a JSON object:
{{
  "is_consistent": true|false,
  "contradictions": ["..."] or [],
  "summary": "brief assessment",
  "verified_answers": [
    {{"agent": "...", "question": "...", "answer": "...", "confidence": "high|medium|low"}}
  ]
}}"""


WRITER_PROMPT = """You are a research writer synthesizing findings from multiple specialized
agents about match-3 games.

Original user query: {query}

Verified findings:
{verified_answers}

Consistency assessment: {consistency_summary}

Write a comprehensive, well-structured answer. Use markdown formatting.
Cite specific agents when presenting their findings (e.g., "(Market data)").
If data is conflicting, present both versions and note the discrepancy.
Length: 300-600 words."""


def multi_agent_rag(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
) -> Generator[str, None, None]:
    # Step 1: router decomposes query
    sub_questions = _route_query(rt, query)
    if not sub_questions:
        yield "Unable to decompose query for multi-agent processing."
        return

    # Step 2: domain agents answer sub-questions (sequential; see Celery chord section for parallel)
    agent_answers = []
    for sq in sub_questions:
        answer = _run_domain_agent(rt, workspace_id, sq["agent"], sq["question"])
        agent_answers.append({
            "agent": sq["agent"],
            "question": sq["question"],
            "answer": answer,
        })

    # Step 3: verifier cross-checks answers
    verified = _verify_answers(rt, query, agent_answers)

    # Step 4: writer synthesizes final answer (streaming)
    yield from _write_answer(rt, query, verified)


def _route_query(rt: Match3Runtime, query: str) -> list[dict]:
    try:
        resp = rt.llm.complete(
            messages=[{"role": "user", "content": ROUTER_PROMPT.format(query=query)}],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("failed to route multi-agent query").ctx(query=query).as_ex(e)

    try:
        return json.loads(resp).get("sub_questions", [])
    except (json.JSONDecodeError, KeyError) as e:
        raise Match3Exception.of("failed to parse multi-agent router response").ctx(query=query).as_ex(e)


def _run_domain_agent(rt: Match3Runtime, workspace_id: str, domain: str, question: str) -> str:
    """Run a single domain agent: retrieve with domain filter, then answer sub-question.

    Domain → topic_tags prefix mapping:
      entity    → entities/*
      market    → market/*
      mechanics → mechanics/*
      growth    → growth/*
    """
    from app.rag.hybrid_search_engine import HybridSearchEngine
    from app.rag.retrieval_config import RetrievalConfig, RerankLevel
    import asyncio

    cfg = RetrievalConfig(
        dense=True, sparse=True, bm25=True,
        rerank=RerankLevel.LIGHTWEIGHT,
        final_top_k=6,
        domain_filter=domain,   # passed through to Milvus/ES filter
    )

    try:
        chunks = asyncio.run(HybridSearchEngine(rt).search(question, workspace_id, cfg))
    except Match3Exception as e:
        raise Match3Exception.of("domain agent search failed").ctx(
            domain=domain, question=question,
        ).as_ex(e)

    if not chunks:
        return f"No data found for: {question}"

    context = "\n\n".join(f"[Source {i+1}]: {c['content']}" for i, c in enumerate(chunks))

    try:
        return rt.llm.complete(
            messages=[{"role": "user", "content": DOMAIN_SEARCH_PROMPT.format(
                domain=domain, question=question, context=context,
            )}],
        )
    except Exception as e:
        raise Match3Exception.of("domain agent llm call failed").ctx(
            domain=domain, question=question,
        ).as_ex(e)


def _verify_answers(rt: Match3Runtime, query: str, agent_answers: list[dict]) -> dict:
    answers_text = "\n\n".join(
        f"[{a['agent'].upper()} Agent] Q: {a['question']}\nA: {a['answer']}"
        for a in agent_answers
    )
    try:
        resp = rt.llm.complete(
            messages=[{"role": "user", "content": VERIFIER_PROMPT.format(
                query=query, answers=answers_text,
            )}],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("verifier agent llm call failed").ctx(query=query).as_ex(e)

    try:
        return json.loads(resp)
    except json.JSONDecodeError as e:
        raise Match3Exception.of("failed to parse verifier response").ctx(query=query).as_ex(e)


def _write_answer(rt: Match3Runtime, query: str, verified: dict) -> Generator[str, None, None]:
    verified_answers_text = json.dumps(verified.get("verified_answers", []), indent=2)
    consistency_summary = verified.get("summary", "")
    try:
        stream = rt.llm.stream(
            messages=[{"role": "user", "content": WRITER_PROMPT.format(
                query=query,
                verified_answers=verified_answers_text,
                consistency_summary=consistency_summary,
            )}],
        )
    except Exception as e:
        raise Match3Exception.of("writer agent stream failed").ctx(query=query).as_ex(e)
    yield from stream
```

---

## 域过滤：`domain_filter` 在 RetrievalConfig 中的传递

`RetrievalConfig.domain_filter` 将检索限定在特定主题分类的块中。该参数可选——若该域下无已标记块，过滤器将被忽略，退回全局搜索。

| domain_filter 值 | Milvus 过滤条件 | ES 过滤条件 |
|-----------------|----------------|------------|
| `"entity"` | `topic_tags contains "entities/"` | `prefix: {topic_tags: "entities/"}` |
| `"market"` | `topic_tags contains "market/"` | `prefix: {topic_tags: "market/"}` |
| `"mechanics"` | `topic_tags contains "mechanics/"` | `prefix: {topic_tags: "mechanics/"}` |
| `"growth"` | `topic_tags contains "growth/"` | `prefix: {topic_tags: "growth/"}` |
| `None` | 不过滤 | 不过滤 |

`domain_filter` 在 `HybridSearchEngine` 内部传入 `dense_search()` 和 `bm25_search()` 的过滤表达式。Graph 通道不适用域过滤（图谱遍历已由锚点实体约束）。

---

## 使用 Celery chord 并行执行（可选）

为获得最大吞吐量，域智能体可通过 `chord` 以并行 Celery 子任务方式运行。上方的同步版本顺序执行，适合 SSE 流式 Q&A；下方的并行版本使用 Celery chord 并发运行各域智能体，适合后台/异步场景。

```python
# app/workers/tasks/multi_agent_task.py
from celery import chord, group
from app.common.constants import constants


@celery_app.task(
    bind=True,
    name="app.workers.tasks.multi_agent_task.domain_agent_task",
    queue=constants.QUEUE_RAG,
    max_retries=2,
    time_limit=60,
    soft_time_limit=50,
)
def domain_agent_task(self, domain: str, question: str, workspace_id: str) -> dict:
    rt = get_worker_runtime()
    from app.rag.multi_agent import _run_domain_agent
    answer = _run_domain_agent(rt, workspace_id, domain, question)
    return {"agent": domain, "question": question, "answer": answer}


@celery_app.task(
    bind=True,
    name="app.workers.tasks.multi_agent_task.multi_agent_verify_task",
    queue=constants.QUEUE_RAG,
    max_retries=1,
    time_limit=120,
    soft_time_limit=110,
)
def multi_agent_verify_task(self, agent_answers: list[dict], query: str, workspace_id: str) -> str:
    rt = get_worker_runtime()
    from app.rag.multi_agent import _verify_answers, _write_answer

    verified = _verify_answers(rt, query, agent_answers)
    return "".join(_write_answer(rt, query, verified))   # non-streaming for background task


def run_multi_agent_parallel(rt, query: str, workspace_id: str, sub_questions: list[dict]) -> str:
    """Run domain agents in parallel via Celery chord.

    Blocks until all agents complete, then runs verifier + writer.
    For streaming Q&A, use the sequential multi_agent_rag() instead.
    """
    agent_tasks = group(
        domain_agent_task.s(sq["agent"], sq["question"], workspace_id)
        for sq in sub_questions
    )
    callback = multi_agent_verify_task.s(query=query, workspace_id=workspace_id)
    return chord(agent_tasks)(callback).get(timeout=120)
```

---

## 与 QAService 的集成

`_answer_path_chunk()` 通过 `complexity="complex"` 映射到 `PROFILE_COMPLEX`，不直接调用多智能体路径。多智能体 RAG 作为 `PROFILE_COMPLEX` 的可选扩展：当路由器返回 `complexity="complex"` 且查询明确涉及多个知识域时，`_answer_path_chunk()` 可选择调用 `multi_agent_rag()`，否则直接走 `HybridSearchEngine` 的 graph 通道。

```
complexity == "complex"
    │
    ├── 单域查询 ──► HybridSearchEngine(PROFILE_COMPLEX)  [graph=True]
    └── 多域查询 ──► multi_agent_rag()                    [每个域独立检索]
```
