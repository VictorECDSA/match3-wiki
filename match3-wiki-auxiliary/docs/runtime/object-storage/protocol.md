# ObjectStorage Protocol

> **功能**: S3 兼容对象存储,存储原始文件和生成文件  
> **推荐实现**: MinIO RELEASE.2025-09-07T16-13-09Z (2025-09-07)  
> **Runtime 接口**: `rt.storage: ObjectStorage` (Protocol)

## 📚 相关文档

- **上级文档**: [runtime.md](../runtime.md) - Runtime 系统总览和 Protocol 设计理念
- **实现方案**: [implementation.md](./implementation.md) - MinIO 适配器实现和配置说明
- **版本技术文档**: [versions/](./versions/) - 具体实现库的详细 API 文档
  - [MinIO RELEASE.2025-09-07](./versions/minio-v2025.09.07.md) - 推荐实现

---

## Protocol 定义

### 接口说明

`ObjectStorage` 提供对象存储能力,用于:
- **文件上传/下载**: 原始文档、生成文件的存储
- **临时访问**: 生成预签名 URL 供临时下载
- **文件管理**: 列出、复制、删除对象

### 主接口定义

```python
from typing import Protocol, BinaryIO, Iterator

class ObjectStorage(Protocol):
    """对象存储抽象接口 (不依赖任何对象存储库)"""
    
    def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """上传对象
        
        Args:
            bucket: 存储桶名称
            key: 对象键 (路径)
            data: 对象数据 (字节或文件对象)
            content_type: MIME 类型 (可选)
            metadata: 用户自定义元数据 (可选)
            
        Returns:
            对象的 ETag
        """
        ...
    
    def get_object(
        self,
        bucket: str,
        key: str,
    ) -> bytes:
        """下载对象
        
        Args:
            bucket: 存储桶名称
            key: 对象键
            
        Returns:
            对象数据 (字节)
        """
        ...
    
    def delete_object(
        self,
        bucket: str,
        key: str,
    ) -> bool:
        """删除对象
        
        Args:
            bucket: 存储桶名称
            key: 对象键
            
        Returns:
            是否删除成功
        """
        ...
    
    def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        recursive: bool = False,
    ) -> Iterator[StorageObject]:
        """列出对象
        
        Args:
            bucket: 存储桶名称
            prefix: 对象键前缀 (可选)
            recursive: 是否递归列出 (默认只列出当前层级)
            
        Yields:
            存储对象元数据
        """
        ...
    
    def object_exists(
        self,
        bucket: str,
        key: str,
    ) -> bool:
        """检查对象是否存在
        
        Args:
            bucket: 存储桶名称
            key: 对象键
            
        Returns:
            是否存在
        """
        ...
    
    def get_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_seconds: int = 3600,
    ) -> str:
        """生成预签名 URL (用于临时访问)
        
        Args:
            bucket: 存储桶名称
            key: 对象键
            expires_seconds: 过期时间 (秒)
            
        Returns:
            预签名 URL
        """
        ...
    
    def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> str:
        """复制对象
        
        Args:
            source_bucket: 源存储桶
            source_key: 源对象键
            dest_bucket: 目标存储桶
            dest_key: 目标对象键
            
        Returns:
            目标对象的 ETag
        """
        ...
```

### 存储对象元数据 Protocol

```python
from typing import Protocol
from datetime import datetime

class StorageObject(Protocol):
    """存储对象元数据"""
    
    @property
    def key(self) -> str:
        """对象键 (路径)"""
        ...
    
    @property
    def size(self) -> int:
        """对象大小 (字节)"""
        ...
    
    @property
    def last_modified(self) -> datetime:
        """最后修改时间"""
        ...
    
    @property
    def etag(self) -> str:
        """对象的 ETag (用于校验)"""
        ...
```

---

## 使用示例

### 业务代码 (上传文件)

```python
from runtime import Runtime

def upload_document(
    rt: Runtime,
    doc_id: int,
    content: bytes,
    filename: str,
) -> str:
    """上传文档 (不知道底层是 MinIO 还是 AWS S3)"""
    
    key = f"documents/{doc_id}/{filename}"
    
    etag = rt.storage.put_object(
        bucket="my-bucket",
        key=key,
        data=content,
        content_type="application/pdf",
        metadata={
            "doc_id": str(doc_id),
            "original_filename": filename,
        },
    )
    
    return key
```

### 业务代码 (下载文件)

