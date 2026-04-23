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

## 何时使用 doc-navigate 检索路径

QA 路由器在以下情况将问题分类为 `doc-navigate`：
- 查询明确针对某个已知特定文档（用户指定了文档名 / 标题）
- 查询需要深入导航某个结构化长文档（"第三章讲了什么"、"找出关于 X 的全部章节"）
- AdaptiveRAG 路由器将查询分类为 `LONG_DOC_LOOKUP`

---

## PageIndex API 使用

```python
# app/rag/page/pageindex_retriever.py
from __future__ import annotations
from pageindex import PageIndexClient
from app.common.exceptions import Match3Exception
from app.common.constants import codes


class PageIndexRetriever:
    """使用 PageIndex 目录树导航从长 PDF 中检索相关页面（doc-navigate 检索路径）。"""

    def __init__(self, client: PageIndexClient, llm_caller):
        # 直接接收 PageIndexClient — rt.pageindex 是 Match3Runtime 上的 Protocol 对象
        # 禁止在此处构造 PageIndexClient，始终从外部注入
        self._client = client
        self._llm = llm_caller  # callable(prompt: str) -> str

    def upload_document(self, pdf_path: str) -> str:
        """上传 PDF 到 PageIndex，返回 doc_id。"""
        try:
            doc_id = self._client.add(pdf_path)
        except Exception as e:
            raise Match3Exception.of("failed to pageindex_client.add").ctx(
                pdf_path=pdf_path,
            ).as_ex(e)
        return doc_id

    def get_tree(self, doc_id: str) -> dict:
        """获取文档的层级目录树。"""
        try:
            tree = self._client.get_tree(doc_id)
        except Exception as e:
            raise Match3Exception.of("failed to pageindex_client.get_tree").ctx(
                doc_id=doc_id,
            ).as_ex(e)
        return tree

    def retrieve(self, doc_id: str, query: str, max_pages: int = 5) -> list[str]:
        """通过目录树导航找到相关页面，返回页面内容字符串列表。"""
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
        """使用 LLM 导航目录树，识别相关页面。"""
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
        """递归导航目录树节点，选择相关子节点。"""
        if len(result) >= max_pages:
            return

        children = node.get("children", [])
        if not children:
            # 叶子节点 — 将其页面范围加入结果
            page_range = node.get("page_range", [])
            if page_range:
                start, end = page_range[0], page_range[1]
                result.extend(range(start, min(end + 1, start + 3)))  # 每个叶子节点最多 3 页
            return

        # 询问 LLM 哪些子节点与查询相关
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

## 与 Q&A 服务的集成

```python
# app/services/qa_service.py  (doc-navigate 检索路径)

def _answer_with_pageindex(
    self,
    query: str,
    doc_id: str,
    raw_file: RawFile,
) -> Generator[str, None, None]:
    """使用 PageIndex 目录树导航回答针对特定文档的查询（doc-navigate 检索路径）。"""

    retriever = PageIndexRetriever(
        client=self._rt.pageindex,
        llm_caller=self._simple_llm_call,
    )

    # 导航目录树并检索相关页面
    try:
        page_contents = retriever.retrieve(doc_id, query, max_pages=5)
    except Match3Exception as e:
        raise Match3Exception.of("failed to pageindex_retriever.retrieve").ctx(
            query=query,
            doc_id=doc_id,
        ).as_ex(e)

    if not page_contents:
        yield "No relevant pages found in this document for your query."
        return

    # 从检索到的页面构建上下文
    context = "\n\n---\n\n".join(
        f"[Page content from {raw_file.filename}]:\n{content}"
        for content in page_contents
    )

    # 生成答案
    system_prompt = (
        "You are a research assistant for a match-3 game knowledge base. "
        "Answer questions based strictly on the provided document pages. "
        "If the answer is not in the pages, say so explicitly."
    )
    user_prompt = f"Document pages:\n\n{context}\n\nQuestion: {query}"

    yield from self._stream_llm(system_prompt, user_prompt)

    def _simple_llm_call(self, prompt: str) -> str:
        """用于目录树导航的非流式 LLM 调用。"""
        try:
            resp = self._rt.llm.complete(
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise Match3Exception.of("failed to llm.complete for tree navigation").ctx(
                prompt_len=len(prompt),
            ).as_ex(e)
        return resp
```

---

## PageIndex 文档管理 API

```
POST   /api/v1/ingest/upload         → 上传文件，创建 RawFile，入队 ingest_task（≥20 页 PDF 额外建 PageIndex 树）
GET    /api/v1/raw/{raw_file_id}     → 获取 RawFile 状态（就绪后包含 pageindex_doc_id）
POST   /api/v1/qa/ask                → 若请求中含 raw_file_id 且文件为 PageIndex 文档 → doc-navigate 检索路径
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
-- 额外添加到 raw_files 表的列（详见 050-database/schema.md）
pageindex_doc_id    VARCHAR(255)   NULL,  -- client.add() 返回的 doc_id
pageindex_tree      JSONB          NULL,  -- 完整目录树结构
page_count          INTEGER        NULL,  -- PDF 总页数
```

这些字段由 `ingest_task` Worker 在调用 `client.add()` 和 `client.get_tree()` 后写入。
