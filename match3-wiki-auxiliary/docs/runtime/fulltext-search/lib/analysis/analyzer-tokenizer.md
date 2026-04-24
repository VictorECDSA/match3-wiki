# 分析器（Analyzer）与分词器（Tokenizer）

Elasticsearch 在索引文档和执行全文查询时，都需要对原始文本进行预处理，将其转换为可用于倒排索引的词项（Token）序列。这一过程由**分析器（Analyzer）**完成，分析器内部由三类组件串联构成。

## 分析流水线

```
原始文本
    ↓
Character Filter（字符过滤器）  ← 可选，预处理原始字符
    ↓
Tokenizer（分词器）             ← 必须，切分为 Token 序列
    ↓
Token Filter（词元过滤器）       ← 可选，对 Token 做变换
    ↓
词项序列（写入倒排索引 / 用于查询匹配）
```

## 三类组件说明

### 字符过滤器（Character Filter）

在分词前处理原始字符串，例如：去除 HTML 标签、替换特殊字符：

```json
// html_strip: remove HTML tags before tokenization
"char_filter": ["html_strip"]
```

### 分词器（Tokenizer）

将连续文本切分为 Token 序列，是分析器的核心组件。常用分词器：

| 分词器 | 切分逻辑 | 适用场景 |
|--------|----------|----------|
| `standard` | Unicode 标准分词，按空格/标点切分，小写化 | 英文通用 |
| `whitespace` | 仅按空格切分 | 保留大小写、标点的场景 |
| `ik_max_word` | IK 中文最大切分 | 中文文档 |

### 词元过滤器（Token Filter）

对分词结果做进一步变换，例如：

```json
"filter": [
    "lowercase",          // uppercase → lowercase
    "stop",               // remove stop words: "the", "is", "a"
    "stemmer"             // stemming: "running" → "run"
]
```

## 本项目的分析器配置

`text_chunks` 索引的 `content` 字段使用 `standard` 分析器（英文）+ IK 中文分析器（若内容含中文）：

```python
mappings = {
    "properties": {
        "content": {
            "type": "text",
            "analyzer": "standard",
        },
        "workspace_id": {
            "type": "keyword",   # keyword field: no analysis, exact match only
        },
    }
}
```

`keyword` 类型字段完全跳过分析器，用于精确过滤（如 `workspace_id`）。
