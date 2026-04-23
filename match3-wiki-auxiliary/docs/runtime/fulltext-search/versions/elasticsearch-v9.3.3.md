# Elasticsearch v9.3.3

**Version**: 9.3.3  
**Release Date**: 2026-04-08  
**Category**: Full-Text Search Engine  
**License**: Elastic License 2.0 & SSPL

---

## API Interface Overview

### 1. Client Connection

```python
from elasticsearch import Elasticsearch

def connect(
    hosts: list[str],              # ES cluster nodes, e.g., ["http://localhost:9200"]
    basic_auth: tuple[str, str],   # (username, password) for authentication
    verify_certs: bool = True,     # Whether to verify SSL certificates
    ca_certs: str | None = None,   # Path to CA certificate file
    timeout: int = 30,             # Connection timeout in seconds
    max_retries: int = 3,          # Maximum retry attempts on failure
    retry_on_timeout: bool = True  # Whether to retry on timeout
) -> Elasticsearch:
    """Create Elasticsearch client connection"""
```

### 2. Index Management

```python
def create_index(
    client: Elasticsearch,
    index_name: str,               # Index name (lowercase, no spaces)
    mappings: dict,                # Field mappings definition
    settings: dict | None = None,  # Index settings (shards, replicas, etc.)
) -> dict:
    """Create a new index with mappings and settings"""

def delete_index(
    client: Elasticsearch,
    index_name: str,               # Index name to delete
    ignore_unavailable: bool = True # Ignore if index doesn't exist
) -> dict:
    """Delete an index"""

def index_exists(
    client: Elasticsearch,
    index_name: str                # Index name to check
) -> bool:
    """Check if index exists"""
```

### 3. Document Operations

```python
def index_document(
    client: Elasticsearch,
    index_name: str,               # Target index name
    document: dict,                # Document content as JSON-serializable dict
    doc_id: str | None = None,     # Document ID (auto-generated if None)
    refresh: str = "false"         # Refresh policy: "true", "wait_for", "false"
) -> dict:
    """Index a single document"""

def bulk_index(
    client: Elasticsearch,
    index_name: str,               # Target index name
    documents: list[dict],         # List of documents to index
    id_field: str = "id",          # Field name to use as document ID
    chunk_size: int = 500,         # Number of documents per batch
    refresh: str = "false"         # Refresh policy
) -> dict:
    """Bulk index multiple documents efficiently"""

def get_document(
    client: Elasticsearch,
    index_name: str,               # Index name
    doc_id: str,                   # Document ID
    _source: list[str] | None = None # Fields to return (all if None)
) -> dict:
    """Retrieve a document by ID"""

def update_document(
    client: Elasticsearch,
    index_name: str,               # Index name
    doc_id: str,                   # Document ID to update
    partial_doc: dict,             # Fields to update
    refresh: str = "false"         # Refresh policy
) -> dict:
    """Partially update a document"""

def delete_document(
    client: Elasticsearch,
    index_name: str,               # Index name
    doc_id: str,                   # Document ID to delete
    refresh: str = "false"         # Refresh policy
) -> dict:
    """Delete a document by ID"""
```

### 4. Search Operations

```python
def search(
    client: Elasticsearch,
    index_name: str,               # Index name to search
    query: dict,                   # Elasticsearch query DSL
    size: int = 10,                # Number of results to return
    from_: int = 0,                # Offset for pagination
    sort: list[dict] | None = None,# Sorting criteria
    _source: list[str] | None = None,# Fields to return
    highlight: dict | None = None  # Highlight configuration
) -> dict:
    """Execute a search query"""

def multi_match_search(
    client: Elasticsearch,
    index_name: str,               # Index name
    query_text: str,               # Search text
    fields: list[str],             # Fields to search (e.g., ["title^3", "content"])
    size: int = 10,                # Number of results
    fuzziness: str = "AUTO"        # Fuzzy matching tolerance
) -> dict:
    """Multi-field full-text search with boosting"""

def filter_search(
    client: Elasticsearch,
    index_name: str,               # Index name
    must: list[dict] | None = None,    # Conditions that must match
    should: list[dict] | None = None,  # Conditions that should match
    must_not: list[dict] | None = None,# Conditions that must not match
    filter: list[dict] | None = None,  # Filter conditions (no scoring)
    size: int = 10                     # Number of results
) -> dict:
    """Boolean query with multiple conditions"""
```

