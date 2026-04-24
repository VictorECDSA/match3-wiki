# 检索路径：wiki-lookup

## 条目查找

**文件**：`app/rag/entry_lookup.py`

```
lookup_or_trigger_compile(rt, query, workspace_id) → WikiPage | None

1. wiki_repo.find_by_topic(query, workspace_id)  → exact match
2. es.search(ES_INDEX_WIKI, multi_match on title^3 + content, filter workspace_id, size=3)
   → return wiki_repo.find_by_id(hits[0]["_id"])
3. return None  (caller triggers compile)
```

---

## QAService：_answer_path_entry()

```
page = lookup_or_trigger_compile(rt, query, workspace_id)

if page is None:     yield "No Wiki entry found for this topic; compilation queued.";  return
if COMPILING:        yield "This Wiki page is being compiled, please try again later."; return

yield from _stream_llm(system_prompt, f"Wiki page content:\n\n{page.content}\n\nQuestion: {query}")
```

---

## 与编译流水线的关系

wiki-lookup 是纯查询侧逻辑——只负责找到已编译的 Wiki 页面并返回。若页面不存在或已过期，则触发异步编译任务后立即返回提示。

编译流水线（OpenKB 五步）的完整实现见 `030-rag/processing/wiki-compile.md`。
