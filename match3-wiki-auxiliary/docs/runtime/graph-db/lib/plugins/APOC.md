# APOC（Awesome Procedures on Cypher）

**APOC** 是 Neo4j 最广泛使用的第三方扩展插件，全称"Awesome Procedures on Cypher"，提供 450+ 个存储过程和函数，覆盖数据导入导出、字符串处理、集合操作、HTTP 调用、批量写入等实用功能——弥补原生 Cypher 在工具函数方面的不足。

## 常用功能分类

### 批量写入（apoc.periodic.iterate）

大量数据写入时避免单次事务过大：

```cypher
CALL apoc.periodic.iterate(
    "MATCH (n:Entity) RETURN n",
    "SET n.processed = true",
    {batchSize: 1000, parallel: false}
)
```

### JSON / 数据转换

```cypher
// Parse JSON string to map
WITH apoc.convert.fromJsonMap('{"key": "value"}') AS data
RETURN data.key

// Convert list to string
RETURN apoc.text.join(["match3", "puzzle", "game"], ", ")
```

### 元数据查询

```cypher
// List all labels and their counts
CALL apoc.meta.stats()
YIELD labels
RETURN labels
```

### HTTP 调用（不推荐在生产中使用）

```cypher
CALL apoc.load.json("https://api.example.com/data")
YIELD value
RETURN value
```

## 安装与启用

在 `neo4j.conf` 中或通过 Docker 环境变量启用：

```yaml
# docker-compose.yml
environment:
  - NEO4J_PLUGINS=["apoc"]
  - NEO4J_apoc_export_file_enabled=true
  - NEO4J_apoc_import_file_enabled=true
```

## 与 GDS 的关系

APOC 是通用工具库（字符串、集合、数据转换），[GDS](../algorithms/GDS.md) 是图算法计算框架，两者功能互补，通常同时安装使用。
