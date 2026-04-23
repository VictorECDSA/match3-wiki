# Milvus v2.6.14

## 版本信息

- **当前版本**: 2.6.14
- **发布时间**: 2026-04-07
- **Python 客户端**: pymilvus 2.6.14+
- **官方文档**: https://milvus.io/docs

## 选型理由

- 开源向量数据库，专为 AI/ML 场景设计
- **支持稠密+稀疏混合向量搜索**（关键！）
- 十亿级向量毫秒级检索性能
- 多种索引算法（HNSW、IVF_FLAT、DiskANN 等）
- 云原生架构，支持水平扩展
- 与主流 AI 框架无缝集成

---

## 接口清单

### 1. 客户端创建

```python
def MilvusClient(
    uri: str,                    # 连接地址，格式: http://host:port 或 Milvus Standalone URI
    token: str | None = None,    # 认证 token（可选）
    timeout: float | None = None, # 请求超时时间（秒）
) -> MilvusClient:
    """创建 Milvus 客户端实例"""
```

**返回**: `MilvusClient` 对象

---

### 2. Collection 管理

```python
def create_collection(
    collection_name: str,             # Collection 名称
    dimension: int,                   # 向量维度
    metric_type: str = "COSINE",     # 相似度度量: COSINE, L2, IP
    index_type: str = "HNSW",        # 索引类型: HNSW, IVF_FLAT, AUTOINDEX
    index_params: dict | None = None, # 索引参数（可选）
    schema: CollectionSchema | None = None,  # 自定义 Schema（高级用法）
) -> None:
    """创建 Collection（类似数据库的表）"""

def has_collection(collection_name: str) -> bool:
    """检查 Collection 是否存在"""

def drop_collection(collection_name: str) -> None:
    """删除 Collection"""

def list_collections() -> list[str]:
    """列出所有 Collection 名称"""
```

---

### 3. 数据插入

```python
def insert(
    collection_name: str,        # Collection 名称
    data: list[dict],           # 数据列表，每个 dict 包含 id、vector、其他字段
) -> dict:
    """
    插入向量数据
    
    Args:
        collection_name: Collection 名称
        data: 数据列表，示例:
            [
                {"id": 1, "vector": [0.1, 0.2, ...], "text": "...", "meta": {...}},
                {"id": 2, "vector": [0.3, 0.4, ...], "text": "...", "meta": {...}},
            ]
    
    Returns:
        dict: 插入结果，包含 insert_count、ids 等信息
    """
```

---

### 4. 向量搜索

```python
def search(
    collection_name: str,                # Collection 名称
    data: list[list[float]],            # 查询向量列表（支持批量查询）
    limit: int = 10,                    # 返回 Top-K 结果数量
    filter: str | None = None,          # 标量字段过滤表达式（可选）
    output_fields: list[str] | None = None,  # 返回的字段列表
    search_params: dict | None = None,  # 搜索参数（可选）
    anns_field: str | None = None,      # 向量字段名（多向量场景必需）
) -> list[list[dict]]:
    """
    向量相似度搜索
    
    Args:
        collection_name: Collection 名称
        data: 查询向量列表，支持批量查询
        limit: 每个查询返回的最相似结果数量
        filter: 标量字段过滤，例如: "chunk_id in [1, 2, 3]"
        output_fields: 返回的字段，例如: ["text", "metadata"]
        search_params: 搜索参数，例如: {"ef": 64} (HNSW)
        anns_field: 向量字段名称，在多向量 Collection 中必须指定
    
    Returns:
        list[list[dict]]: 搜索结果，每个查询返回一个结果列表
            [
                [  # 第1个查询的结果
                    {"id": 123, "distance": 0.95, "entity": {"text": "..."}},
                    {"id": 456, "distance": 0.89, "entity": {"text": "..."}},
                ],
                [  # 第2个查询的结果
                    ...
                ],
            ]
    """
```

---

### 5. 混合搜索（稠密+稀疏）

