# FullTextSearch Protocol

> **功能**: BM25 关键词检索和聚合  
> **推荐实现**: Elasticsearch v9.3.3 (2026-04-08)  
> **Runtime 接口**: `rt.search: FullTextSearch` (Protocol)

## 📚 相关文档

- **上级文档**: [runtime.md](../runtime.md) - Runtime 系统总览和 Protocol 设计理念
- **实现方案**: [implementation.md](./implementation.md) - Elasticsearch 适配器实现和配置说明
- **版本技术文档**: [versions/](./versions/) - 具体实现库的详细 API 文档
  - [Elasticsearch v9.3.3](./versions/elasticsearch-v9.3.3.md) - 推荐实现

---

## Protocol 定义

### 接口说明

`FullTextSearch` 提供全文搜索能力,用于:
- **BM25 检索**: 基于 BM25 算法的关键词相关性检索
- **聚合分析**: 文档统计和聚合查询
- **混合检索**: 与向量搜索结合的 Hybrid Search

### 主接口定义

```python
from typing import Protocol, Any

class FullTextSearch(Protocol):
    """全文搜索抽象接口 (不依赖任何搜索引擎)"""
    
    def index(
        self,
        index_name: str,
        document: dict[str, Any],
        document_id: str | None = None,
    ) -> str:
        """索引文档
        
        Args:
            index_name: 索引名称
            document: 文档数据
            document_id: 文档 ID (可选,不提供则自动生成)
            
        Returns:
            文档 ID
        """
        ...
    
    def bulk_index(
        self,
        index_name: str,
        documents: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """批量索引文档
        
        Args:
            index_name: 索引名称
            documents: 文档列表,每条必须包含 "_id" 字段
            
        Returns:
            (成功数量, 失败数量)
        """
        ...
    
    def search(
        self,
        index_name: str,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        fields: list[str] | None = None,
    ) -> list[SearchResult]:
        """全文搜索
        
        Args:
            index_name: 索引名称
            query: 搜索查询文本
            limit: 返回结果数量
            filters: 过滤条件 (可选)
            fields: 返回的字段列表 (可选,None 表示返回全部)
            
        Returns:
            搜索结果列表
        """
        ...
    
    def delete(
        self,
        index_name: str,
        document_id: str,
    ) -> bool:
        """删除文档
        
        Args:
            index_name: 索引名称
            document_id: 文档 ID
            
        Returns:
            是否删除成功
        """
        ...
    
    def delete_by_query(
        self,
        index_name: str,
        query: dict[str, Any],
    ) -> int:
        """按查询条件删除文档
        
        Args:
            index_name: 索引名称
            query: 查询条件
            
        Returns:
            删除的文档数量
        """
        ...
    
    def close(self) -> None:
        """关闭连接"""
        ...
```

### 搜索结果 Protocol

```python
from typing import Protocol, Any

class SearchResult(Protocol):
    """搜索结果 (单条)"""
    
    @property
    def id(self) -> str:
        """文档 ID"""
        ...
    
    @property
    def score(self) -> float:
        """相关性分数"""
        ...
    
    @property
    def source(self) -> dict[str, Any]:
        """文档源数据"""
        ...
```

---

## 使用示例

### 业务代码 (索引)

```python
from runtime import Runtime

def index_document(
    rt: Runtime,
    doc_id: int,
    text: str,
    metadata: dict,
) -> None:
    """索引文档 (不知道底层是 ES 还是其他搜索引擎)"""
    
    rt.search.index(
        index_name="documents",
        document={
            "text": text,
            "metadata": metadata,
            "created_at": datetime.now().isoformat(),
        },
        document_id=str(doc_id),
    )
```

### 业务代码 (搜索)

```python
def keyword_search(
    rt: Runtime,
    query: str,
    top_k: int = 20,
) -> list[dict]:
    """关键词搜索 (BM25)"""
    
    results = rt.search.search(
        index_name="documents",
        query=query,
        limit=top_k,
        fields=["text", "metadata"],
    )
    
    return [
        {
            "id": r.id,
            "score": r.score,
            "text": r.source["text"],
            "metadata": r.source["metadata"],
        }
        for r in results
    ]
```