### 5. Aggregation Operations

```python
def aggregate(
    client: Elasticsearch,
    index_name: str,               # Index name
    aggs: dict,                    # Aggregation definition
    query: dict | None = None,     # Optional query to filter documents
    size: int = 0                  # Number of documents to return (0 for aggs only)
) -> dict:
    """Execute aggregation queries (stats, grouping, etc.)"""
```

### 6. Runtime Interface (Match3 Project)

```python
from typing import Protocol

class IElasticsearchClient(Protocol):
    """Elasticsearch client interface for dependency injection"""
    
    def search(
        self,
        index: str,                # Index name
        query: dict,               # Query DSL
        size: int = 10,
        from_: int = 0,
        **kwargs
    ) -> dict:
        """Execute search query"""
    
    def index(
        self,
        index: str,                # Index name
        document: dict,            # Document to index
        id: str | None = None,
        refresh: str = "false",
        **kwargs
    ) -> dict:
        """Index a document"""
    
    def bulk(
        self,
        operations: list[dict],    # Bulk operations
        refresh: str = "false",
        **kwargs
    ) -> dict:
        """Execute bulk operations"""
    
    def indices_create(
        self,
        index: str,                # Index name
        body: dict | None = None,  # Mappings and settings
        **kwargs
    ) -> dict:
        """Create an index"""
    
    def indices_delete(
        self,
        index: str,                # Index name
        ignore_unavailable: bool = True,
        **kwargs
    ) -> dict:
        """Delete an index"""
```

---

## Detailed Interface Usage

### 1. Client Connection

#### Basic Connection

```python
from elasticsearch import Elasticsearch

# Local development
client = Elasticsearch(
    hosts=["http://localhost:9200"],
    basic_auth=("elastic", "password"),  # Username and password
    verify_certs=False,                  # Disable SSL verification for local dev
    timeout=30,                          # 30s timeout
    max_retries=3,                       # Retry up to 3 times
    retry_on_timeout=True                # Retry on timeout errors
)

# Production with SSL
client = Elasticsearch(
    hosts=["https://es-node1:9200", "https://es-node2:9200"],
    basic_auth=("elastic", "prod_password"),
    verify_certs=True,                   # Enable SSL verification
    ca_certs="/path/to/ca.crt",          # Path to CA certificate
    timeout=60,
    max_retries=5
)
```

#### Cloud Connection (Elastic Cloud)

```python
from elasticsearch import Elasticsearch

client = Elasticsearch(
    cloud_id="deployment-name:encoded-cloud-id",  # Cloud deployment ID
    api_key=("api_key_id", "api_key_secret"),    # API key authentication
    timeout=30
)
```

#### Health Check

```python
# Check cluster health
health = client.cluster.health()
print(f"Cluster status: {health['status']}")  # green/yellow/red

# Check if client is connected
if client.ping():
    print("Connected to Elasticsearch")
```

---

### 2. Index Management

#### Create Index with Mappings