```python
def hybrid_search(
    collection_name: str,                    # Collection 名称
    data: list[dict],                       # 查询向量列表
        # 示例: [{"dense": [0.1, 0.2, ...], "sparse": {0: 0.5, 3: 0.8}}]
    limit: int = 10,                        # 返回 Top-K 结果数量
    reranker: str = "rrf",                  # 重排序策略: rrf（默认）, weighted
    reranker_params: dict | None = None,    # 重排序参数
    filter: str | None = None,              # 标量字段过滤
    output_fields: list[str] | None = None, # 返回的字段列表
) -> list[list[dict]]:
    """
    混合向量搜索（稠密向量 + 稀疏向量）
    
    Args:
        data: 包含 dense 和 sparse 向量的查询数据
        reranker: 重排序算法
            - "rrf": Reciprocal Rank Fusion（默认）
            - "weighted": 加权融合
        reranker_params: 重排序参数，示例:
            - RRF: {"k": 60}
            - Weighted: {"weights": [0.7, 0.3]}  # [dense权重, sparse权重]
    
    Returns:
        list[list[dict]]: 融合后的搜索结果
    """
```

---

### 6. 数据查询

```python
def query(
    collection_name: str,                # Collection 名称
    filter: str,                         # 标量字段过滤表达式（必需）
    output_fields: list[str] | None = None,  # 返回的字段列表
    limit: int | None = None,            # 返回数量限制（可选）
) -> list[dict]:
    """
    按标量字段查询（不使用向量）
    
    Args:
        filter: 过滤表达式，示例:
            - "id in [1, 2, 3]"
            - "chunk_id == 100"
            - "metadata['source'] == 'wiki'"
    
    Returns:
        list[dict]: 查询结果列表
    """
```

---

### 7. 数据删除

```python
def delete(
    collection_name: str,   # Collection 名称
    filter: str,           # 删除条件表达式
) -> dict:
    """
    按条件删除数据
    
    Args:
        filter: 删除条件，示例:
            - "id in [1, 2, 3]"
            - "chunk_id < 1000"
    
    Returns:
        dict: 删除结果，包含 delete_count 等信息
    """
```

---

## 详细用法

### 1. 客户端创建

在 `Match3Runtime` 中创建客户端：

```python
from pymilvus import MilvusClient

# 从环境变量读取连接地址
milvus_client = MilvusClient(
    uri=env.MILVUS_URI,  # 例如: "http://localhost:19530"
    timeout=30.0,         # 请求超时 30 秒
)
```

**URI 格式**:
- Standalone: `http://host:port`
- Cluster: `http://host:19530`
- Milvus Lite (嵌入式): `./milvus_lite.db`

---

### 2. Collection 创建

#### 简单模式（自动 Schema）

```python
# 创建 Collection - 稠密向量
client.create_collection(
    collection_name="match3_dense",
    dimension=1536,          # OpenAI text-embedding-3-small
    metric_type="COSINE",    # 余弦相似度
    index_type="HNSW",       # HNSW 索引（推荐）
    index_params={
        "M": 16,             # HNSW 参数：每个节点的邻居数
        "efConstruction": 256, # 构建时的搜索深度
    },
)
```

#### 混合向量模式（稠密+稀疏）

```python
from pymilvus import (
    MilvusClient,
    DataType,
    CollectionSchema,
    FieldSchema,
)

# 定义 Schema
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True),
    FieldSchema(name="chunk_id", dtype=DataType.INT64),  # 关联的 Chunk ID
    FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=1536),  # 稠密向量
    FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),    # 稀疏向量
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),       # 文本内容
]

schema = CollectionSchema(
    fields=fields,
    description="Match3 hybrid vector collection",
)

# 创建 Collection
client.create_collection(
    collection_name="match3_hybrid",
    schema=schema,
)

# 为稠密向量创建索引
client.create_index(
    collection_name="match3_hybrid",
    field_name="dense_vector",
    index_type="HNSW",
    metric_type="COSINE",
    params={"M": 16, "efConstruction": 256},
)

# 为稀疏向量创建索引
client.create_index(
    collection_name="match3_hybrid",
    field_name="sparse_vector",
    index_type="SPARSE_INVERTED_INDEX",  # 稀疏向量专用索引
    metric_type="IP",                    # 内积（Inner Product）
)
```

---

### 3. 数据插入

#### 稠密向量插入

```python
# 准备数据
data = [
    {
        "id": 1,
        "vector": embedder.embed(["Hello world"])[0],  # 1536维向量
        "chunk_id": 100,
        "text": "Hello world",
        "metadata": {"source": "doc1.pdf", "page": 1},
    },
    {
        "id": 2,
        "vector": embedder.embed(["Machine learning"])[0],
        "chunk_id": 101,
        "text": "Machine learning",
        "metadata": {"source": "doc2.pdf", "page": 5},
    },
]

# 插入数据
result = client.insert(
    collection_name="match3_dense",
    data=data,
)

print(f"插入了 {result['insert_count']} 条数据")
```

