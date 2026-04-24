# Elasticsearch DSL 查询语法

**DSL（Domain-Specific Language，领域特定语言）** 在 Elasticsearch 中指基于 JSON 构造的结构化查询语言，通过 HTTP 请求体传递，描述全文检索、过滤、排序、聚合等操作。所有对 Elasticsearch 的搜索请求都通过 DSL 表达。

## 查询上下文 vs 过滤上下文

DSL 中的条件分为两类：

| 类型 | 作用 | 是否影响评分 | 是否可缓存 |
|------|------|-------------|-----------|
| 查询上下文（query context） | 计算文档与查询的相关性分数 `_score` | 是 | 否 |
| 过滤上下文（filter context） | 判断文档是否满足条件，二值匹配 | 否 | 是 |

`bool` 查询的 `must` / `should` 运行在查询上下文；`filter` / `must_not` 运行在过滤上下文。

## 常用查询类型

### match — 全文匹配

分析查询词后在倒排索引中匹配，是最基本的全文检索方式：

```python
query = {
    "match": {
        "content": {
            "query": "elasticsearch tutorial",
            "operator": "and"   # both terms must appear; default is "or"
        }
    }
}
```

### multi_match — 多字段匹配与字段提权（Boosting）

在多个字段上同时匹配，用 `^N` 语法放大某字段的得分权重：

```python
query = {
    "multi_match": {
        "query": "python programming",
        "fields": [
            "title^3",     # 3x weight
            "content^1",
            "tags^2"
        ],
        "type": "best_fields",   # use highest-scoring field
        "fuzziness": "AUTO"
    }
}
```

`type` 常用值：
- `best_fields`：取各字段中最高分（默认）
- `most_fields`：累加各字段分数
- `cross_fields`：将多字段视为一个大字段

### bool — 复合布尔查询

将多个子查询组合，是构建复杂条件最常用的容器：

```python
query = {
    "bool": {
        "must": [                              # AND — must match, affects score
            {"match": {"content": "python"}}
        ],
        "should": [                            # OR — optional, boosts score if matched
            {"match": {"tags": "tutorial"}},
            {"match": {"category": "programming"}}
        ],
        "must_not": [                          # NOT — must not match, filter context
            {"term": {"status": "draft"}}
        ],
        "filter": [                            # AND — must match, no score contribution
            {"range": {"view_count": {"gte": 100}}},
            {"term": {"category": "tech"}}
        ]
    }
}
```

`should` 在没有 `must` 时相当于 OR；有 `must` 时变为加分项（满足则提高 `_score`，不满足不排除）。

### range — 范围查询

用于日期、数值字段的区间过滤：

```python
query = {
    "range": {
        "created_at": {
            "gte": "2026-01-01",
            "lte": "2026-04-22",
            "format": "yyyy-MM-dd"
        }
    }
}
```

常用运算符：`gte`（≥）、`gt`（>）、`lte`（≤）、`lt`（<）。

### prefix / wildcard — 前缀与通配符查询

```python
# prefix: efficient, uses index
query_prefix = {
    "prefix": {"title": {"value": "intro"}}   # matches "introduction", "intro to"
}

# wildcard: flexible but slow (full scan on un-analyzed field)
query_wildcard = {
    "wildcard": {"title": {"value": "elastic*search"}}   # * = any chars
}
```

`prefix` 在索引上运行效率高；`wildcard` 尤其是以 `*` 开头的模式会退化为全量扫描，应谨慎使用。

### highlight — 高亮摘要

在返回结果中标记命中片段，常用于前端展示搜索关键词高亮：

```python
highlight = {
    "fields": {
        "content": {
            "pre_tags": ["<strong>"],
            "post_tags": ["</strong>"],
            "fragment_size": 150,       # snippet length in chars
            "number_of_fragments": 3    # max snippets per document
        }
    }
}
# highlight is a top-level parameter alongside query, not nested inside query
response = client.search(index="articles", query=query, highlight=highlight)
```

响应中每个命中文档的 `highlight` 字段包含已插入 `<strong>` 标签的文本片段。

## 在本项目中的使用

本项目的全文检索场景（文档块搜索）主要使用 `bool` + `must`（`match` 或 `multi_match`）+ `filter`（`term` 按工作区过滤）的组合模式，并通过字段 Boosting 提升标题相关性。聚合操作详见 [aggregation.md](./aggregation.md)，分析器与分词器详见 [analysis/analyzer-tokenizer.md](./analysis/analyzer-tokenizer.md)。
