# Fulltext Search Implementation — Elasticsearch

## 概述

使用 **Elasticsearch v9.3.3** 实现 `FullTextSearch` Protocol，提供 BM25 关键词搜索能力。

---

## 工厂函数

```python
# backend/runtime_impl/implements/fulltext_search/fulltext_search.py
from elasticsearch import Elasticsearch
from backend.config import Config, Env
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.fulltext_search import FullTextSearch
from .impl_elasticsearch.es_adapter import ElasticsearchAdapter

def create_fulltext_search(config: Config, env: Env, logger: Logger) -> FullTextSearch:
    """创建 FullTextSearch 实例
    
    Args:
        config: 配置对象
        env: 环境变量
        logger: 日志记录器
    
    Returns:
        实现了 FullTextSearch Protocol 的 ElasticsearchAdapter 实例
    
    Raises:
        ValueError: provider 不支持时抛出
    """
    provider = config.runtime.fulltext_search.provider
    
    if provider == "elasticsearch":
        es_client = Elasticsearch(
            env.ELASTICSEARCH_URL,
            request_timeout=config.runtime.fulltext_search.implementations.elasticsearch.request_timeout,
            max_retries=config.runtime.fulltext_search.implementations.elasticsearch.max_retries,
        )
        
        logger.info("Elasticsearch client initialized")
        return ElasticsearchAdapter(es_client, config, logger)
    else:
        raise ValueError(f"Unsupported fulltext_search provider: {provider}")
```

---

## 适配器实现

```python
# backend/runtime_impl/implements/fulltext_search/impl_elasticsearch/es_adapter.py
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from backend.config import Config
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.fulltext_search import FullTextSearch

class ElasticsearchAdapter:
    """Elasticsearch 适配器，实现 FullTextSearch Protocol"""
    
    def __init__(self, client: Elasticsearch, config: Config, logger: Logger):
        self.client = client
        self.config = config.runtime.fulltext_search
        self.logger = logger
    
    def create_index(self, index_name: str):
        """创建索引，配置 BM25 和分词器"""
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
                            "default": {"type": "standard"},
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
        """索引单个文档"""
        self.client.index(
            index=index_name,
            id=doc_id,
            document=document,
        )
        self.logger.debug(f"Indexed document {doc_id} into {index_name}")
    
    def bulk_index(self, index_name: str, documents: list[dict]):
        """批量索引文档"""
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
        """BM25 关键词搜索"""
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
        """删除文档"""
        self.client.delete(index=index_name, id=doc_id)
        self.logger.debug(f"Deleted document {doc_id} from {index_name}")
    
    def delete_index(self, index_name: str):
        """删除索引"""
        if self.client.indices.exists(index=index_name):
            self.client.indices.delete(index=index_name)
            self.logger.info(f"Deleted index: {index_name}")
```

---

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  fulltext_search:
    provider: elasticsearch
    implementations:
      elasticsearch:
        request_timeout: 30    # 请求超时（秒）
        max_retries: 3         # 最大重试次数
```

### Env (.env)

```bash
ELASTICSEARCH_URL=http://localhost:9200
```

---

## 相关文档

- **[protocol.md](./protocol.md)** — FullTextSearch Protocol 定义
- **[versions/elasticsearch-v9.3.3.md](./versions/elasticsearch-v9.3.3.md)** — Elasticsearch 版本技术文档
- **[../../design/solution-final/030-rag/](../../design/solution-final/030-rag/)** — BM25 在 RAG 中的使用
