# PageIndex：长文档目录树检索（doc-navigate 检索路径）

## 什么是 PageIndex

PageIndex（VectifyAI 出品，Apache-2.0 协议）是一个长文档检索系统，通过**层级目录树**导航文档内容。工作原理如下：

1. 将 PDF 上传至 PageIndex API
2. API 解析 PDF，构建层级目录树（章节 → 节 → 小节）
3. 查询时，LLM 通过选择相关分支来导航目录树
4. 系统检索所选叶子页面的实际页面内容
5. 检索到的页面内容作为最终答案的上下文

适用场景：
- 市场调研报告（40–200 页）
- 游戏设计文档
- 技术规格说明
- 任何内容结构清晰、可导航的 PDF

---

## PageIndex 与普通分块的关系

PageIndex 是**叠加路径**，不是替代路径。

对于 ≥20 页的 PDF，导入流水线做两件事：

1. **正常分块流水线**（所有 PDF 均执行）：markitdown 解析 → 语义分块 → embed_task（写入 Milvus + Elasticsearch）→ graph_task（写入 Neo4j）
2. **PageIndex 建树**（≥20 页 PDF 额外执行）：`_register_pageindex()` 将 PDF 上传至 PageIndex API，获取 `doc_id` 和目录树，存入 `raw_files.pageindex_doc_id / pageindex_tree`

两条路径同时进行，互不影响。查询时，`hybrid-search` 使用 Milvus/ES，`doc-navigate` 使用 PageIndex 目录树导航。同一份大 PDF 的内容可通过任意路径被检索。

---

## PageIndex API 使用

```python
# app/rag/page/pageindex_retriever.py
from __future__ import annotations
from pageindex import PageIndexClient
from app.common.exceptions import Match3Exception
from app.common.constants import codes


class PageIndexRetriever:
    """Retrieve relevant pages from a long PDF using PageIndex TOC-tree navigation (doc-navigate retrieval path)."""

    def __init__(self, client: PageIndexClient, llm_caller):
        # PageIndexClient is injected directly — it is NOT on Match3Runtime.
        # Callers instantiate it from app.intelligence.pageindex and pass it in.
        self._client = client
        self._llm = llm_caller  # callable(prompt: str) -> str

    def upload_document(self, pdf_path: str) -> str:
        """Upload PDF to PageIndex; returns doc_id."""
        try:
            doc_id = self._client.add(pdf_path)
        except Exception as e:
            raise Match3Exception.of("failed to pageindex_client.add").ctx(
                pdf_path=pdf_path,
            ).as_ex(e)
        return doc_id

    def get_tree(self, doc_id: str) -> dict:
        """Return the hierarchical table-of-contents tree for a document."""
        try:
            tree = self._client.get_tree(doc_id)
        except Exception as e:
            raise Match3Exception.of("failed to pageindex_client.get_tree").ctx(
                doc_id=doc_id,
            ).as_ex(e)
        return tree

    def retrieve(self, doc_id: str, query: str, max_pages: int = 5) -> list[str]:
        """Navigate the TOC tree to find relevant pages; return list of page content strings."""
        tree = self.get_tree(doc_id)
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

## 目录树结构示例

市场调研 PDF "Mobile Gaming Report 2025.pdf"（82 页）会生成如下目录树：

```json
{
  "title": "Mobile Gaming Report 2025",
  "page_range": [1, 82],
  "children": [
    {
      "title": "Executive Summary",
      "page_range": [1, 4],
      "children": []
    },
    {
      "title": "Chapter 1: Market Overview",
      "page_range": [5, 20],
      "children": [
        {
          "title": "1.1 Global Revenue by Genre",
          "page_range": [5, 9],
          "children": []
        },
        {
          "title": "1.2 Match-3 Segment Analysis",
          "page_range": [10, 16],
          "children": []
        }
      ]
    },
    {
      "title": "Chapter 2: Top Publishers",
      "page_range": [21, 45],
      "children": [...]
    }
  ]
}
```

对于查询"2025 年三消品类的收入分布是什么？"，LLM 的导航过程如下：
1. 根节点 → "Chapter 1: Market Overview"（最相关）
2. 第一章 → "1.2 Match-3 Segment Analysis"（最相关）
3. 检索第 10–12 页（叶子节点页面）

---

## 存储：PostgreSQL 中的 PageIndex 元数据

`raw_files` 表存储 PageIndex 元数据：

```sql
-- additional columns on the raw_files table (see 050-database/schema.md for full schema)
pageindex_doc_id    VARCHAR(255)   NULL,  -- doc_id returned by client.add()
pageindex_tree      JSONB          NULL,  -- full TOC tree structure
page_count          INTEGER        NULL,  -- total page count of the PDF
```

这些字段由 `ingest_task` Worker 在调用 `client.add()` 和 `client.get_tree()` 后写入。