```python
def download_document(
    rt: Runtime,
    key: str,
) -> bytes:
    """下载文档"""
    
    if not rt.storage.object_exists("my-bucket", key):
        raise FileNotFoundError(f"Document not found: {key}")
    
    return rt.storage.get_object("my-bucket", key)
```

### 业务代码 (生成临时下载链接)

```python
def get_download_url(
    rt: Runtime,
    doc_id: int,
    filename: str,
    expires_hours: int = 1,
) -> str:
    """生成临时下载链接 (1小时有效)"""
    
    key = f"documents/{doc_id}/{filename}"
    
    return rt.storage.get_presigned_url(
        bucket="my-bucket",
        key=key,
        expires_seconds=expires_hours * 3600,
    )
```

### 业务代码 (列出文件)

```python
def list_user_documents(
    rt: Runtime,
    user_id: int,
) -> list[dict]:
    """列出用户的所有文档"""
    
    prefix = f"documents/{user_id}/"
    
    objects = rt.storage.list_objects(
        bucket="my-bucket",
        prefix=prefix,
        recursive=True,
    )
    
    return [
        {
            "key": obj.key,
            "size": obj.size,
            "last_modified": obj.last_modified.isoformat(),
        }
        for obj in objects
    ]
```

### 单元测试

```python
from unittest.mock import MagicMock, Mock
from runtime import Runtime

def test_upload_document():
    # Mock 对象存储
    mock_storage = MagicMock()
    mock_storage.put_object.return_value = "abc123etag"
    
    # 创建测试 Runtime
    rt = Runtime(
        cache=MagicMock(),
        queue=MagicMock(),
        vector_db=MagicMock(),
        graph_db=MagicMock(),
        db=MagicMock(),
        search=MagicMock(),
        storage=mock_storage,
    )
    
    # 测试
    key = upload_document(rt, doc_id=1, content=b"test", filename="test.pdf")
    
    assert key == "documents/1/test.pdf"
    mock_storage.put_object.assert_called_once()
```

---

## 设计说明

### 流式上传/下载

对于大文件,应该支持流式操作:

```python
def put_object(
    self,
    bucket: str,
    key: str,
    data: bytes | BinaryIO,  # 支持文件对象
    ...
) -> str: ...
```

业务代码:

```python
with open("large_file.zip", "rb") as f:
    rt.storage.put_object("my-bucket", "large_file.zip", f)
```

### 分片上传

对于超大文件 (> 5GB),需要分片上传:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class MultipartUpload(Protocol):
    """分片上传接口 (可选)"""
    
    def initiate_multipart_upload(
        self,
        bucket: str,
        key: str,
    ) -> str:
        """初始化分片上传,返回 upload_id"""
        ...
    
    def upload_part(
        self,
        bucket: str,
        key: str,
        upload_id: str,
        part_number: int,
        data: bytes,
    ) -> str:
        """上传分片,返回 ETag"""
        ...
    
    def complete_multipart_upload(
        self,
        bucket: str,
        key: str,
        upload_id: str,
        parts: list[tuple[int, str]],  # [(part_number, etag), ...]
    ) -> str:
        """完成分片上传"""
        ...
```

### 存储桶管理

存储桶的创建通常在应用启动时完成,不放入 Runtime:

```python
# 初始化脚本
def init_storage_buckets(minio_client: Minio):
    if not minio_client.bucket_exists("my-bucket"):
        minio_client.make_bucket("my-bucket")
```

### 异步支持

如果需要异步操作 (FastAPI 推荐):

```python
class ObjectStorage(Protocol):
    async def put_object(...) -> str: ...
    async def get_object(...) -> bytes: ...
```

MinIO 官方暂不支持异步,可以使用 `asyncio.to_thread()` 包装:

```python
async def put_object(self, bucket, key, data, ...):
    return await asyncio.to_thread(
        self._client.put_object,
        bucket, key, data, ...
    )
```

---

## 扩展性

### 切换到 AWS S3

```python
import boto3

class S3Adapter:
    """AWS S3 适配器 (实现 ObjectStorage Protocol)"""
    
    def __init__(self, s3_client):
        self._client = s3_client
    
    def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BytesIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        response = self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
            Metadata=metadata or {},
        )
        
        return response["ETag"].strip('"')
    
    def get_object(
        self,
        bucket: str,
        key: str,
    ) -> bytes:
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    
    # ... 其他方法类似
```

**无需修改 Runtime 或业务代码！**

---

**创建时间**: 2026-04-23  
**最后更新**: 2026-04-23  
**版本**: 2.0