### 业务代码 (批量索引)

```python
def batch_index_documents(
    rt: Runtime,
    documents: list[dict],
) -> None:
    """批量索引文档"""
    
    # 添加 _id 字段
    docs_with_id = [
        {"_id": str(doc["id"]), **doc}
        for doc in documents
    ]
    
    success, failed = rt.search.bulk_index(
        index_name="documents",
        documents=docs_with_id,
    )
    
    print(f"Indexed {success} documents, {failed} failed")
```

### 单元测试

```python
from unittest.mock import MagicMock, Mock
from runtime import Runtime

def test_keyword_search():
    # Mock 搜索引擎
    mock_result = Mock()
    mock_result.id = "123"
    mock_result.score = 0.85
    mock_result.source = {
        "text": "Test document",
        "metadata": {"author": "Alice"},
    }
    
    mock_search = MagicMock()
    mock_search.search.return_value = [mock_result]
    
    # 创建测试 Runtime
    rt = Runtime(
        cache=MagicMock(),
        queue=MagicMock(),
        vector_db=MagicMock(),
        graph_db=MagicMock(),
        db=MagicMock(),
        search=mock_search,
        storage=MagicMock(),
    )
    
    # 测试
    results = keyword_search(rt, "test query")
    
    assert len(results) == 1
    assert results[0]["text"] == "Test document"
    mock_search.search.assert_called_once()
```

---

## 设计说明

### 查询语法的抽象

不同搜索引擎的查询语法不同:
- Elasticsearch: Query DSL (JSON)
- Solr: Lucene 查询语法
- MeiliSearch: 简化的查询字符串

**两种方案**:

#### 方案 1: 统一使用简单查询字符串 (推荐)
```python
def search(self, query: str, ...) -> ...
```

适配器负责将查询字符串转换为目标引擎的查询格式。

#### 方案 2: 支持原生查询
```python
def search(self, query: str | dict, ...) -> ...
```

允许传入引擎特定的查询对象 (如 ES 的 Query DSL)。

**推荐方案 1**: 大多数场景下简单查询字符串足够。

### 高级功能

Elasticsearch 有许多高级功能 (聚合、高亮、建议等):

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class AdvancedSearch(Protocol):
    """高级搜索功能 (可选)"""
    
    def aggregate(
        self,
        index_name: str,
        aggregations: dict,
    ) -> dict:
        """聚合查询"""
        ...
    
    def highlight(
        self,
        index_name: str,
        query: str,
        fields: list[str],
    ) -> list[SearchResult]:
        """搜索并高亮"""
        ...
```

使用 `@runtime_checkable` 检查是否支持。

### 索引管理

索引的创建和配置通常在应用启动时完成,不放入 Runtime:

```python
# 初始化脚本
def init_search_indices(es_client: Elasticsearch):
    es_client.indices.create(
        index="documents",
        body={
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "metadata": {"type": "object"},
                }
            }
        }
    )
```

### 异步支持

如果使用异步 Elasticsearch 客户端:

```python
from elasticsearch import AsyncElasticsearch

class FullTextSearch(Protocol):
    async def search(...) -> list[SearchResult]: ...
```

---

## 扩展性

### 切换到 OpenSearch

```python
from opensearchpy import OpenSearch

class OpenSearchAdapter:
    """OpenSearch 适配器 (实现 FullTextSearch Protocol)"""
    
    def __init__(self, client: OpenSearch):
        self._client = client
    
    def search(
        self,
        index_name: str,
        query: str,
        limit: int = 10,
        filters: dict | None = None,
        fields: list[str] | None = None,
    ) -> list[SearchResult]:
        # OpenSearch 的 API 与 Elasticsearch 几乎完全兼容
        response = self._client.search(
            index=index_name,
            body={
                "query": {"match": {"text": query}},
                "size": limit,
            }
        )
        
        return [OpenSearchResult(hit) for hit in response["hits"]["hits"]]
    
    # ... 其他方法类似
```

**无需修改 Runtime 或业务代码！**

---

**创建时间**: 2026-04-23  
**最后更新**: 2026-04-23  
**版本**: 2.0
