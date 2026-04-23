# Fulltext Search Implementation — Elasticsearch

## 概述

Match3 使用 **Elasticsearch v9.3.3** 作为全文搜索引擎，提供 **BM25 关键词搜索**能力。

## 适配器实现

### ElasticsearchAdapter

```python
# app/intelligence/fulltext_search/elasticsearch_adapter.py
from elasticsearch import Elasticsearch
from app.runtime import Match3Runtime


class ElasticsearchAdapter:
    """Elasticsearch 适配器，实现 FulltextSearch Protocol。"""

    def __init__(self, rt: Match3Runtime):
        self.client: Elasticsearch = rt.es
        self.config = rt.config.es
        self.logger = rt.logger

    def create_index(self, index_name: str):
        """创建索引，配置 BM25 和分词器。"""
        if self.client.indices.exists(index=index_name):
            self.logger.info(f"Index {index_name} already exists")
            return

        self.client.indices.create(
            index=index_name,
            body={
                "settings": {
                    "number_of_shards": 3,
                    "number_of_replicas": 1,
                    "analysis": {
                        "analyzer": {
                            "default": {
                                "type": "standard",
                            },
                            "english_analyzer": {
                                "type": "standard",
                                "stopwords": "_english_",
                            },
                        }
                    },
                },
                "mappings": {
                    "properties": {
                        "id": {"type": "integer"},
                        "text": {
                            "type": "text",
                            "analyzer": "standard",
                            "fields": {
                                "english": {
                                    "type": "text",
                                    "analyzer": "english_analyzer",
                                }
                            },
                        },
                        "workspace_id": {"type": "integer"},
                        "raw_file_id": {"type": "integer"},
                    }
                },
            }
        )
        self.logger.info(f"Created index: {index_name}")

    def index_document(self, index_name: str, doc_id: int, document: dict):
        """索引单个文档。"""
        self.client.index(
            index=index_name,
            id=doc_id,
            document=document,
        )
        self.logger.debug(f"Indexed document {doc_id} into {index_name}")

    def bulk_index(self, index_name: str, documents: list[dict]):
        """批量索引文档。"""
        from elasticsearch.helpers import bulk

        actions = [
            {
                "_index": index_name,
                "_id": doc["id"],
                "_source": doc,
            }
            for doc in documents
        ]

        success, failed = bulk(self.client, actions)
        self.logger.info(f"Bulk indexed: {success} success, {failed} failed")

    def search(
        self,
        index_name: str,
        query: str,
        workspace_id: int,
        top_k: int = 20,
    ) -> list[dict]:
        """BM25 关键词搜索。"""
        response = self.client.search(
            index=index_name,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["text^2", "text.english"],
                                    "type": "best_fields",
                                }
                            }
                        ],
                        "filter": [
                            {"term": {"workspace_id": workspace_id}}
                        ],
                    }
                },
                "size": top_k,
            }
        )

        return [
            {
                "id": hit["_source"]["id"],
                "score": hit["_score"],
                "text": hit["_source"]["text"],
                "raw_file_id": hit["_source"]["raw_file_id"],
            }
            for hit in response["hits"]["hits"]
        ]

    def delete_document(self, index_name: str, doc_id: int):
        """删除文档。"""
        self.client.delete(index=index_name, id=doc_id)
        self.logger.debug(f"Deleted document {doc_id} from {index_name}")

    def delete_index(self, index_name: str):
        """删除索引。"""
        if self.client.indices.exists(index=index_name):
            self.client.indices.delete(index=index_name)
            self.logger.info(f"Deleted index: {index_name}")
```

## Runtime 集成

```python
# app/runtime.py (build_runtime 部分)
from elasticsearch import Elasticsearch

es_client = Elasticsearch(
    env.ES_URL,
    request_timeout=config.es.request_timeout,
    max_retries=config.es.max_retries,
)

return Match3Runtime(
    # ...
    es=es_client,
    # ...
)
```

## 索引设计

### text_chunks 索引

```json
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "default": {
          "type": "standard"
        },
        "english_analyzer": {
          "type": "standard",
          "stopwords": "_english_"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "id": {"type": "integer"},
      "text": {
        "type": "text",
        "analyzer": "standard",
        "fields": {
          "english": {
            "type": "text",
            "analyzer": "english_analyzer"
          }
        }
      },
      "workspace_id": {"type": "integer"},
      "raw_file_id": {"type": "integer"}
    }
  }
}
```

