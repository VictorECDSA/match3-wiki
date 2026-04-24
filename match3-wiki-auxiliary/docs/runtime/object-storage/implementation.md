# ObjectStorage 实现 — MinIO RELEASE.2025-10-15

## 文件布局

```
backend/runtime_impl/implements/object_storage/
├── object_storage.py                           # create_object_storage(config, env, logger) -> ObjectStorage
└── impl_minio/
    ├── minio_object_storage.py                 # MinIOObjectStorage
    └── minio_storage_object.py                 # MinIOStorageObject
```

依赖：`minio` 7.2+（Python SDK）。

---

## 工厂函数

```python
# backend/runtime_impl/implements/object_storage/object_storage.py
from minio import Minio
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from backend.config import Config, Env
from backend.runtime.protocols.logger.logger import Logger
from backend.runtime.protocols.object_storage.object_storage import ObjectStorage
from .impl_minio.minio_object_storage import MinIOObjectStorage

def create_object_storage(config: Config, env: Env, logger: Logger) -> ObjectStorage:
    provider = config.runtime.object_storage.provider

    if provider != "minio":
        raise Match3Exception.of_code(
            codes.CONFIG_MISSING_REQUIRED,
            "unsupported object_storage provider",
        ).ctx(provider=provider)

    impl = config.runtime.object_storage.implementations.minio
    try:
        client = Minio(
            endpoint=env.MINIO_ENDPOINT,
            access_key=env.MINIO_ACCESS_KEY,
            secret_key=env.MINIO_SECRET_KEY,
            secure=impl.secure,
            region=impl.region,
        )
        if not client.bucket_exists(impl.bucket):
            client.make_bucket(impl.bucket)
            logger.info("created default bucket", bucket=impl.bucket)
    except Exception as e:
        raise Match3Exception.of_code(codes.MINIO_ERROR, "failed to init minio") \
            .ctx(endpoint=env.MINIO_ENDPOINT, bucket=impl.bucket).as_ex(e)

    logger.info("minio client initialized", endpoint=env.MINIO_ENDPOINT, bucket=impl.bucket)
    return MinIOObjectStorage(client)
```

---

## 适配器

```python
# backend/runtime_impl/implements/object_storage/impl_minio/minio_object_storage.py
from io import BytesIO
from datetime import timedelta
from typing import BinaryIO, Iterator
from minio import Minio
from minio.error import S3Error
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from .minio_storage_object import MinIOStorageObject

class MinIOObjectStorage:
    """MinIO implementation of ObjectStorage protocol."""

    def __init__(self, client: Minio):
        self._client = client

    def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        if isinstance(data, (bytes, bytearray)):
            stream, length = BytesIO(bytes(data)), len(data)
        else:
            stream, length = data, -1
        try:
            result = self._client.put_object(
                bucket_name=bucket,
                object_name=key,
                data=stream,
                length=length,
                part_size=10 * 1024 * 1024,
                content_type=content_type or "application/octet-stream",
                metadata=metadata,
            )
        except Exception as e:
            raise Match3Exception.of_code(codes.MINIO_ERROR, "minio put failed") \
                .ctx(bucket=bucket, key=key).as_ex(e)
        return result.etag

    def get_object(self, bucket: str, key: str) -> bytes:
        try:
            resp = self._client.get_object(bucket_name=bucket, object_name=key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        except Exception as e:
            raise Match3Exception.of_code(codes.MINIO_ERROR, "minio get failed") \
                .ctx(bucket=bucket, key=key).as_ex(e)

    def delete_object(self, bucket: str, key: str) -> bool:
        try:
            self._client.remove_object(bucket_name=bucket, object_name=key)
            return True
        except Exception as e:
            raise Match3Exception.of_code(codes.MINIO_ERROR, "minio delete failed") \
                .ctx(bucket=bucket, key=key).as_ex(e)

    def object_exists(self, bucket: str, key: str) -> bool:
        try:
            self._client.stat_object(bucket_name=bucket, object_name=key)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise Match3Exception.of_code(codes.MINIO_ERROR, "minio stat failed") \
                .ctx(bucket=bucket, key=key).as_ex(e)
        except Exception as e:
            raise Match3Exception.of_code(codes.MINIO_ERROR, "minio stat failed") \
                .ctx(bucket=bucket, key=key).as_ex(e)

    def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        recursive: bool = False,
    ) -> Iterator[MinIOStorageObject]:
        try:
            it = self._client.list_objects(
                bucket_name=bucket, prefix=prefix, recursive=recursive,
            )
        except Exception as e:
            raise Match3Exception.of_code(codes.MINIO_ERROR, "minio list failed") \
                .ctx(bucket=bucket, prefix=prefix).as_ex(e)
        for obj in it:
            yield MinIOStorageObject(obj)

    def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> str:
        from minio.commonconfig import CopySource
        try:
            result = self._client.copy_object(
                bucket_name=dest_bucket,
                object_name=dest_key,
                source=CopySource(source_bucket, source_key),
            )
        except Exception as e:
            raise Match3Exception.of_code(codes.MINIO_ERROR, "minio copy failed") \
                .ctx(
                    source_bucket=source_bucket, source_key=source_key,
                    dest_bucket=dest_bucket, dest_key=dest_key,
                ).as_ex(e)
        return result.etag

    def get_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_seconds: int = 3600,
        method: str = "GET",
    ) -> str:
        method_upper = method.upper()
        if method_upper not in ("GET", "PUT"):
            raise Match3Exception.of_code(
                codes.CONFIG_MISSING_REQUIRED,
                "unsupported presign method",
            ).ctx(bucket=bucket, key=key, method=method)
        expires = timedelta(seconds=expires_seconds)
        try:
            if method_upper == "GET":
                return self._client.presigned_get_object(bucket, key, expires=expires)
            return self._client.presigned_put_object(bucket, key, expires=expires)
        except Exception as e:
            raise Match3Exception.of_code(codes.MINIO_ERROR, "minio presign failed") \
                .ctx(bucket=bucket, key=key, method=method_upper).as_ex(e)
```

---

## 对象元数据

```python
# backend/runtime_impl/implements/object_storage/impl_minio/minio_storage_object.py
from datetime import datetime
from minio.datatypes import Object as MinioObject

class MinIOStorageObject:
    """Wraps minio.datatypes.Object as StorageObject protocol."""

    def __init__(self, obj: MinioObject):
        self._obj = obj

    @property
    def key(self) -> str:
        return self._obj.object_name

    @property
    def size(self) -> int:
        return int(self._obj.size or 0)

    @property
    def last_modified(self) -> datetime:
        return self._obj.last_modified

    @property
    def etag(self) -> str:
        return self._obj.etag or ""
```

---

## 配置与环境

- `config.yaml`：`runtime.object_storage.*`
- `.env`：`MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`

详见 [`../config.md`](../config.md)。

---

## 关联文档

- [protocol.md](./protocol.md) — ObjectStorage / StorageObject Protocol
- [versions/minio-v2025.10.15.md](./versions/minio-v2025.10.15.md) — minio-py 接口速查
- [`../../design/solution-final/020-ingestion/`](../../design/solution-final/020-ingestion/) — 对象键规范与导入流水线
