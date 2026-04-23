# 检索路由器

## RAGPath 枚举

```python
# app/rag/router.py
class RAGPath(str, Enum):
    CHUNK = "chunk"     # hybrid-search：分块语料库混合检索
    ENTRY = "entry"     # wiki-lookup：已编译 Wiki 条目查找
    PAGE  = "page"      # doc-navigate：PageIndex 长文档导航
```

---

## 路径选择逻辑

```
查询到达 QAService.ask()
         │
         ▼
[1] 请求中是否明确指定了 raw_file_id？
    ├─ 是 + 文件为 PageIndex 文档 ──────────────────────────► doc-navigate
    └─ 否 ─────────────────────────────────────────────────►[2]

[2] AdaptiveRAGRouter.route(query) → (path, complexity)
    ├─ path == "entry" ──────────────────────────────────────► wiki-lookup
    ├─ path == "page"  ──────────────────────────────────────► doc-navigate（查找最匹配的文档）
    └─ path == "chunk" ──────────────────────────────────────►[3]

[3] complexity → RetrievalConfig Profile（hybrid-search）
    ├─ "simple"      → PROFILE_SIMPLE      (Dense+Sparse+BM25, lightweight rerank)
    ├─ "moderate"    → PROFILE_MODERATE    (+ multi_query, cross_encoder rerank)
    ├─ "complex"     → PROFILE_COMPLEX     (+ HyDE + Graph, cross_encoder rerank)
    ├─ "analytical"  → PROFILE_ANALYTICAL  (SQL only)
    └─ "uncertain"   → PROFILE_UNCERTAIN   (+ CRAG + web fallback)
```

---

## AdaptiveRAGRouter

```python
# app/rag/router.py

ROUTER_PROMPT = """You are routing a user query to the correct knowledge retrieval path.

Paths:
- chunk: General factual Q&A, comparisons, research questions. Uses hybrid-search.
- entry: Requesting a specific wiki page, topic summary, or knowledge article.
- page: Navigating a specific long document (report, PDF, design doc). User references a document.

Complexity levels (for chunk path only — determines retrieval profile):
- simple:     Single-hop fact lookup ("What is X?")
- moderate:   Multi-hop, comparisons ("Compare X and Y")
- complex:    Deep analysis, graph relationships, multi-entity
- analytical: Structured data query (revenue numbers, download stats) → SQL
- uncertain:  May need web search fallback

Query: {query}

Reply with JSON only:
{{"path": "chunk|entry|page", "complexity": "simple|moderate|complex|analytical|uncertain"}}
"""


class AdaptiveRAGRouter:
    """Routes queries to hybrid-search (chunk), wiki-lookup (entry), or doc-navigate (page)."""

    def __init__(self, rt: Match3Runtime):
        self._rt = rt

    def route(self, query: str) -> tuple[RAGPath, str]:
        """Classify query, return (path, complexity) tuple."""
        try:
            content = self._rt.llm.complete(
                messages=[{"role": "user", "content": ROUTER_PROMPT.format(query=query)}],
                model=self._rt.config.llm.default_model,
                response_format={"type": "json_object"},
                max_tokens=100, temperature=0,
            )
        except Exception as e:
            raise Match3Exception.of("failed to route query").ctx(query=query).as_ex(e)

        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            raise Match3Exception.of("failed to parse router response").ctx(query=query).as_ex(e)

        path = RAGPath(result.get("path", "chunk"))
        complexity = result.get("complexity", "simple")
        return path, complexity
```

---

## QAService 主入口（ask）

**文件**：`app/services/qa_service.py`

```
path, complexity = _select_path(query, raw_file_id, workspace_id)
session = qa_repo.insert(QASession(status=GENERATING, rag_path=path, ...))

gen = {
    RAGPath.PAGE:  _answer_path_page(query, raw_file_id, workspace_id),
    RAGPath.ENTRY: _answer_path_entry(query, workspace_id),
    RAGPath.CHUNK: _answer_path_chunk(query, workspace_id, complexity),
}[path]

for token in gen:
    yield token                          # SSE streaming

qa_repo.update(session  # answer="".join(parts), status=DONE)
```

### _select_path() 实现

```
if raw_file_id:
    rf = raw_file_repo.find_by_id(raw_file_id)
    if rf.pageindex_doc_id → return (PAGE, None)

# Otherwise: ask AdaptiveRAGRouter
return AdaptiveRAGRouter(rt).route(query)   # → (RAGPath, complexity: str)
```

### _answer_path_chunk()

`complexity` 字符串通过 `PROFILE_MAP` 映射到 `RetrievalConfig`，由 `HybridSearchEngine` 执行五阶段检索：

```python
from app.rag.retrieval_profiles import PROFILE_MAP
from app.rag.hybrid_search_engine import HybridSearchEngine

async def _answer_path_chunk(query, workspace_id, complexity):
    cfg = PROFILE_MAP.get(complexity, PROFILE_MAP["simple"])
    chunks = await HybridSearchEngine(rt).search(query, workspace_id, cfg)

    context = "\n\n".join(f"[Source {i+1}]: {c['content']}" for i, c in enumerate(chunks))
    yield from _stream_llm(system_prompt, f"Retrieved context:\n\n{context}\n\nQuestion: {query}")
```

complexity → Profile 映射关系详见 `030-rag/retrieval/hybrid-search.md` 第 6 节。

---

## 复杂查询的多智能体扩展

当 `complexity == "complex"` 且查询涉及多个知识域时，`_answer_path_chunk()` 可选择调用 `multi_agent_rag()`：

```
complexity == "complex"
    │
    ├── 单域查询 ──► HybridSearchEngine(PROFILE_COMPLEX)  [graph=True]
    └── 多域查询 ──► multi_agent_rag()                    [每个域独立检索]
```

多智能体 RAG 详见 `030-rag/retrieval/multi-agent.md`。

---

## 提示缓存（CAG）策略

对于 wiki-lookup 或带已知上下文的 hybrid-search，使用 Anthropic `cache_control` 缓存静态部分：

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": wiki_page_content,
             "cache_control": {"type": "ephemeral"}},   # static part, cached by LLM provider
            {"type": "text", "text": f"Question: {query}"},  # dynamic part, not cached
        ],
    }
]
```

| 静态部分（缓存） | 动态部分（不缓存） |
|----------------|-----------------|
| 系统提示 + 角色 + 指令 | 检索到的块（每次查询都会变化） |
| 完整 Wiki 页面（wiki-lookup）| 用户查询 |
| 工具定义（agentic 场景） | — |

---

## complexity 选择启发式

| 查询类型 | complexity |
|----------|-----------|
| "X 是什么？" | `simple` |
| "比较 X 和 Y" | `moderate` |
| "与 X 有关联的游戏有哪些？" | `complex` |
| "前 10 名游戏的收入" | `analytical` |
| "Y 领域的最新趋势是什么？" | `uncertain` |
| "告诉我关于 X 的一切" | `complex`（可扩展为 multi-agent） |