#### 混合向量插入（稠密+稀疏）

```python
# 获取稠密+稀疏向量
dense_vecs, sparse_vecs = embedder.embed_both(["Hello world", "AI research"])

# 构建数据
data = [
    {
        "id": 1,
        "chunk_id": 100,
        "dense_vector": dense_vecs[0],   # list[float]
        "sparse_vector": sparse_vecs[0],  # dict[int, float]
        "text": "Hello world",
    },
    {
        "id": 2,
        "chunk_id": 101,
        "dense_vector": dense_vecs[1],
        "sparse_vector": sparse_vecs[1],
        "text": "AI research",
    },
]

# 插入
client.insert(collection_name="match3_hybrid", data=data)
```

**稀疏向量格式**:
```python
# 稀疏向量示例：词ID -> 权重
sparse_vector = {
    0: 0.5,    # 词 0 的权重
    3: 0.8,    # 词 3 的权重
    17: 0.3,   # 词 17 的权重
}
```

---

### 4. 向量搜索

#### 基础搜索

```python
# 查询向量
query_text = "What is machine learning?"
query_vector = embedder.embed([query_text])[0]

# 搜索
results = client.search(
    collection_name="match3_dense",
    data=[query_vector],        # 支持批量查询
    limit=10,                   # Top-10
    output_fields=["text", "chunk_id", "metadata"],
)

# 处理结果
for hit in results[0]:  # results[0] 是第一个查询的结果
    print(f"ID: {hit['id']}, Score: {hit['distance']:.4f}")
    print(f"Text: {hit['entity']['text']}")
    print(f"Metadata: {hit['entity']['metadata']}")
```

#### 带过滤的搜索

```python
# 只搜索特定 Chunk
results = client.search(
    collection_name="match3_dense",
    data=[query_vector],
    limit=10,
    filter="chunk_id in [100, 101, 102]",  # 标量字段过滤
    output_fields=["text"],
)
```

#### 批量搜索

```python
# 一次查询多个向量
query_texts = ["What is AI?", "How does NLP work?"]
query_vectors = embedder.embed(query_texts)

results = client.search(
    collection_name="match3_dense",
    data=query_vectors,  # 多个查询向量
    limit=5,
)

# 遍历每个查询的结果
for i, query_result in enumerate(results):
    print(f"\nQuery {i+1}: {query_texts[i]}")
    for hit in query_result:
        print(f"  - {hit['entity']['text']} (score={hit['distance']:.4f})")
```

---

### 5. 混合搜索（稠密+稀疏）

**Match3 的核心检索能力！**

```python
# 准备查询
query_text = "What is retrieval augmented generation?"
dense_vec, sparse_vec = embedder.embed_both([query_text])

# 混合搜索
results = client.hybrid_search(
    collection_name="match3_hybrid",
    data=[
        {
            "dense": dense_vec[0],   # 稠密向量
            "sparse": sparse_vec[0],  # 稀疏向量
        }
    ],
    limit=20,
    reranker="rrf",              # Reciprocal Rank Fusion
    reranker_params={"k": 60},   # RRF 参数
    output_fields=["text", "chunk_id"],
)

# 结果已经融合并重排序
for hit in results[0]:
    print(f"ID: {hit['id']}, Score: {hit['distance']:.4f}")
    print(f"Text: {hit['entity']['text']}\n")
```

**RRF（Reciprocal Rank Fusion）原理**:
```
score(item) = Σ [1 / (k + rank_in_list_i)]

其中：
- k: 常数，通常为 60
- rank_in_list_i: 该item在第i个排序列表中的排名
```

**加权融合模式**:

```python
results = client.hybrid_search(
    collection_name="match3_hybrid",
    data=[{"dense": dense_vec[0], "sparse": sparse_vec[0]}],
    limit=20,
    reranker="weighted",
    reranker_params={"weights": [0.7, 0.3]},  # 70% dense + 30% sparse
    output_fields=["text"],
)
```

---

### 6. 数据查询（非向量）

```python
# 按 ID 查询
results = client.query(
    collection_name="match3_hybrid",
    filter="id in [1, 2, 3]",
    output_fields=["text", "chunk_id"],
)

for item in results:
    print(item)
```

