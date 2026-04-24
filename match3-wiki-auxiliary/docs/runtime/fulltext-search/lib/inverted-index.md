# 倒排索引（Inverted Index）

**倒排索引（Inverted Index）** 是全文搜索引擎的核心数据结构，由词项（Term）到文档列表的映射构成——与正排索引（文档 → 包含哪些词）方向相反，故名"倒排"。Elasticsearch 中每个字段都有独立的倒排索引。

## 结构示意

给定三个文档：

```
doc_1: "match3 game retention"
doc_2: "game level design"
doc_3: "retention strategy"
```

对应的倒排索引：

```
"match3"    → [doc_1]
"game"      → [doc_1, doc_2]
"retention" → [doc_1, doc_3]
"level"     → [doc_2]
"design"    → [doc_2]
"strategy"  → [doc_3]
```

每个词项的文档列表还记录词频（TF）、位置、偏移量等信息，供 BM25 打分使用。

## 查询流程

执行 `match` 查询时，Elasticsearch 先对查询文本分词（同样走 Analyzer 流水线），再在倒排索引中查找各词项的文档集合，取交集或并集，最后用 BM25 排序：

```
query: "game retention"
→ tokens: ["game", "retention"]
→ "game" hits: [doc_1, doc_2]
→ "retention" hits: [doc_1, doc_3]
→ union: [doc_1(×2), doc_2, doc_3]  → BM25 score → ranked results
```

## 与向量索引的对比

倒排索引擅长精确词汇匹配，构建快、查询稳定；向量索引（如 HNSW）擅长语义相似度，能跨越词汇差异。两者互补，是混合检索的两条腿。

倒排索引的构建和维护由 Elasticsearch 内部自动完成，业务代码只需关注分析器（Analyzer）的配置是否与预期分词方式匹配。
