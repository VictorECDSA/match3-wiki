# Collection（集合）

**Collection** 是 Milvus 中组织向量数据的基本单位，类似关系数据库中的"表"（Table）。每个 Collection 有固定的字段（Schema），包含一个或多个向量字段和若干标量字段，支持向量检索和标量过滤的组合查询。

## 与关系数据库的类比

| Milvus 概念 | 关系数据库类比 |
|-------------|----------------|
| Collection | 表（Table） |
| Schema | 建表 DDL |
| Entity | 行（Row） |
| Field | 列（Column） |
| Index | 索引 |
| Partition | 分区 |

## 本项目的 Collection

### match3_chunks

存储文本块的稠密向量和稀疏向量：

```python
schema = CollectionSchema(fields=[
    FieldSchema("id",            DataType.VARCHAR,        max_length=36, is_primary=True),
    FieldSchema("workspace_id",  DataType.VARCHAR,        max_length=36),
    FieldSchema("raw_file_id",   DataType.VARCHAR,        max_length=36),
    FieldSchema("chunk_type",    DataType.VARCHAR,        max_length=32),
    FieldSchema("dense_vector",  DataType.FLOAT_VECTOR,   dim=1536),
    FieldSchema("sparse_vector", DataType.SPARSE_FLOAT_VECTOR),
])
```

### image_chunks

存储图片的 CLIP 向量：

```python
schema = CollectionSchema(fields=[
    FieldSchema("id",           DataType.VARCHAR,       max_length=36, is_primary=True),
    FieldSchema("workspace_id", DataType.VARCHAR,       max_length=36),
    FieldSchema("image_path",   DataType.VARCHAR,       max_length=512),
    FieldSchema("description",  DataType.VARCHAR,       max_length=2048),
    FieldSchema("dense_vector", DataType.FLOAT_VECTOR,  dim=768),   # CLIP dim
])
```

## 标量过滤

Collection 中的标量字段（如 `workspace_id`）可在向量检索时作为过滤条件，确保工作区数据隔离：

```python
results = collection.search(
    data=[query_vector],
    anns_field="dense_vector",
    param=search_params,
    expr='workspace_id == "ws-123"',  # scalar filter
    limit=50,
)
```