---

### 7. 数据删除

```python
# 按 ID 删除
client.delete(
    collection_name="match3_hybrid",
    filter="id in [1, 2, 3]",
)

# 按条件删除（例如清理旧数据）
client.delete(
    collection_name="match3_hybrid",
    filter="chunk_id < 1000",
)
```

---

## Match3Runtime 接口设计

在 Runtime 中，Milvus 以 `MilvusClient` 注入：

```python
from typing import Protocol
from pymilvus import MilvusClient

@dataclass(frozen=True)
class Match3Runtime:
    config: Config
    env: Env
    logger: Logger
    milvus: MilvusClient  # Milvus 客户端
    # ... 其他依赖
```

**为什么不用 Protocol？**
- `MilvusClient` 是官方标准接口，功能完备
- 无需额外抽象层
- 如需替换向量数据库，只需修改 `build_runtime()` 中的实现

**替换其他向量数据库示例**:

```python
# 替换为 Qdrant
from qdrant_client import QdrantClient

def build_runtime(config, env) -> Match3Runtime:
    # ...
    milvus = QdrantClient(url=env.QDRANT_URL)  # 修改这里
    # 其他代码不变
    return Match3Runtime(milvus=milvus, ...)
```

**服务层使用示例**:

```python
class EmbedService:
    def __init__(self, rt: Match3Runtime):
        self.milvus = rt.milvus
        self.embedder = rt.embedder
        self.logger = rt.logger
    
    def search_similar_chunks(
        self,
        query: str,
        workspace_id: int,
        top_k: int = 20,
    ) -> list[dict]:
        # 混合向量检索
        dense, sparse = self.embedder.embed_both([query])
        
        results = self.milvus.hybrid_search(
            collection_name=f"workspace_{workspace_id}",
            data=[{"dense": dense[0], "sparse": sparse[0]}],
            limit=top_k,
            reranker="rrf",
            reranker_params={"k": 60},
            output_fields=["text", "chunk_id"],
        )
        
        return results[0]
```

---

## Docker 部署

### docker-compose.yml

```yaml
version: '3.8'

services:
  milvus-standalone:
    image: milvusdb/milvus:v2.6.14
    container_name: match3-milvus
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
      MINIO_ACCESS_KEY_ID: minioadmin
      MINIO_SECRET_ACCESS_KEY: minioadmin
    volumes:
      - milvus_data:/var/lib/milvus
    ports:
      - "19530:19530"  # gRPC
      - "9091:9091"    # Metrics (Prometheus)
    depends_on:
      - etcd
      - minio
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    container_name: match3-etcd
    environment:
      ETCD_AUTO_COMPACTION_MODE: revision
      ETCD_AUTO_COMPACTION_RETENTION: '1000'
      ETCD_QUOTA_BACKEND_BYTES: '4294967296'
      ETCD_SNAPSHOT_COUNT: '50000'
    volumes:
      - etcd_data:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd
    healthcheck:
      test: ["CMD", "etcdctl", "endpoint", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  minio:
    image: minio/minio:RELEASE.2026-04-11T03-20-12Z
    container_name: match3-minio-milvus
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/minio_data
    command: minio server /minio_data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  milvus_data:
  etcd_data:
  minio_data:
```

### 启动服务

```bash
docker-compose up -d milvus-standalone
docker-compose logs -f milvus-standalone
```

### 验证服务

```bash
# Python 客户端连接测试
python -c "
from pymilvus import MilvusClient
client = MilvusClient(uri='http://localhost:19530')
print('Collections:', client.list_collections())
"
```

---

## 性能优化

### 1. 索引选择

| 索引类型 | 场景 | 内存占用 | 查询速度 | 构建时间 |
|---------|-----|---------|---------|---------|
| HNSW | 小到中等数据集（< 1B），高精度要求 | 高 | 极快 | 中等 |
| IVF_FLAT | 中等数据集，平衡性能和精度 | 中等 | 快 | 快 |
| IVF_SQ8 | 大数据集，内存受限 | 低 | 中等 | 快 |
| AUTOINDEX | 自动选择（推荐） | - | - | - |

**推荐配置**:

