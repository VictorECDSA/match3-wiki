# doc-navigate：PageIndex 长文档检索

本文件介绍 Q&A 服务的主入口结构，以及 doc-navigate 路径与 PageIndex 的集成。PageIndex 客户端及检索器的核心实现位于 `020-ingestion/pageindex.md`。

---

## 何时选择 doc-navigate

doc-navigate 适用于以下两种场景：

**场景 A**：用户明确引用了某个文档
```
用户："Q2 2025 移动游戏报告中关于三消留存率说了什么？"
```
路由器检测到文档引用 → 查找含 `pageindex_doc_id` 的匹配 RawFile → 使用 doc-navigate。

**场景 B**：用户在 API 请求中直接指定 `raw_file_id`
```json
{
  "query": "按收入排名前 10 的三消游戏有哪些？",
  "raw_file_id": "abc123"
}
```

---

## QAService 结构

**文件**：`app/services/qa_service.py`

### ask() 主入口

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

### _select_path() 路由逻辑

```
if raw_file_id:
    rf = raw_file_repo.find_by_id(raw_file_id)
    if rf.pageindex_doc_id → return (PAGE, None)

# Otherwise: ask AdaptiveRAGRouter
return AdaptiveRAGRouter(rt).route(query)   # → (RAGPath, complexity: str)
```

---

## _answer_path_page()

PageIndex 目录树导航路径：

```
# 1. Resolve document
rf = raw_file_repo.find_by_id(raw_file_id)         # if explicit
   or raw_file_repo.find_all_with_pageindex(ws)     # pick most-recently-updated

# 2. Navigate via PageIndex
page_contents = PageIndexRetriever(rt.pageindex, llm_caller).retrieve(
    rf.pageindex_doc_id, query, max_pages=5
)

# 3. Build context and stream
context = "\n\n---\n\n".join(f"[Pages from: {rf.filename}]\n{c}" for c in page_contents)
yield from _stream_llm(system_prompt, f"Document content:\n\n{context}\n\nQuestion: {query}")
```

`_find_best_pageindex_doc()`：多文档时按 `updated_at` 降序取第一个；精确多文档匹配逻辑可在此扩展。

---

## _answer_path_entry()

```
page = lookup_or_trigger_compile(rt, query, workspace_id)

if page is None:     yield "未找到该主题的 Wiki 条目，已加入编译队列。"; return
if COMPILING:        yield "该 Wiki 页面正在编译中，请稍后再试。";       return

yield from _stream_llm(system_prompt, f"Wiki page content:\n\n{page.content}\n\nQuestion: {query}")
```

---

## _answer_path_chunk()

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

complexity → Profile 映射关系见 `030-rag/hybrid-search.md` 第 13 节。

---

## LLM 辅助方法

| 方法 | 用途 |
|------|------|
| `_stream_llm(system_prompt, user_prompt)` | 流式输出 LLM token，供所有路径使用 |
| `_simple_llm_call(prompt) → str` | 非流式调用，供 PageIndexRetriever 目录树导航用 |
