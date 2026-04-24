# 检索路径：doc-navigate

`doc-navigate` 使用 PageIndex 目录树导航从长 PDF 中检索相关页面。`PageIndexRetriever` 的实现位于 `app/rag/page/pageindex_retriever.py`。

---

## 何时选择 doc-navigate

doc-navigate 适用于以下两种场景：

**场景 A**：用户明确引用了某个文档
```
User: "What does the Q2 2025 mobile gaming report say about match-3 retention rates?"
```
路由器检测到文档引用 → 查找含 `pageindex_doc_id` 的匹配 RawFile → 使用 doc-navigate。

**场景 B**：用户在 API 请求中直接指定 `raw_file_id`
```json
{
  "query": "Top 10 match-3 games ranked by revenue?",
  "raw_file_id": "abc123"
}
```

---

## PageIndexRetriever

```python
# app/rag/page/pageindex_retriever.py
from __future__ import annotations
from pageindex import PageIndexClient
from app.common.exceptions import Match3Exception


class PageIndexRetriever:
    """Retrieve relevant pages from a long PDF by navigating its TOC tree (doc-navigate path)."""

    def __init__(self, client: PageIndexClient, llm_caller):
        # PageIndexClient is injected directly — it is NOT on Match3Runtime.
        # Callers instantiate it from app.intelligence.pageindex and pass it in.
        self._client = client
        self._llm = llm_caller  # callable(prompt: str) -> str

    def retrieve(self, doc_id: str, query: str, max_pages: int = 5) -> list[str]:
        """Navigate the TOC tree to find relevant pages; return list of page content strings."""
        tree = self._get_tree(doc_id)
        relevant_page_nums = self._navigate_tree(tree, query, max_pages)

        page_contents = []
        for page_num in relevant_page_nums:
            try:
                content = self._client.get_page_content(doc_id, pages=[page_num])
            except Exception as e:
                raise Match3Exception.of("failed to pageindex_client.get_page_content").ctx(
                    doc_id=doc_id,
                    page_num=page_num,
                ).as_ex(e)
            page_contents.append(content)

        return page_contents

    def _get_tree(self, doc_id: str) -> dict:
        try:
            return self._client.get_tree(doc_id)
        except Exception as e:
            raise Match3Exception.of("failed to pageindex_client.get_tree").ctx(
                doc_id=doc_id,
            ).as_ex(e)

    def _navigate_tree(self, tree: dict, query: str, max_pages: int) -> list[int]:
        """Use LLM to navigate the TOC tree and identify relevant pages."""
        all_relevant = []
        self._navigate_node(tree, query, all_relevant, max_pages)
        return all_relevant[:max_pages]

    def _navigate_node(
        self,
        node: dict,
        query: str,
        result: list[int],
        max_pages: int,
        depth: int = 0,
    ) -> None:
        """Recursively navigate a TOC node, selecting relevant children."""
        if len(result) >= max_pages:
            return

        children = node.get("children", [])
        if not children:
            # leaf node — add its page range to results
            page_range = node.get("page_range", [])
            if page_range:
                start, end = page_range[0], page_range[1]
                result.extend(range(start, min(end + 1, start + 3)))  # at most 3 pages per leaf
            return

        # ask LLM which children are relevant to the query
        child_summaries = "\n".join(
            f"{i+1}. [{c.get('title', 'Untitled')}] pages {c.get('page_range', '?')}"
            for i, c in enumerate(children)
        )
        prompt = f"""You are navigating a document table of contents to answer: "{query}"

Which of these sections are relevant? Reply with comma-separated numbers only (e.g. "1,3").
If none are relevant, reply "none".

Sections:
{child_summaries}"""

        response = self._llm(prompt).strip()

        if response.lower() == "none":
            return

        selected_indices = []
        for part in response.split(","):
            try:
                idx = int(part.strip()) - 1
                if 0 <= idx < len(children):
                    selected_indices.append(idx)
            except ValueError:
                pass

        for idx in selected_indices:
            if len(result) >= max_pages:
                break
            self._navigate_node(children[idx], query, result, max_pages, depth + 1)
```

---

## QAService：_answer_path_page()

```python
# app/services/qa_service.py  (doc-navigate path)
from app.intelligence.pageindex import VectifyPageIndexClient
from app.intelligence.llm import OpenAILLMCaller
from app.rag.page.pageindex_retriever import PageIndexRetriever


def _answer_path_page(
    self,
    query: str,
    raw_file_id: str | None,
) -> Generator[str, None, None]:
    """Answer a query against a specific long PDF using PageIndex tree navigation."""
    raw_file_repo = RawFileRepository(self._rt.db)

    # resolve document
    if raw_file_id:
        rf = raw_file_repo.find_by_id(raw_file_id)
    else:
        rf = self._find_best_pageindex_doc(raw_file_repo)

    if rf is None or not rf.pageindex_doc_id:
        yield "No PageIndex document found for this query."
        return

    # instantiate intelligence-layer clients (not on Match3Runtime)
    pageindex_client = VectifyPageIndexClient(api_key=self._rt.env.PAGEINDEX_API_KEY)
    llm = OpenAILLMCaller(
        api_key=self._rt.env.OPENAI_API_KEY,
        model=self._rt.config.llm.default_model,
    )

    def _simple_llm_call(prompt: str) -> str:
        """Non-streaming LLM call used for TOC tree navigation."""
        try:
            return llm.complete(messages=[{"role": "user", "content": prompt}])
        except Exception as e:
            raise Match3Exception.of("failed to llm.complete for tree navigation").ctx(
                prompt_len=len(prompt),
            ).as_ex(e)

    retriever = PageIndexRetriever(client=pageindex_client, llm_caller=_simple_llm_call)

    # navigate TOC tree and fetch relevant pages
    try:
        page_contents = retriever.retrieve(rf.pageindex_doc_id, query, max_pages=5)
    except Match3Exception as e:
        raise Match3Exception.of("failed to pageindex_retriever.retrieve").ctx(
            query=query,
            doc_id=rf.pageindex_doc_id,
        ).as_ex(e)

    if not page_contents:
        yield "No relevant pages found in this document for your query."
        return

    context = "\n\n---\n\n".join(
        f"[Pages from: {rf.filename}]\n{c}" for c in page_contents
    )
    system_prompt = (
        "You are a research assistant for a match-3 game knowledge base. "
        "Answer questions based strictly on the provided document pages. "
        "If the answer is not in the pages, say so explicitly."
    )
    yield from self._stream_llm(system_prompt, f"Document content:\n\n{context}\n\nQuestion: {query}")


def _find_best_pageindex_doc(self, raw_file_repo: RawFileRepository) -> RawFile | None:
    """Return the most-recently-updated RawFile that has a pageindex_doc_id."""
    docs = raw_file_repo.find_all_with_pageindex(self._workspace_id)
    if not docs:
        return None
    return sorted(docs, key=lambda r: r.updated_at, reverse=True)[0]
```