```python
# HNSW（默认推荐）
index_params = {
    "M": 16,              # 邻居数（8-64），越大越精确但内存占用越高
    "efConstruction": 256, # 构建时搜索深度（64-512）
}

# 搜索时参数
search_params = {
    "ef": 64,  # 搜索深度（16-512），越大越精确但越慢
}
```

### 2. 批量操作

```python
# ❌ 避免：逐条插入
for vec in vectors:
    client.insert("match3_dense", [vec])

# ✅ 推荐：批量插入
batch_size = 1000
for i in range(0, len(vectors), batch_size):
    batch = vectors[i:i+batch_size]
    client.insert("match3_dense", batch)
```

### 3. 搜索优化

```python
# 调整搜索参数平衡速度和精度
results = client.search(
    collection_name="match3_dense",
    data=[query_vector],
    limit=10,
    search_params={"ef": 32},  # 降低 ef 提速，但精度略降
)
```

### 4. 分区策略

```python
# 为不同 Workspace 创建分区
client.create_partition(
    collection_name="match3_dense",
    partition_name="workspace_1",
)

# 插入时指定分区
client.insert(
    collection_name="match3_dense",
    data=data,
    partition_name="workspace_1",
)

# 搜索时只搜索特定分区
results = client.search(
    collection_name="match3_dense",
    data=[query_vector],
    limit=10,
    partition_names=["workspace_1"],  # 只搜索这个分区
)
```

---

## 监控与维护

### 1. Collection 统计

```python
# 查看 Collection 统计信息
stats = client.get_collection_stats(collection_name="match3_dense")
print(f"Total entities: {stats['row_count']}")
```

### 2. 索引状态

```python
# 检查索引状态
indexes = client.list_indexes(collection_name="match3_dense")
for idx in indexes:
    print(f"Field: {idx['field_name']}, Index: {idx['index_type']}")
```

### 3. Metrics 监控

Milvus 暴露 Prometheus metrics 在 `http://localhost:9091/metrics`：

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'milvus'
    static_configs:
      - targets: ['milvus:9091']
```

**关键指标**:
- `milvus_search_latency`: 搜索延迟
- `milvus_insert_latency`: 插入延迟
- `milvus_index_build_latency`: 索引构建时间
- `milvus_memory_usage`: 内存使用量

---

## 常见问题

### 1. 内存不足

**现象**: `OOMKilled` 或搜索缓慢

**解决**:
- 使用压缩索引（IVF_SQ8）
- 启用分区，减少单次搜索范围
- 增加服务器内存
- 使用 DiskANN（磁盘索引）

### 2. 搜索精度不足

**解决**:
- 增大索引参数: `M=32, efConstruction=512`
- 增大搜索参数: `ef=128`
- 使用 HNSW 而非 IVF

### 3. 插入速度慢

**解决**:
- 增大批量插入大小（1000-5000）
- 先插入数据，最后统一构建索引
- 使用 AUTOINDEX

---

## 替换其他向量数据库

### 切换到 Qdrant

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# 创建客户端
qdrant = QdrantClient(url="http://localhost:6333")

# 创建 Collection
qdrant.create_collection(
    collection_name="match3_dense",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)

# 插入数据
qdrant.upsert(
    collection_name="match3_dense",
    points=[
        {"id": 1, "vector": [0.1, 0.2, ...], "payload": {"text": "..."}},
    ],
)

# 搜索
results = qdrant.search(
    collection_name="match3_dense",
    query_vector=[0.1, 0.2, ...],
    limit=10,
)
```

### 切换到 Pinecone

```python
import pinecone

# 初始化
pinecone.init(api_key="YOUR_API_KEY", environment="us-west1-gcp")

# 创建索引
pinecone.create_index("match3-dense", dimension=1536, metric="cosine")
index = pinecone.Index("match3-dense")

# 插入
index.upsert(vectors=[("id1", [0.1, 0.2, ...], {"text": "..."})])

# 搜索
results = index.query(vector=[0.1, 0.2, ...], top_k=10, include_metadata=True)
```

---

## 参考资源

- **Milvus 官方文档**: https://milvus.io/docs
- **pymilvus API 文档**: https://milvus.io/api-reference/pymilvus/v2.6.x/About.md
- **混合搜索指南**: https://milvus.io/docs/multi-vector-search.md
- **性能调优**: https://milvus.io/docs/performance_tuning.md
- **索引选择指南**: https://milvus.io/docs/index.md
- **GitHub**: https://github.com/milvus-io/milvus
