# VectorDatabase Protocol

> **功能**: 混合向量搜索 (稠密+稀疏向量)  
> **推荐实现**: Milvus v2.6.14 (2026-04-07)  
> **Runtime 接口**: `rt.vector_db: VectorDatabase` (Protocol)

## 📚 相关文档

- **上级文档**: [runtime.md](../runtime.md) - Runtime 系统总览和 Protocol 设计理念
- **实现方案**: [implementation.md](./implementation.md) - Milvus 适配器实现和配置说明
- **版本技术文档**: [versions/](./versions/) - 具体实现库的详细 API 文档
  - [Milvus v2.6.14](./versions/milvus-v2.6.14.md) - 推荐实现

---

## Protocol 定义

### 接口说明

`VectorDatabase` 提供向量检索能力,用于:
- **语义搜索**: 基于稠密向量 (Dense Vector) 的语义相似度检索
- **混合搜索**: 结合稠密向量和稀疏向量 (Sparse Vector) 的混合检索
- **RAG 检索**: 为 Retrieval-Augmented Generation 提供文档检索

### 主接口定义

```python
from typing import Protocol, Any

class VectorDatabase(Protocol):
    """向量数据库抽象接口 (不依赖任何向量库)"""
    
    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        filter_expr: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        """向量检索
        
        Args:
            collection_name: Collection 名称
            query_vector: 查询向量 (稠密向量)
            limit: 返回结果数量
            filter_expr: 过滤表达式 (可选)
            output_fields: 返回的字段列表 (可选)
            
        Returns:
            搜索结果列表
        """
        ...
    
    def hybrid_search(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: dict[int, float],
        limit: int = 10,
        reranker: str = "rrf",
        output_fields: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        """混合向量检索 (稠密+稀疏)
        
        Args:
            collection_name: Collection 名称
            dense_vector: 稠密向量
            sparse_vector: 稀疏向量 ({token_id: weight})
            limit: 返回结果数量
            reranker: 重排序策略 (rrf/weighted)
            output_fields: 返回的字段列表 (可选)
            
        Returns:
            搜索结果列表
        """
        ...
    
    def insert(
        self,
        collection_name: str,
        data: list[dict[str, Any]],
    ) -> list[int | str]:
        """插入向量数据
        
        Args:
            collection_name: Collection 名称
            data: 数据列表,每条包含 id、向量、其他字段
            
        Returns:
            插入的 ID 列表
        """
        ...
    
    def delete(
        self,
        collection_name: str,
        ids: list[int | str],
    ) -> None:
        """删除向量数据
        
        Args:
            collection_name: Collection 名称
            ids: 要删除的 ID 列表
        """
        ...
    
    def close(self) -> None:
        """关闭连接"""
        ...
```

### 搜索结果 Protocol

```python
from typing import Protocol, Any

class VectorSearchResult(Protocol):
    """向量搜索结果 (单条)"""
    
    @property
    def id(self) -> int | str:
        """文档 ID"""
        ...
    
    @property
    def distance(self) -> float:
        """相似度距离"""
        ...
    
    @property
    def entity(self) -> dict[str, Any]:
        """实体字段 (如 text、metadata)"""
        ...
```

---

## 使用示例

### 业务代码 (语义搜索)

```python
from runtime import Runtime

def semantic_search(rt: Runtime, query: str, embedder: Embedder) -> list[str]:
    """语义搜索 (不知道底层是 Milvus 还是其他向量库)"""
    
    # 生成查询向量
    query_vector = embedder.embed([query])[0]
    
    # 向量检索
    results = rt.vector_db.search(
        collection_name="documents",
        query_vector=query_vector,
        limit=10,
        output_fields=["text"],
    )
    
    return [r.entity["text"] for r in results]
```

### 业务代码 (混合搜索)

```python
def hybrid_search(
    rt: Runtime,
    query: str,
    dense_embedder: Embedder,
    sparse_embedder: SparseEmbedder,
) -> list[dict]:
    """混合搜索 (稠密 + 稀疏)"""
    
    # 生成稠密向量
    dense_vector = dense_embedder.embed([query])[0]
    
    # 生成稀疏向量
    sparse_vector = sparse_embedder.encode([query])[0]
    
    # 混合检索
    results = rt.vector_db.hybrid_search(
        collection_name="documents",
        dense_vector=dense_vector,
        sparse_vector=sparse_vector,
        limit=20,
        reranker="rrf",
        output_fields=["text", "metadata"],
    )
    
    return [
        {
            "id": r.id,
            "distance": r.distance,
            "text": r.entity["text"],
            "metadata": r.entity["metadata"],
        }
        for r in results
    ]
```

### 单元测试

```python
from unittest.mock import MagicMock
from runtime import Runtime

def test_semantic_search():
    # Mock 向量数据库
    mock_vector_db = MagicMock()
    mock_result = MagicMock()
    mock_result.entity = {"text": "Test document"}
    mock_vector_db.search.return_value = [mock_result]
    
    # 创建测试 Runtime
    rt = Runtime(
        cache=MagicMock(),
        queue=MagicMock(),
        vector_db=mock_vector_db,
        graph_db=MagicMock(),
        db=MagicMock(),
        search=MagicMock(),
        storage=MagicMock(),
    )
    
    # 测试
    results = semantic_search(rt, "test query", mock_embedder)
    
    assert results == ["Test document"]
    mock_vector_db.search.assert_called_once()
```

---

## 设计说明

### 抽象粒度

- ✅ **好的抽象**: `search(query_vector: list[float])` (通用)
- ❌ **过度抽象**: `search(query: pymilvus.AnnSearchRequest)` (依赖具体库)

### 返回值设计

使用 Protocol 定义返回值类型:

```python
class VectorSearchResult(Protocol):
    """向量搜索结果接口"""
    id: int | str
    distance: float
    entity: dict[str, Any]
```

避免直接返回 `pymilvus.SearchResult`。

### 特定功能的处理

某些向量库可能有独特功能 (如 Milvus 的混合搜索):

- **方案 1**: 在 Protocol 中定义可选方法
- **方案 2**: 使用 `@runtime_checkable` 检查是否支持

```python
from typing import runtime_checkable

@runtime_checkable
class HybridSearchCapable(Protocol):
    def hybrid_search(...) -> ...: ...

# 使用时检查
if isinstance(rt.vector_db, HybridSearchCapable):
    results = rt.vector_db.hybrid_search(...)
else:
    # 降级到普通搜索
    results = rt.vector_db.search(...)
```

---

## 扩展性

### 切换到 Qdrant

```python
from qdrant_client import QdrantClient

class QdrantAdapter:
    """Qdrant 适配器 (实现 VectorDatabase Protocol)"""
    
    def __init__(self, client: QdrantClient):
        self._client = client
    
    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        filter_expr: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        # Qdrant 的搜索逻辑
        results = self._client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
        )
        
        return [QdrantSearchResult(r) for r in results]
    
    # ... 其他方法类似
```

**无需修改 Runtime 或业务代码！**

---

**创建时间**: 2026-04-23  
**最后更新**: 2026-04-23  
**版本**: 2.0
