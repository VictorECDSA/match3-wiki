# RAG 模块概述

## 三条检索路径

| 路径 | 路由标记 | 适用场景 | 核心存储 |
|------|---------|---------|---------|
| `hybrid-search` | `chunk` | 通用事实性问答、语义搜索 | Milvus + Elasticsearch + Neo4j |
| `wiki-lookup` | `entry` | 查询/编译特定主题的 Wiki 条目 | PostgreSQL `t_wiki_pages` |
| `doc-navigate` | `page` | 长 PDF 文档导航（≥20 页） | PageIndex API |

---

## 两条独立流程

RAG 模块分为两条完全独立的流程——**索引流程**（离线，文档导入时执行）和**检索流程**（在线，用户提问时执行）：

### 索引流程（离线）

```
原始文档（PDF / DOCX / HTML / MD）
    │
    ▼
[1] 格式转 Markdown
    │
    ▼
[2] 切块策略（markdown_header 或 fixed_size）
    │
    ▼
[3] Parent-Child 索引层（必须应用）
    │ child（300 字）建向量索引，携带 parent_id
    │ 查询命中 child → 返回 parent（1500 字）上下文
    ▼
[4] 三路并行建索引
    ├── Dense + Sparse Embedding → Milvus
    ├── 原文 + metadata → Elasticsearch（BM25）
    └── LLM 实体抽取 → Neo4j（可选，graph=True 时启用）
```

Wiki 页面的索引流程独立，走 OpenKB 五步编译流水线——见 `030-rag/indexing/wiki-compile.md`。

### 检索流程（在线）

```
用户查询
    │
    ▼
AdaptiveRAGRouter → (path, complexity)
    │
    ├── chunk  → HybridSearchEngine 五阶段流水线（查询扩展→多通道检索→RRF融合→精排→验证）
    ├── entry  → lookup_or_trigger_compile()
    └── page   → PageIndexRetriever 目录树导航
    │
    ▼
LLM 生成（SSE 流式输出）
```

---

## 索引侧与查询侧的对应关系

| 索引侧决策 | 查询侧影响 |
|-----------|-----------|
| parent_child 必须应用 | 查询返回大块上下文，减少截断损失 |
| 建了 sparse 索引（BGE-M3 SPLADE） | 查询侧才能开 `sparse=True` |
| 建了 Neo4j 图谱 | 查询侧才能开 `graph=True` |
| ≥20 页 PDF 提交了 PageIndex 建树 | 可走 doc-navigate 路径 |
| 主题原始素材已编译为 WikiPage | wiki-lookup 直接返回已编译页面 |

---

## 文档索引

### 索引流程

| 文件 | 内容 |
|------|------|
| `030-rag/indexing/chunking.md` | 文档转 Markdown、切块策略、Parent-Child 索引层、三路建索引 |
| `030-rag/indexing/wiki-compile.md` | OpenKB 五步 Wiki 编译流水线、WikiCompileService、compile_topic 任务 |

### 检索流程

| 文件 | 内容 |
|------|------|
| `030-rag/retrieval/router.md` | RAGPath 枚举、AdaptiveRAGRouter、路径选择逻辑、QAService 分发、CAG 策略 |
| `030-rag/retrieval/hybrid-search.md` | 五阶段检索流水线、RetrievalConfig、PROFILE_MAP、所有检索策略 |
| `030-rag/retrieval/wiki-lookup.md` | `lookup_or_trigger_compile()` 条目查找逻辑 |
| `030-rag/retrieval/doc-navigate.md` | PageIndex 长文档检索、QAService doc-navigate 路径 |
| `030-rag/retrieval/multi-agent.md` | 多智能体 RAG（并行域智能体 + 验证器 + 写作器） |