```python
# Define field mappings
mappings = {
    "properties": {
        "title": {
            "type": "text",                    # Full-text field
            "analyzer": "standard",            # Tokenizer for indexing
            "search_analyzer": "standard",     # Tokenizer for searching
            "fields": {
                "keyword": {                   # Keyword sub-field for exact match
                    "type": "keyword",
                    "ignore_above": 256        # Max length for keyword
                }
            }
        },
        "content": {
            "type": "text",
            "analyzer": "english"              # Language-specific analyzer
        },
        "category": {
            "type": "keyword"                  # Exact match field (no tokenization)
        },
        "tags": {
            "type": "keyword"                  # Array of keywords
        },
        "created_at": {
            "type": "date",                    # Date field
            "format": "strict_date_optional_time||epoch_millis"
        },
        "view_count": {
            "type": "integer"                  # Numeric field
        },
        "metadata": {
            "type": "object",                  # Nested object
            "enabled": True                    # Enable indexing of nested fields
        }
    }
}

# Index settings
settings = {
    "number_of_shards": 3,                     # Number of primary shards
    "number_of_replicas": 2,                   # Number of replica shards
    "refresh_interval": "1s",                  # Refresh frequency
    "analysis": {
        "analyzer": {
            "my_custom_analyzer": {            # Custom analyzer
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "stop", "snowball"]
            }
        }
    }
}

# Create index
response = client.indices.create(
    index="articles",
    mappings=mappings,
    settings=settings
)
print(f"Index created: {response['acknowledged']}")
```

#### Update Mappings (Add New Fields)

```python
# Add new fields to existing index
new_mappings = {
    "properties": {
        "author": {
            "type": "keyword"
        },
        "likes": {
            "type": "integer"
        }
    }
}

client.indices.put_mapping(
    index="articles",
    body=new_mappings
)
```

#### Delete Index

```python
client.indices.delete(
    index="articles",
    ignore_unavailable=True  # Don't raise error if index doesn't exist
)
```

#### Index Templates

```python
# Create index template for auto-creating indices
template = {
    "index_patterns": ["logs-*"],              # Apply to indices matching pattern
    "template": {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 1
        },
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "message": {"type": "text"},
                "level": {"type": "keyword"}
            }
        }
    }
}

client.indices.put_index_template(
    name="logs_template",
    body=template
)
```

---

### 3. Document Operations

#### Index Single Document

```python
# Index with auto-generated ID
doc = {
    "title": "Introduction to Elasticsearch",
    "content": "Elasticsearch is a distributed search engine...",
    "category": "tutorial",
    "tags": ["search", "elasticsearch"],
    "created_at": "2026-04-22T15:30:00Z",
    "view_count": 0
}

response = client.index(
    index="articles",
    document=doc,
    refresh="wait_for"  # Wait for refresh before returning (makes doc searchable)
)
print(f"Document ID: {response['_id']}")
```

#### Index with Custom ID

```python
client.index(
    index="articles",
    id="article-001",     # Custom document ID
    document=doc
)
```

#### Bulk Index Documents

```python
from elasticsearch.helpers import bulk

# Prepare bulk actions
documents = [
    {
        "_index": "articles",
        "_id": f"doc-{i}",
        "_source": {
            "title": f"Article {i}",
            "content": f"Content for article {i}",
            "view_count": i * 10
        }
    }
    for i in range(1000)
]

# Bulk index
success, failed = bulk(
    client,
    documents,
    chunk_size=500,           # Send 500 docs per request
    request_timeout=60,       # Timeout per request
    raise_on_error=False      # Continue on partial failures
)
print(f"Indexed: {success}, Failed: {len(failed)}")
```

#### Get Document by ID

```python
doc = client.get(
    index="articles",
    id="article-001",
    _source=["title", "created_at"]  # Only return specific fields
)
print(doc["_source"])
```

#### Update Document

```python
# Partial update
client.update(
    index="articles",
    id="article-001",
    doc={
        "view_count": 100,           # Update specific fields
        "last_viewed": "2026-04-22T16:00:00Z"
    }
)

# Update with script
client.update(
    index="articles",
    id="article-001",
    script={
        "source": "ctx._source.view_count += params.increment",
        "params": {"increment": 1}   # Increment view count by 1
    }
)
```

#### Delete Document

```python
client.delete(
    index="articles",
    id="article-001"
)
```

---

### 4. Search Operations

