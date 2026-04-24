# 检索路径：doc-navigate

PageIndex 客户端及检索器的核心实现位于 `020-ingestion/pageindex.md`。

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

## QAService：_answer_path_page()

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

## LLM 辅助方法

| 方法 | 用途 |
|------|------|
| `_stream_llm(system_prompt, user_prompt)` | 流式输出 LLM token，供所有路径使用 |
| `_simple_llm_call(prompt) → str` | 非流式调用，供 PageIndexRetriever 目录树导航用 |
