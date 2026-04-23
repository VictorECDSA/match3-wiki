# RAG 概述：三条检索路径

## 自适应路由器

每个 Q&A 查询首先经过 `AdaptiveRAGRouter`，对查询进行分类并选择合适的检索路径。

```python
# app/rag/router.py
from __future__ import annotations
from enum import Enum
from typing import Generator
from app.common.exceptions import Match3Exception
from app.runtime import Match3Runtime


class RAGPath(str, Enum):
    CHUNK = "chunk"     # hybrid-search：对分块语料库进行混合检索（Dense + Sparse + BM25 + 可选 GraphRAG）+ 重排序
    ENTRY = "entry"     # 编译好的 Wiki 条目页面查找
    PAGE = "page"       # PageIndex 长文档导航


class ChunkMethod(str, Enum):
    NAIVE = "naive"
    MULTI_QUERY = "multi_query"
    HYDE = "hyde"
    HYBRID = "hybrid"
    RERANK = "rerank"
    CRAG = "crag"
    SELF_RAG = "self_rag"
    GRAPH_RAG = "graph_rag"
    TEXT2SQL = "text2sql"
    AGENTIC = "agentic"
    SPECULATIVE = "speculative"
    MULTI_AGENT = "multi_agent"


ROUTER_PROMPT = """You are routing a user query to the correct knowledge retrieval path.

Paths:
- chunk: General factual Q&A, comparisons, research questions. Uses semantic search.
- entry: Requesting a specific wiki page, topic summary, or knowledge article.
- page: Navigating a specific long document (report, PDF, design doc). User references a document.

Query complexity levels (for chunk path only):
- simple: Single-hop fact lookup. Method: naive or hybrid+rerank.
- moderate: Multi-hop, needs comparisons. Method: multi_query or hyde.
- complex: Deep analysis, graph relationships, multi-entity. Method: graph_rag or multi_agent.
- analytical: Structured data query (revenue numbers, download stats). Method: text2sql.
- uncertain: May need web search fallback. Method: crag.

Query: {query}

Reply with JSON only:
{{"path": "chunk|entry|page", "complexity": "simple|moderate|complex|analytical|uncertain", "method": "naive|multi_query|hyde|hybrid|rerank|crag|self_rag|graph_rag|text2sql|agentic|speculative|multi_agent"}}
"""


class AdaptiveRAGRouter:
    """将查询路由到 hybrid-search（chunk）、wiki-lookup（entry）或 doc-navigate（page），基于查询分类结果。"""

    def __init__(self, rt: Match3Runtime):
        self._rt = rt

    def route(self, query: str, context: dict | None = None) -> tuple[RAGPath, ChunkMethod]:
        """对查询进行分类，返回 (path, method) 元组。"""
        import json

        try:
            content = self._rt.llm.complete(
                messages=[{
                    "role": "user",
                    "content": ROUTER_PROMPT.format(query=query),
                }],
                model=self._rt.config.llm.default_model,
                response_format={"type": "json_object"},
                max_tokens=100,
                temperature=0,
            )
        except Exception as e:
            raise Match3Exception.of("failed to route query").ctx(query=query).as_ex(e)

        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            raise Match3Exception.of("failed to parse router response").ctx(query=query).as_ex(e)

        path = RAGPath(result.get("path", "chunk"))
        method = ChunkMethod(result.get("method", "hybrid"))
        return path, method
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

[2] AdaptiveRAGRouter.route(query)
    ├─ path == "entry" ──────────────────────────────────────► wiki-lookup
    ├─ path == "page"  ──────────────────────────────────────► doc-navigate（查找最匹配的文档）
    └─ path == "chunk" ──────────────────────────────────────►[3]

[3] method 选择（hybrid-search 路径）
    ├─ "naive"        ─────► NaiveRAG
    ├─ "multi_query"  ─────► MultiQueryRAG
    ├─ "hyde"         ─────► HyDERAG
    ├─ "hybrid"       ─────► HybridSearch + Reranker（最常用）
    ├─ "crag"         ─────► CorrectiveRAG
    ├─ "self_rag"     ─────► SelfRAG
    ├─ "graph_rag"    ─────► GraphRAG
    ├─ "text2sql"     ─────► Text2SQLRAG
    ├─ "agentic"      ─────► AgenticRAG
    ├─ "speculative"  ─────► SpeculativeRAG
    └─ "multi_agent"  ─────► MultiAgentRAG
```

---

## 路径概述

### hybrid-search

用于对分块语料库进行临时事实性查询。路由器将此路径标记为 `chunk`，对应三条路径中检索能力最强的一条：Dense 向量 + Sparse BM42 + BM25 关键词 + 可选 Neo4j 图谱。

**输入**：自然语言查询
**存储**：Milvus（向量）+ Elasticsearch（BM25）+ Neo4j（图谱）
**输出**：携带来源引用的流式答案

全部 16 种 RAG 方法均属于此路径。完整伪代码见 `030-rag/path-chunk.md`。

常用 method 选择启发式：
| 查询类型 | 推荐方法 |
|------------|-------------------|
| "X 是什么？" | naive 或 hybrid+rerank |
| "比较 X 和 Y" | multi_query 或 hyde |
| "与 X 有关联的游戏有哪些？" | graph_rag |
| "前 10 名游戏的收入" | text2sql |
| "Y 领域的最新趋势是什么？" | crag（可能需要 Web 兜底） |
| "告诉我关于 X 的一切" | multi_agent |
| "X 是否为真？" | self_rag 或 speculative |

### wiki-lookup

用于 Wiki 页面查找与编译。

**输入**：主题名称 / slug
**存储**：PostgreSQL（Wiki 页面）+ MinIO（编译好的 .md 文件）
**输出**：完整编译好的 Wiki 页面（若已过期则按需编译）

详见 `030-rag/path-entry.md`。

### doc-navigate

用于导航某个特定的长 PDF 文档。

**输入**：查询 + doc_id（或用于模糊匹配的文档标题）
**存储**：PageIndex API + PostgreSQL 中的 raw_files 元数据
**输出**：来自 PDF 特定页面的流式答案

详见 `030-rag/path-page.md`。

---

## 提示缓存（CAG）策略

对于使用 `wiki-lookup` 或带已知上下文的 `hybrid-search` 的查询：

```
静态部分（缓存）：
┌──────────────────────────────────────┐
│ 系统提示 + 角色 + 指令               │ ← 由 LLM 提供商缓存
│ 完整 Wiki 页面（若为 wiki-lookup）  │   （Anthropic: cache_control=ephemeral）
│ 工具定义（若为 agentic）             │
└──────────────────────────────────────┘

动态部分（不缓存）：
┌──────────────────────────────────────┐
│ 检索到的块（每次查询都会变化）       │
│ 用户查询                             │
└──────────────────────────────────────┘
```

对于 Anthropic Claude，使用 `cache_control`：
```python
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": wiki_page_content,
                "cache_control": {"type": "ephemeral"},  # 缓存此块
            },
            {
                "type": "text",
                "text": f"Question: {query}",             # 动态内容，不缓存
            },
        ],
    }
]
```
