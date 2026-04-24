# 对象存储实现方案 — MinIO

## 概述

使用 **MinIO RELEASE.2025-09-07T16-13-09Z** 实现 `ObjectStorage` Protocol，提供 S3 兼容的对象存储服务。

---

## 工厂函数

```python
# backend/runtime_impl/implements/object_storage/object_storage.py
from minio import Minio
from backend.config import Config, Env
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.object_storage import ObjectStorage
from .impl_minio.minio_adapter import MinioAdapter

def create_object_storage(config: Config, env: Env, logger: Logger) -> ObjectStorage:
    """创建 ObjectStorage 实例
    
    Args:
        config: 配置对象
        env: 环境变量
        logger: 日志记录器
    
    Returns:
        实现了 ObjectStorage Protocol 的 MinioAdapter 实例
    
    Raises:
        ValueError: provider 不支持时抛出
    """
    provider = config.runtime.object_storage.provider
    
    if provider == "minio":
        minio_client = Minio(
            endpoint=env.MINIO_ENDPOINT,
            access_key=env.MINIO_ACCESS_KEY,
            secret_key=env.MINIO_SECRET_KEY,
            secure=config.runtime.object_storage.implementations.minio.secure,
        )
        
        bucket = config.runtime.object_storage.implementations.minio.bucket
        
        # 确保 bucket 存在
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
            logger.info(f"Created bucket: {bucket}")
        
        logger.info(f"MinIO client initialized (bucket: {bucket})")
        return MinioAdapter(minio_client, bucket, logger)
    else:
        raise ValueError(f"Unsupported object_storage provider: {provider}")
```

---

## 适配器实现

```python
# backend/runtime_impl/implements/object_storage/impl_minio/minio_adapter.py
from io import BytesIO
from datetime import timedelta
from minio import Minio
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.object_storage import ObjectStorage

class MinioAdapter:
    """MinIO 适配器，实现 ObjectStorage Protocol"""
    
    def __init__(self, client: Minio, bucket: str, logger: Logger):
        self.client = client
        self.bucket = bucket
        self.logger = logger
    
    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """上传对象到 MinIO
        
        Args:
            key: 对象键（路径），例如 "files/document.pdf"
            data: 文件二进制数据
            content_type: MIME 类型
        
        Returns:
            对象的 S3 URI
        """
        data_stream = BytesIO(data)
        
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=key,
            data=data_stream,
            length=len(data),
            content_type=content_type,
        )
        
        self.logger.debug(f"Uploaded object: {key}")
        return f"s3://{self.bucket}/{key}"
    
    def get_object(self, key: str) -> bytes:
        """从 MinIO 下载对象
        
        Args:
            key: 对象键
        
        Returns:
            文件二进制数据
        """
        response = self.client.get_object(
            bucket_name=self.bucket,
            object_name=key,
        )
        
        try:
            data = response.read()
            self.logger.debug(f"Downloaded object: {key}")
            return data
        finally:
            response.close()
            response.release_conn()
    
    def delete_object(self, key: str) -> None:
        """删除对象"""
        self.client.remove_object(
            bucket_name=self.bucket,
            object_name=key,
        )
        self.logger.debug(f"Deleted object: {key}")
    
    def list_objects(self, prefix: str = "") -> list[str]:
        """列出对象键
        
        Args:
            prefix: 前缀过滤
        
        Returns:
            对象键列表
        """
        objects = self.client.list_objects(
            bucket_name=self.bucket,
            prefix=prefix,
            recursive=True,
        )
        return [obj.object_name for obj in objects]
    
    def get_presigned_url(
        self,
        key: str,
        expires_seconds: int = 3600,
    ) -> str:
        """获取预签名 URL（临时下载链接）
        
        Args:
            key: 对象键
            expires_seconds: URL 有效期（秒）
        
        Returns:
            预签名 URL
        """
        url = self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=key,
            expires=timedelta(seconds=expires_seconds),
        )
        
        return url
    
    def object_exists(self, key: str) -> bool:
        """检查对象是否存在"""
        try:
            self.client.stat_object(
                bucket_name=self.bucket,
                object_name=key,
            )
            return True
        except:
            return False
```

---

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  object_storage:
    provider: minio
    implementations:
      minio:
        bucket: match3-wiki-files    # 存储桶名称
        secure: false                # 是否使用 HTTPS（生产环境建议 true）
```

### Env (.env)

```bash
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

---

## 相关文档

- **[protocol.md](./protocol.md)** — ObjectStorage Protocol 定义
- **[versions/minio-v2025.09.07.md](./versions/minio-v2025.09.07.md)** — MinIO API 详细说明
- **[../../design/solution-final/020-ingestion/](../../design/solution-final/020-ingestion/)** — 文件导入流程
