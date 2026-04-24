# 系统主流程时序图

本目录描述 match3-wiki 四条核心数据流：数据如何在 API → Service → Worker → Storage → Intelligence 各层之间流动。

---

## 流程列表

| 文件 | 流程 | 简述 |
|------|------|------|
| [flow-1-ingestion.md](flow-1-ingestion.md) | 文件导入流水线 | 上传文件 → 解析 → 分块 → 向量化 → 知识图谱抽取；≥20 页 PDF 额外向 PageIndex 建树 |
| [flow-2-qa-chunk.md](flow-2-qa-chunk.md) | Q&A 问答（hybrid-search） | 用户提问 → 混合检索（Dense+Sparse+BM25+图谱）→ 重排序 → LLM 流式回答 |
| [flow-3-wiki-compile.md](flow-3-wiki-compile.md) | Wiki 页面编译 | 触发编译 → 五步流水线 → 生成 Wiki 页面；编译完成后 wiki-lookup 路径直接命中 |
| [flow-4-pageindex.md](flow-4-pageindex.md) | Q&A 问答（doc-navigate） | 用户提问 → PageIndex 目录树导航 → 精准定位章节 → LLM 流式回答 |

---

## Q&A 三条检索路径

流程 2 和流程 4 都是 Q&A 问答流程，区别在于 AdaptiveRAGRouter 的路由结果：

| 路径 | 触发条件 | 检索方式 | 数据来源 |
|------|----------|----------|----------|
| **hybrid-search** | 通用知识类问题 | Dense + Sparse + BM25 三路混合检索 + 可选 GraphRAG（复杂查询）+ cross-encoder 重排序 | Milvus / Elasticsearch / Neo4j |
| **wiki-lookup** | 已有对应 Wiki 条目的主题查询 | 直接读取已编译的 Wiki 页面，不做向量检索 | PostgreSQL（t_wiki_pages） |
| **doc-navigate** | 明确指向某份大型 PDF 文档的查询 | PageIndex 目录树导航，LLM 选择相关章节节点 | PageIndex API |

所有三条路径共用同一个 API 入口（`GET /api/v1/qa/ask`）和 SSE 流式输出结构，前端无需感知路径差异。

---

## 导入与查询的数据依赖关系

```
Flow 1 (ingestion)
  │
  ├── all files ──► chunk → Milvus + ES (used by hybrid-search)
  │                       → Neo4j (used by GraphRAG)
  │
  └── PDF ≥20 pages ──► (also) PageIndex tree build (used by doc-navigate)

Flow 3 (wiki compile) ──on publish──► t_wiki_pages (used by wiki-lookup)

Flow 2 (hybrid-search)  ┐
Flow 4 (doc-navigate)   ├── both retrieve from Flow 1 output
wiki-lookup             ┘── reads from Flow 3 output
```