#### Basic Full-Text Search

```python
# Simple match query
response = client.search(
    index="articles",
    query={
        "match": {
            "content": {
                "query": "elasticsearch tutorial",  # Search text
                "operator": "and"                   # Both terms must match
            }
        }
    },
    size=10,                                        # Return top 10 results
    from_=0                                         # Offset for pagination
)

for hit in response["hits"]["hits"]:
    print(f"Score: {hit['_score']}, Title: {hit['_source']['title']}")
```

#### Multi-Field Search with Boosting

```python
# Search across multiple fields with different weights
response = client.search(
    index="articles",
    query={
        "multi_match": {
            "query": "python programming",
            "fields": [
                "title^3",      # Title has 3x weight
                "content^1",    # Content has 1x weight
                "tags^2"        # Tags have 2x weight
            ],
            "type": "best_fields",  # Use best matching field's score
            "fuzziness": "AUTO"     # Allow fuzzy matching
        }
    },
    size=20
)
```

#### Boolean Query (Complex Filtering)

```python
response = client.search(
    index="articles",
    query={
        "bool": {
            "must": [                              # Conditions that MUST match
                {"match": {"content": "python"}}
            ],
            "should": [                            # Conditions that SHOULD match (boost score)
                {"match": {"tags": "tutorial"}},
                {"match": {"category": "programming"}}
            ],
            "must_not": [                          # Conditions that MUST NOT match
                {"term": {"status": "draft"}}
            ],
            "filter": [                            # Filter without affecting score
                {"range": {"view_count": {"gte": 100}}},
                {"term": {"category": "tech"}}
            ]
        }
    },
    size=10
)
```

#### Range Queries

```python
# Date range
response = client.search(
    index="articles",
    query={
        "range": {
            "created_at": {
                "gte": "2026-01-01",               # Greater than or equal
                "lte": "2026-04-22",               # Less than or equal
                "format": "yyyy-MM-dd"
            }
        }
    }
)

# Numeric range
response = client.search(
    index="articles",
    query={
        "range": {
            "view_count": {
                "gte": 1000,
                "lt": 10000
            }
        }
    }
)
```

#### Prefix and Wildcard Search

```python
# Prefix search (efficient)
response = client.search(
    index="articles",
    query={
        "prefix": {
            "title": {
                "value": "intro"                   # Matches "introduction", "intro to", etc.
            }
        }
    }
)

# Wildcard search (slower, use sparingly)
response = client.search(
    index="articles",
    query={
        "wildcard": {
            "title": {
                "value": "elastic*search"          # * matches any characters
            }
        }
    }
)
```

#### Highlighting Search Results

```python
response = client.search(
    index="articles",
    query={
        "match": {"content": "elasticsearch"}
    },
    highlight={
        "fields": {
            "content": {
                "pre_tags": ["<strong>"],          # HTML tag before match
                "post_tags": ["</strong>"],        # HTML tag after match
                "fragment_size": 150,              # Snippet length
                "number_of_fragments": 3           # Max number of snippets
            }
        }
    }
)

for hit in response["hits"]["hits"]:
    print(hit["highlight"]["content"])  # Highlighted snippets
```

---

### 5. Aggregation Operations

#### Basic Aggregations

```python
# Count by category
response = client.search(
    index="articles",
    size=0,  # Don't return documents, only aggregations
    aggs={
        "by_category": {
            "terms": {
                "field": "category",               # Group by category
                "size": 10                         # Return top 10 categories
            }
        }
    }
)

for bucket in response["aggregations"]["by_category"]["buckets"]:
    print(f"{bucket['key']}: {bucket['doc_count']} articles")
```

#### Nested Aggregations

```python
# Category distribution + avg view count per category
response = client.search(
    index="articles",
    size=0,
    aggs={
        "by_category": {
            "terms": {"field": "category"},
            "aggs": {                              # Nested aggregation
                "avg_views": {
                    "avg": {"field": "view_count"} # Average view count
                },
                "total_views": {
                    "sum": {"field": "view_count"} # Total view count
                }
            }
        }
    }
)
```

