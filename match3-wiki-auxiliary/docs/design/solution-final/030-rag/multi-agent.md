# 多智能体 RAG（方法 14）

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
# app/rag/chunk/multi_agent.py
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
    """多智能体 RAG 主入口，适用于需要多个知识域的复杂查询。

    执行步骤：
    1. 路由器将查询分解为子问题并分配域智能体
    2. 域智能体并行检索并回答子问题
    3. 验证器交叉核查智能体答案的一致性
    4. 写作器合成最终流式答案
    """

    # 第一步：路由器分解查询
    sub_questions = _route_query(rt, query)
    if not sub_questions:
        yield "无法将该查询分解为多智能体子问题。"
        return

    # 第二步：域智能体回答子问题（通过每域 hybrid_search 并行执行）
    agent_answers = []
    for sq in sub_questions:
        answer = _run_domain_agent(rt, workspace_id, sq["agent"], sq["question"])
        agent_answers.append({
            "agent": sq["agent"],
            "question": sq["question"],
            "answer": answer,
        })

    # 第三步：验证器交叉核查答案
    verified = _verify_answers(rt, query, agent_answers)

    # 第四步：写作器合成最终答案（流式）
    yield from _write_answer(rt, query, verified)


def _route_query(rt: Match3Runtime, query: str) -> list[dict]:
    """使用 LLM 将查询分解为子问题并分配域智能体。"""
    try:
        resp = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": ROUTER_PROMPT.format(query=query),
            }],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("failed to route multi-agent query").ctx(
            query=query,
        ).as_ex(e)

    try:
        data = json.loads(resp)
        return data.get("sub_questions", [])
    except (json.JSONDecodeError, KeyError) as e:
        raise Match3Exception.of("failed to parse multi-agent router response").ctx(
            query=query,
        ).as_ex(e)


def _run_domain_agent(
    rt: Match3Runtime,
    workspace_id: str,
    domain: str,
    question: str,
) -> str:
    """执行单个域智能体：先检索相关块，再回答子问题。

    域智能体按主题分类前缀过滤块：
    - entity    → 过滤标记为 entities/* 的块
    - market    → 过滤标记为 market/* 的块
    - mechanics → 过滤标记为 mechanics/* 的块
    - growth    → 过滤标记为 growth/* 的块
    """
    from app.rag.chunk.hybrid_search import hybrid_search

    # 检索块（混合搜索，可选按域标签过滤）
    try:
        chunks = hybrid_search(rt, question, workspace_id, top_k=20, domain_filter=domain)
    except Match3Exception as e:
        raise Match3Exception.of("domain agent hybrid search failed").ctx(
            domain=domain, question=question,
        ).as_ex(e)

    if not chunks:
        return f"No data found for: {question}"

    context = "\n\n".join(
        f"[Source {i+1}]: {c['content']}"
        for i, c in enumerate(chunks[:6])
    )

    try:
        resp = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": DOMAIN_SEARCH_PROMPT.format(
                    domain=domain,
                    question=question,
                    context=context,
                ),
            }],
        )
    except Exception as e:
        raise Match3Exception.of("domain agent llm call failed").ctx(
            domain=domain, question=question,
        ).as_ex(e)

    return resp


def _verify_answers(
    rt: Match3Runtime,
    query: str,
    agent_answers: list[dict],
) -> dict:
    """交叉核查各域智能体答案的一致性。"""
    answers_text = "\n\n".join(
        f"[{a['agent'].upper()} Agent] Q: {a['question']}\nA: {a['answer']}"
        for a in agent_answers
    )

    try:
        resp = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": VERIFIER_PROMPT.format(
                    query=query,
                    answers=answers_text,
                ),
            }],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("verifier agent llm call failed").ctx(
            query=query,
        ).as_ex(e)

    try:
        return json.loads(resp)
    except json.JSONDecodeError as e:
        raise Match3Exception.of("failed to parse verifier response").ctx(
            query=query,
        ).as_ex(e)


def _write_answer(
    rt: Match3Runtime,
    query: str,
    verified: dict,
) -> Generator[str, None, None]:
    """将验证后的智能体发现流式合成为最终答案。"""
    verified_answers_text = json.dumps(
        verified.get("verified_answers", []),
        indent=2,
    )
    consistency_summary = verified.get("summary", "")

    try:
        stream = rt.llm.stream(
            messages=[{
                "role": "user",
                "content": WRITER_PROMPT.format(
                    query=query,
                    verified_answers=verified_answers_text,
                    consistency_summary=consistency_summary,
                ),
            }],
        )
    except Exception as e:
        raise Match3Exception.of("writer agent stream failed").ctx(
            query=query,
        ).as_ex(e)

    yield from stream
```

---

## `hybrid_search` 中的域过滤

`hybrid_search()` 新增的 `domain_filter` 参数将块检索限制在特定主题分类下。该参数可选——若该域下没有已标记的块，过滤器将被忽略，退回到全局搜索。

```python
# app/rag/chunk/hybrid_search.py  (domain_filter extension)
from app.common.constants import constants

