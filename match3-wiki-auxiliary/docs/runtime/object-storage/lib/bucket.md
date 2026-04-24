# Bucket 与 Object Key

**Bucket（存储桶）** 和 **Object Key（对象键）** 是对象存储的两个基本组织概念，构成对象存储的命名空间。

## Bucket（存储桶）

Bucket 是对象的顶层容器，类似文件系统中的根目录，但没有层级限制。每个 Bucket 有全局唯一名称（在同一 MinIO 实例内），有独立的访问策略和存储配置。

```python
# Create bucket if not exists
if not client.bucket_exists("match3-raw"):
    client.make_bucket("match3-raw")
```

本项目使用两个 Bucket：

| Bucket | 用途 |
|--------|------|
| `match3-raw` | 原始上传文件（PDF、图片、视频等） |
| `match3-processed` | 处理后的中间产物（图片描述、截图等） |

## Object Key（对象键）

Object Key 是对象在 Bucket 内的唯一标识，类似文件路径字符串，但并不真正存在层级目录结构（`/` 只是键名的一部分，由客户端惯例约定）。

### 本项目的命名约定

```
raw/{workspace_id}/{uuid}.{ext}
```

例如：

```
raw/ws-a1b2c3/d4e5f6-7890-abcd.pdf
raw/ws-a1b2c3/1122-3344-5566.jpg
```

`workspace_id` 放在路径前缀中，便于按工作区批量列举或删除：

```python
# List all objects for a workspace
objects = client.list_objects("match3-raw", prefix=f"raw/{workspace_id}/")
for obj in objects:
    print(obj.object_name, obj.size)
```

## 与文件系统的对比

| 概念 | 对象存储 | 文件系统 |
|------|----------|----------|
| 顶层容器 | Bucket | 挂载点 / 根目录 |
| 路径 | Object Key（字符串） | 目录树（真实层级） |
| 元数据 | 每个对象附带自定义元数据 | inode 属性 |
| 扁平结构 | ✓（`/` 只是命名惯例） | ✗（真正的目录树） |