#### Date Histogram

```python
# Articles per month
response = client.search(
    index="articles",
    size=0,
    aggs={
        "articles_over_time": {
            "date_histogram": {
                "field": "created_at",
                "calendar_interval": "month",      # Group by month
                "format": "yyyy-MM"
            }
        }
    }
)
```

#### Statistics Aggregation

```python
# Statistics on view counts
response = client.search(
    index="articles",
    size=0,
    aggs={
        "view_stats": {
            "stats": {
                "field": "view_count"              # Count, min, max, avg, sum
            }
        }
    }
)

stats = response["aggregations"]["view_stats"]
print(f"Min: {stats['min']}, Max: {stats['max']}, Avg: {stats['avg']}")
```

---

### 6. Runtime Integration (Match3 Project)

#### Runtime Interface Implementation

```python
from elasticsearch import Elasticsearch
from typing import Protocol

class IElasticsearchClient(Protocol):
    """Elasticsearch client interface for dependency injection"""
    
    def search(self, index: str, query: dict, size: int = 10, from_: int = 0, **kwargs) -> dict: ...
    def index(self, index: str, document: dict, id: str | None = None, refresh: str = "false", **kwargs) -> dict: ...
    def bulk(self, operations: list[dict], refresh: str = "false", **kwargs) -> dict: ...
    def indices_create(self, index: str, body: dict | None = None, **kwargs) -> dict: ...
    def indices_delete(self, index: str, ignore_unavailable: bool = True, **kwargs) -> dict: ...

def build_elasticsearch_client(config: ESConfig) -> IElasticsearchClient:
    """Build Elasticsearch client from config"""
    return Elasticsearch(
        hosts=config.hosts,
        basic_auth=(config.username, config.password),
        verify_certs=config.verify_certs,
        ca_certs=config.ca_certs,
        timeout=config.timeout,
        max_retries=config.max_retries,
        retry_on_timeout=True
    )
```

#### Injecting into Runtime

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Match3Runtime:
    """Runtime dependency container (immutable)"""
    
    es_client: IElasticsearchClient  # Elasticsearch client interface
    # ... other dependencies
    
def build_runtime(config: Config) -> Match3Runtime:
    """Build runtime with all dependencies"""
    
    es_client = build_elasticsearch_client(config.elasticsearch)
    
    return Match3Runtime(
        es_client=es_client,
        # ... other dependencies
    )
```

#### Usage in Repository

```python
class ArticleRepository:
    """Repository for article full-text search"""
    
    def __init__(self, runtime: Match3Runtime):
        self._es = runtime.es_client
        self._index = "articles"
    
    async def search_articles(
        self,
        query_text: str,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20
    ) -> list[dict]:
        """Search articles with full-text query"""
        
        # Build query
        must_clauses = [
            {"multi_match": {
                "query": query_text,
                "fields": ["title^3", "content^1", "tags^2"],
                "fuzziness": "AUTO"
            }}
        ]
        
        if category:
            must_clauses.append({"term": {"category": category}})
        
        # Execute search
        response = self._es.search(
            index=self._index,
            query={"bool": {"must": must_clauses}},
            size=page_size,
            from_=(page - 1) * page_size,
            highlight={
                "fields": {
                    "content": {
                        "fragment_size": 150,
                        "number_of_fragments": 2
                    }
                }
            }
        )
        
        # Parse results
        return [
            {
                "id": hit["_id"],
                "score": hit["_score"],
                "title": hit["_source"]["title"],
                "snippet": hit.get("highlight", {}).get("content", [])[0] if hit.get("highlight") else None
            }
            for hit in response["hits"]["hits"]
        ]
    
    async def index_article(self, article: dict) -> str:
        """Index a new article"""
        response = self._es.index(
            index=self._index,
            document=article,
            refresh="wait_for"  # Make searchable immediately
        )
        return response["_id"]