## 使用示例

### 创建索引

```python
from app.intelligence.fulltext_search.elasticsearch_adapter import ElasticsearchAdapter

adapter = ElasticsearchAdapter(rt)
adapter.create_index("text_chunks")
```

### 索引单个文档

```python
adapter.index_document(
    index_name="text_chunks",
    doc_id=12345,
    document={
        "id": 12345,
        "text": "这是一段文本内容",
        "workspace_id": 1,
        "raw_file_id": 42,
    },
)
```

### 批量索引

```python
documents = [
    {"id": 1, "text": "文本1", "workspace_id": 1, "raw_file_id": 42},
    {"id": 2, "text": "文本2", "workspace_id": 1, "raw_file_id": 42},
    # ... 更多文档
]

adapter.bulk_index("text_chunks", documents)
```

### BM25 搜索

```python
results = adapter.search(
    index_name="text_chunks",
    query="match3 puzzle game",
    workspace_id=1,
    top_k=20,
)

for result in results:
    print(f"Score: {result['score']:.4f} - {result['text'][:100]}")
```

### 删除文档

```python
adapter.delete_document("text_chunks", doc_id=12345)
```

## 高级搜索

### Multi-field 搜索

```python
response = adapter.client.search(
    index="text_chunks",
    body={
        "query": {
            "multi_match": {
                "query": "candy crush saga",
                "fields": ["text^2", "text.english", "title^3"],
                "type": "best_fields",
            }
        },
        "size": 20,
    }
)
```

### Boolean 查询

```python
response = adapter.client.search(
    index="text_chunks",
    body={
        "query": {
            "bool": {
                "must": [
                    {"match": {"text": "match3"}}
                ],
                "should": [
                    {"match": {"text": "puzzle"}}
                ],
                "filter": [
                    {"term": {"workspace_id": 1}},
                    {"range": {"created_at": {"gte": "2024-01-01"}}}
                ],
            }
        }
    }
)
```

### Highlighting

```python
response = adapter.client.search(
    index="text_chunks",
    body={
        "query": {
            "match": {"text": "candy crush"}
        },
        "highlight": {
            "fields": {
                "text": {
                    "pre_tags": ["<em>"],
                    "post_tags": ["</em>"],
                }
            }
        }
    }
)

for hit in response["hits"]["hits"]:
    if "highlight" in hit:
        print(hit["highlight"]["text"])
```

## 性能优化

### 1. 批量索引

使用 `bulk_index` 而非单个 `index_document`：

```python
# ✅ 正确：批量索引
adapter.bulk_index("text_chunks", documents)

# ❌ 错误：循环单个索引
for doc in documents:
    adapter.index_document("text_chunks", doc["id"], doc)
```

### 2. 分片配置

- **小索引**（< 10GB）：1-3 个分片
- **中等索引**（10-100GB）：3-5 个分片
- **大索引**（> 100GB）：5-10 个分片

### 3. 刷新策略

```python
# 批量导入时关闭自动刷新
adapter.client.indices.put_settings(
    index="text_chunks",
    body={"index": {"refresh_interval": "-1"}}
)

# 导入完成后重新启用
adapter.client.indices.put_settings(
    index="text_chunks",
    body={"index": {"refresh_interval": "1s"}}
)
```

### 4. 查询优化

- 使用 `filter` 而非 `must` 进行精确匹配（不计算分数）
- 限制返回字段：`_source: ["id", "text"]`
- 使用 `size` 限制返回数量

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  fulltext_search:
    provider: elasticsearch
    implementations:
      elasticsearch:
        request_timeout: 30    # Request timeout (seconds)
        max_retries: 3         # Max retries
```

### Env (.env)

```bash
ELASTICSEARCH_URL=http://localhost:9200
```

## 相关文档

- **[protocol.md](./protocol.md)** — FulltextSearch Protocol 定义
- **[versions/elasticsearch-v9.3.3.md](./versions/elasticsearch-v9.3.3.md)** — Elasticsearch 版本技术文档
- **[../../design/solution-final/030-rag/](../../design/solution-final/030-rag/)** — BM25 在 RAG 中的使用