def hybrid_search(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 20,
    domain_filter: str | None = None,   # "entity", "market", "mechanics", "growth"
) -> list[dict]:
    """混合搜索：Milvus ANN + Elasticsearch BM25，使用 RRF 合并结果。
    可选 domain_filter 将搜索限制在带有该域前缀标签的块中。
    """
    embedding = _embed_query(rt, query)

    # Milvus ANN 搜索
    milvus_filter = f'workspace_id == "{workspace_id}"'
    if domain_filter:
        milvus_filter += f' && domain == "{domain_filter}"'

    try:
        milvus_results = rt.milvus.search(
            collection_name=constants.MILVUS_COLLECTION,
            data=[embedding],
            anns_field="dense_vector",
            param={"metric_type": "COSINE", "params": {"ef": 200}},
            limit=top_k,
            expr=milvus_filter,
            output_fields=["chunk_id", "content", "raw_file_id", "domain"],
        )
    except Exception as e:
        raise Match3Exception.of("milvus search failed in domain agent").ctx(
            workspace_id=workspace_id, domain=domain_filter,
        ).as_ex(e)

    # Elasticsearch BM25 搜索
    es_filter_clauses = [{"term": {"workspace_id": workspace_id}}]
    if domain_filter:
        es_filter_clauses.append({"prefix": {"topic_tags": domain_filter + "/"}})

    try:
        es_resp = rt.es.search(
            index=constants.ES_INDEX_CHUNKS,
            body={
                "query": {
                    "bool": {
                        "must": {"match": {"content": query}},
                        "filter": es_filter_clauses,
                    }
                },
                "size": top_k,
            },
        )
    except Exception as e:
        raise Match3Exception.of("es search failed in domain agent").ctx(
            workspace_id=workspace_id, domain=domain_filter,
        ).as_ex(e)

    return _rrf_merge(milvus_results, es_resp["hits"]["hits"], top_k)
```

---

## 使用 Celery chord 并行执行（可选）

为获得最大吞吐量，域智能体可以通过 `chord` 以并行 Celery 子任务的方式运行。上方的同步版本为简化起见顺序执行；下方的并行版本使用 Celery chord 并发运行各域智能体。

```python
# app/workers/multi_agent_task.py（可选并行执行版本）
from celery import chord, group
from app.common.constants import constants


@celery_app.task(
    bind=True,
    name="app.workers.tasks.rag_task.domain_agent_task",
    queue=constants.QUEUE_RAG,
    max_retries=2,
    time_limit=60,
    soft_time_limit=50,
)
def domain_agent_task(self, domain: str, question: str, workspace_id: str) -> dict:
    """并行 chord 中的单个域智能体任务。"""
    rt = get_worker_runtime()
    from app.rag.chunk.multi_agent import _run_domain_agent
    answer = _run_domain_agent(rt, workspace_id, domain, question)
    return {"agent": domain, "question": question, "answer": answer}


@celery_app.task(
    bind=True,
    name="app.workers.tasks.rag_task.multi_agent_verify_task",
    queue=constants.QUEUE_RAG,
    max_retries=1,
    time_limit=120,
    soft_time_limit=110,
)
def multi_agent_verify_task(self, agent_answers: list[dict], query: str, workspace_id: str) -> str:
    """所有域智能体完成后执行验证器 + 写作器（chord 回调）。"""
    rt = get_worker_runtime()
    from app.rag.chunk.multi_agent import _verify_answers, _write_answer

    verified = _verify_answers(rt, query, agent_answers)
    # 后台任务使用非流式版本
    answer_parts = list(_write_answer(rt, query, verified))
    return "".join(answer_parts)


def run_multi_agent_parallel(rt, query: str, workspace_id: str, sub_questions: list[dict]) -> str:
    """使用 Celery chord 并行运行域智能体。

    阻塞直到所有智能体完成，然后运行验证器和写作器。
    适用于后台/异步调用场景（如异步 Wiki 编译）。
    流式 Q&A 请使用 multi_agent_rag() 中的顺序版本。
    """
    agent_tasks = group(
        domain_agent_task.s(sq["agent"], sq["question"], workspace_id)
        for sq in sub_questions
    )
    callback = multi_agent_verify_task.s(query=query, workspace_id=workspace_id)
    result = chord(agent_tasks)(callback)
    return result.get(timeout=120)
```

---

## 与 QAService 的集成

在 `QAService._answer_path_chunk()` 中，`multi_agent` 方法通过以下方式分发：

```python
ChunkMethod.MULTI_AGENT: lambda: list(multi_agent_rag(rt, query, workspace_id)),
```

由于 `multi_agent_rag()` 本身是一个生成器，lambda 对其进行包装，使 `_answer_path_chunk()` 能与其他所有方法统一迭代。
