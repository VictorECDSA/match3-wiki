# ObjectStorage Protocol

- **功能**：S3 兼容对象存储（上传、下载、预签名 URL、列出、复制）
- **推荐实现**：MinIO RELEASE.2025-10-15T17-29-55Z（客户端 minio-py 7.2+）
- **Runtime 字段**：`rt.storage: ObjectStorage`
- **错误码**：失败时抛 `Match3Exception.of_code(codes.MINIO_ERROR, ...)` (500006)

---

## 类清单

| 类 | 文件 | 类型 |
|----|------|------|
| `ObjectStorage` | `backend/runtime/protocols/object_storage/object_storage.py` | Protocol |
| `StorageObject` | `backend/runtime/protocols/object_storage/storage_object.py` | Protocol |

---

## ObjectStorage

```python
# backend/runtime/protocols/object_storage/object_storage.py
from typing import Protocol, BinaryIO, Iterator
from .storage_object import StorageObject

class ObjectStorage(Protocol):
    """S3-compatible object storage protocol."""

    def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str: ...

    def get_object(
        self,
        bucket: str,
        key: str,
    ) -> bytes: ...

    def delete_object(
        self,
        bucket: str,
        key: str,
    ) -> bool: ...

    def object_exists(
        self,
        bucket: str,
        key: str,
    ) -> bool: ...

    def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        recursive: bool = False,
    ) -> Iterator[StorageObject]: ...

    def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> str: ...

    def get_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_seconds: int = 3600,
        method: str = "GET",
    ) -> str: ...
```

### 方法签名

| 方法 | 参数 | 返回 |
|------|------|------|
| `put_object` | `bucket`, `key`, `data: bytes \| BinaryIO`, `content_type: str \| None`, `metadata: dict[str, str] \| None` | `str`（ETag） |
| `get_object` | `bucket`, `key` | `bytes` |
| `delete_object` | `bucket`, `key` | `bool` |
| `object_exists` | `bucket`, `key` | `bool` |
| `list_objects` | `bucket`, `prefix: str = ""`, `recursive: bool = False` | `Iterator[StorageObject]` |
| `copy_object` | `source_bucket`, `source_key`, `dest_bucket`, `dest_key` | `str`（目标对象 ETag） |
| `get_presigned_url` | `bucket`, `key`, `expires_seconds: int = 3600`, `method: str = "GET"`（`GET` / `PUT`） | `str`（URL） |

### 使用约束

- **`data` 接受 `bytes` 或 file-like**；大文件必须传文件对象避免内存占用。
- **Bucket 创建**不在 Protocol 中，由工厂函数初始化时自动创建默认 bucket（见实现层）。
- **预签名 URL 最长 7 天**（S3 协议上限）；业务侧需按需缩短。

---

## StorageObject

```python
# backend/runtime/protocols/object_storage/storage_object.py
from typing import Protocol
from datetime import datetime

class StorageObject(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def size(self) -> int: ...

    @property
    def last_modified(self) -> datetime: ...

    @property
    def etag(self) -> str: ...
```

---

## 使用示例

```python
# 上传
etag = rt.storage.put_object(
    bucket="match3-wiki-files",
    key=f"raw/{workspace_id}/{raw_file_id}.pdf",
    data=pdf_bytes,
    content_type="application/pdf",
    metadata={"raw_file_id": str(raw_file_id)},
)

# 生成下载链接
url = rt.storage.get_presigned_url(
    bucket="match3-wiki-files",
    key=f"raw/{workspace_id}/{raw_file_id}.pdf",
    expires_seconds=3600,
)

# 列出对象
for obj in rt.storage.list_objects(
    bucket="match3-wiki-files",
    prefix=f"raw/{workspace_id}/",
    recursive=True,
):
    print(obj.key, obj.size)
```

---

## 关联文档

- [implementation.md](./implementation.md) — MinIO 适配器
- [versions/minio-v2025.10.15.md](./versions/minio-v2025.10.15.md) — minio-py 接口速查
- [../config.md](../config.md) — `runtime.object_storage.*` 配置
- [`../../design/solution-final/020-ingestion/`](../../design/solution-final/020-ingestion/) — 文件导入与对象键规范