```

---

## Why Elasticsearch v9.3.3?

### ES 9.x 系列主要特性

- **向量搜索增强**: 原生支持稠密向量和稀疏向量
- **时序数据优化**: TSDB 模式改进,降低存储成本
- **ES|QL 查询语言**: 统一日志和时序数据查询
- **性能提升**: 查询速度和索引效率持续优化
- **安全增强**: 基于角色的访问控制 (RBAC) 改进

### 9.3.3 修复和改进 (2026-04-08)

- 修复日志摄取管道的边缘情况
- 优化大规模集群的分片分配性能
- 改进 aggregation 查询的内存使用

### API 稳定性

- **Python 客户端**: elasticsearch-py 9.3.0+ 完全兼容
- **向后兼容**: 9.x 系列 API 保持稳定
- **前向兼容**: 语言客户端支持与更新版本 ES 服务端通信

---

### Key Features in v9.x

1. **Improved Performance**
   - Faster indexing and search speeds
   - Better memory management
   - Optimized aggregations

2. **Enhanced Security**
   - Built-in security features (authentication, authorization)
   - Role-based access control (RBAC)
   - Audit logging

3. **Better Developer Experience**
   - Simplified API
   - Better error messages
   - Improved documentation

4. **Cloud-Native Features**
   - Better Kubernetes integration
   - Auto-scaling support
   - Snapshot lifecycle management

### When to Use Elasticsearch

✅ **Use Elasticsearch when**:
- Full-text search with advanced features (fuzzy, phrase, multi-field)
- Log and event data analysis (ELK stack)
- Aggregations and analytics on large datasets
- Real-time indexing and search requirements

❌ **Don't use Elasticsearch when**:
- Simple exact-match queries (use PostgreSQL)
- Vector similarity search (use Milvus)
- Graph relationships (use Neo4j)
- Primary data store (use PostgreSQL)

---

## Integration with Match3 Architecture

```
┌─────────────────────────────────────────────────┐
│                  FastAPI Layer                  │
│            (Article Search Endpoint)            │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│            ArticleRepository                    │
│  - search_articles()                            │
│  - index_article()                              │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│         Match3Runtime.es_client                 │
│       (IElasticsearchClient Protocol)           │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│          Elasticsearch Cluster                  │
│        (v9.2.8, Full-Text Search)               │
└─────────────────────────────────────────────────┘
```

**Data Flow**:
1. User submits search query via FastAPI
2. Repository builds ES query DSL
3. Runtime provides ES client interface
4. ES executes full-text search and returns results
5. Repository parses and returns formatted results

---

## Configuration Example

```python
from pydantic import BaseModel

class ElasticsearchConfig(BaseModel):
    """Elasticsearch configuration"""
    
    hosts: list[str] = ["http://localhost:9200"]
    username: str = "elastic"
    password: str
    verify_certs: bool = False
    ca_certs: str | None = None
    timeout: int = 30
    max_retries: int = 3
    
    # Index settings
    default_shards: int = 3
    default_replicas: int = 2
    refresh_interval: str = "1s"
```

---

## Best Practices

1. **Index Design**
   - Use keyword fields for exact matches
   - Use text fields for full-text search
   - Don't over-normalize (ES is not a relational DB)

2. **Query Optimization**
   - Use filter context when you don't need scoring
   - Limit `size` and use pagination
   - Avoid deep pagination (use `search_after` instead)

3. **Bulk Operations**
   - Always use bulk API for multiple documents
   - Keep bulk request size reasonable (1000-5000 docs)

4. **Refresh Policy**
   - Use `refresh=false` for better performance
   - Use `refresh=wait_for` when immediate searchability is needed

5. **Monitoring**
   - Monitor cluster health regularly
   - Watch for heap usage and garbage collection
   - Set up alerts for slow queries
