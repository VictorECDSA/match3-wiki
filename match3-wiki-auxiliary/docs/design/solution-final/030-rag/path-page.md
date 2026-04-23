# doc-navigate：PageIndex 长文档检索

本文件介绍 Q&A 服务与 PageIndex 在 doc-navigate 查询中的集成。PageIndex 客户端及检索器的核心实现位于 `020-ingestion/pageindex.md`。

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

## QAService 中的 Doc-Navigate

```python
# app/services/qa_service.py
from app.common.constants import constants

class QAService:

    def __init__(self, rt: Match3Runtime):
        self._rt = rt

    def ask(
        self,
        query: str,
        workspace_id: str,
        user_id: str,
        raw_file_id: str | None = None,
    ) -> Generator[str, None, None]:
        """Q&A 主入口，选择检索路径并流式输出答案。"""

        # 确定检索路径
        path, method = self._select_path(query, raw_file_id, workspace_id)

        # 创建 QA 会话
        qa_repo = QARepository(self._rt.db_engine)
        session = qa_repo.insert(QASession(
            id=str(uuid4()),
            workspace_id=workspace_id,
            user_id=user_id,
            query=query,
            rag_path=path.value,
            rag_method=method.value if method else None,
            status=QASessionStatus.GENERATING,
        ))

        # 执行路径
        answer_parts = []
        try:
            if path == RAGPath.PAGE:
                gen = self._answer_path_page(query, raw_file_id, workspace_id)
            elif path == RAGPath.ENTRY:
                gen = self._answer_path_entry(query, workspace_id)
            else:
                gen = self._answer_path_chunk(query, workspace_id, method)

            for token in gen:
                answer_parts.append(token)
                yield token

        except Match3Exception as e:
            qa_repo.update_status(session.id, QASessionStatus.FAILED, error=str(e))
            raise

        # 保存完整答案
        full_answer = "".join(answer_parts)
        qa_repo.update_answer(session.id, answer=full_answer, status=QASessionStatus.DONE)

    def _select_path(
        self,
        query: str,
        raw_file_id: str | None,
        workspace_id: str,
    ) -> tuple[RAGPath, ChunkMethod | None]:
        """根据上下文选择检索路径。"""

        # 显式文件引用 → 检查是否为 PageIndex 文档
        if raw_file_id:
            raw_file_repo = RawFileRepository(self._rt.db_engine)
            rf = raw_file_repo.find_by_id(raw_file_id)
            if rf and rf.pageindex_doc_id:
                return RAGPath.PAGE, None

        # 路由器对查询进行分类
        from app.rag.router import AdaptiveRAGRouter
        router = AdaptiveRAGRouter(self._rt)
        return router.route(query)

    def _answer_path_page(
        self,
        query: str,
        raw_file_id: str | None,
        workspace_id: str,
    ) -> Generator[str, None, None]:
        """使用 PageIndex 目录树导航回答问题。"""
        from app.rag.page.pageindex_retriever import PageIndexRetriever

        # 查找文档
        if raw_file_id:
            raw_file_repo = RawFileRepository(self._rt.db_engine)
            rf = raw_file_repo.find_by_id(raw_file_id)
        else:
            # 为该查询查找最匹配的 PageIndex 文档
            rf = self._find_best_pageindex_doc(query, workspace_id)

        if rf is None or not rf.pageindex_doc_id:
            yield "未找到与该查询相关的长文档。"
            return

        retriever = PageIndexRetriever(
            client=self._rt.pageindex,
            llm_caller=self._simple_llm_call,
        )

        try:
            page_contents = retriever.retrieve(rf.pageindex_doc_id, query, max_pages=5)
        except Match3Exception as e:
            raise Match3Exception.of("failed to retrieve pageindex pages").ctx(
                query=query,
                doc_id=rf.pageindex_doc_id,
            ).as_ex(e)

        if not page_contents:
            yield f"在文档 '{rf.filename}' 中未找到与该查询相关的章节。"
            return

        context = "\n\n---\n\n".join(
            f"[Pages from: {rf.filename}]\n{content}"
            for content in page_contents
        )

        system_prompt = (
            "You are a research assistant for a match-3 game knowledge base. "
            "Answer the question based strictly on the provided document pages. "
            "Always cite the document name and indicate which section the information came from."
        )
        user_prompt = f"Document content:\n\n{context}\n\nQuestion: {query}"

        yield from self._stream_llm(system_prompt, user_prompt)

    def _find_best_pageindex_doc(self, query: str, workspace_id: str) -> "RawFile | None":
        """从 PostgreSQL 查询当前工作区内已注册 PageIndex 的文档，返回第一个（默认取最近更新的）。"""
        raw_file_repo = RawFileRepository(self._rt.db_engine)
        try:
            candidates = raw_file_repo.find_all_with_pageindex(workspace_id)
        except Exception as e:
            raise Match3Exception.of("failed to find pageindex docs").ctx(
                query=query, workspace_id=workspace_id,
            ).as_ex(e)

        if not candidates:
            return None

        # 若只有一个文档，直接返回；若有多个，返回最近更新的一个
        # （更精确的多文档匹配逻辑可在此扩展，例如对 filename/tags 做模糊匹配）
        candidates.sort(key=lambda rf: rf.updated_at, reverse=True)
        return candidates[0]

    def _answer_path_entry(self, query: str, workspace_id: str) -> Generator[str, None, None]:
        """从已编译的 Wiki 条目页面检索并回答。"""
        from app.rag.entry.entry_lookup import lookup_or_trigger_compile

        page = lookup_or_trigger_compile(self._rt, query, workspace_id)

        if page is None:
            yield "未找到该主题的 Wiki 条目，已加入编译队列。"
            return

        if page.status == WikiPageStatus.COMPILING:
            yield "该 Wiki 页面正在编译中，请稍后再试。"
            return

        system_prompt = (
            "You are a research assistant for a match-3 game knowledge base. "
            "Answer the question based on the provided wiki page content."
        )
        user_prompt = f"Wiki page content:\n\n{page.content}\n\nQuestion: {query}"

        yield from self._stream_llm(system_prompt, user_prompt)

    def _answer_path_chunk(
        self,
        query: str,
        workspace_id: str,
        method: "ChunkMethod",
    ) -> Generator[str, None, None]:
        """使用基于文本块的 RAG 方法回答问题。"""
        from app.rag.chunk import (
            naive_rag, multi_query_rag, hyde_rag,
            hybrid_search, rerank, crag, self_rag,
            graph_rag, text2sql_rag, agentic_rag,
            multimodal_rag, speculative_rag,
        )

        method_map = {
            ChunkMethod.NAIVE: lambda: naive_rag(self._rt, query, workspace_id),
            ChunkMethod.MULTI_QUERY: lambda: multi_query_rag(self._rt, query, workspace_id),
            ChunkMethod.HYDE: lambda: hyde_rag(self._rt, query, workspace_id),
            ChunkMethod.HYBRID: lambda: rerank(query, hybrid_search(self._rt, query, workspace_id, top_k=150)),
            ChunkMethod.RERANK: lambda: rerank(query, hybrid_search(self._rt, query, workspace_id, top_k=150)),
            ChunkMethod.CRAG: lambda: crag.corrective_rag(self._rt, query, workspace_id),
            ChunkMethod.SELF_RAG: lambda: self_rag.self_rag(self._rt, query, workspace_id),
            ChunkMethod.GRAPH_RAG: lambda: graph_rag.graph_rag(self._rt, query, workspace_id),
            ChunkMethod.TEXT2SQL: lambda: text2sql_rag.text2sql_rag(self._rt, query, workspace_id),
            ChunkMethod.AGENTIC: lambda: agentic_rag.agentic_rag(self._rt, query, workspace_id),
            ChunkMethod.SPECULATIVE: lambda: speculative_rag.speculative_rag(self._rt, query, workspace_id),
        }

        retrieve_fn = method_map.get(method, method_map[ChunkMethod.HYBRID])
        chunks = retrieve_fn()

        if not chunks:
            yield "知识库中未找到与该查询相关的信息。"
            return

        context = "\n\n".join(
            f"[Source {i+1}]: {c['content']}"
            for i, c in enumerate(chunks[:8])
        )

        system_prompt = (
            "You are a research assistant for a match-3 game knowledge base. "
            "Answer the question based on the retrieved context. "
            "Be specific and cite source numbers. "
            "If the context doesn't contain the answer, say so clearly."
        )
        user_prompt = f"Retrieved context:\n\n{context}\n\nQuestion: {query}"

        yield from self._stream_llm(system_prompt, user_prompt)

    def _stream_llm(self, system_prompt: str, user_prompt: str) -> Generator[str, None, None]:
        """流式输出 LLM 响应 token。"""
        try:
            stream = self._rt.llm.stream(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:
            raise Match3Exception.of("failed to stream llm response").ctx(
                system_len=len(system_prompt),
                user_len=len(user_prompt),
            ).as_ex(e)

        yield from stream

    def _simple_llm_call(self, prompt: str) -> str:
        """用于目录树导航和路由的非流式 LLM 调用。"""
        try:
            resp = self._rt.llm.complete(
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise Match3Exception.of("failed to simple llm call").ctx(
                prompt_len=len(prompt),
            ).as_ex(e)
        return resp
```
