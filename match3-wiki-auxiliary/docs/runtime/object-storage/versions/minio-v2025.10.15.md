# MinIO RELEASE.2025-10-15T17-29-55Z

- **Version**: RELEASE.2025-10-15T17-29-55Z
- **Release Date**: 2025-10-15
- **Category**: Object Storage (S3-compatible)
- **License**: GNU AGPL v3.0
- **Python SDK**: `minio` 7.2+

> **升级说明**：本版本修复了 Session Policy Bypass 特权提升漏洞（CVE-2025-62506）。所有线上部署应优先升级至该版本或更高。此版本起 MinIO 社区版移除了 Web 管理控制台，管理操作通过 `mc` CLI 或 S3 API 完成。

---

## 客户端初始化

```python
from minio import Minio

def Minio(
    endpoint: str,                          # host:port
    access_key: str | None = None,
    secret_key: str | None = None,
    session_token: str | None = None,
    secure: bool = True,                    # HTTPS
    region: str | None = None,
    http_client: "urllib3.PoolManager | None" = None,
    credentials: "Provider | None" = None,
    cert_check: bool = True,
) -> Minio: ...
```

---

## Bucket 操作

```python
client.bucket_exists(bucket_name: str) -> bool
client.make_bucket(
    bucket_name: str,
    location: str | None = None,
    object_lock: bool = False,
) -> None
client.remove_bucket(bucket_name: str) -> None
client.list_buckets() -> list[Bucket]
```

---

## 对象上传

```python
# 流式上传（size 已知或 -1）
client.put_object(
    bucket_name: str,
    object_name: str,
    data: BinaryIO,
    length: int,                            # -1 表示未知，需要 part_size > 0
    content_type: str = "application/octet-stream",
    metadata: dict[str, str] | None = None,
    sse=None,
    progress=None,
    part_size: int = 0,                     # 0 = 自动，推荐 10MB 以上
    num_parallel_uploads: int = 3,
    tags=None,
    retention=None,
    legal_hold: bool = False,
) -> ObjectWriteResult

# 从本地文件上传
client.fput_object(
    bucket_name: str,
    object_name: str,
    file_path: str,
    content_type: str = "application/octet-stream",
    metadata: dict[str, str] | None = None,
    sse=None,
    progress=None,
    part_size: int = 0,
    tags=None,
    retention=None,
    legal_hold: bool = False,
) -> ObjectWriteResult
```

---

## 对象下载 / 查询

```python
# 流式下载
resp = client.get_object(
    bucket_name: str,
    object_name: str,
    offset: int = 0,
    length: int = 0,                        # 0 = 全部
    request_headers: dict | None = None,
    ssec=None,
    version_id: str | None = None,
    extra_query_params: dict | None = None,
)
# 使用后务必：resp.close(); resp.release_conn()

# 下载到文件
client.fget_object(
    bucket_name: str,
    object_name: str,
    file_path: str,
    request_headers=None,
    ssec=None,
    version_id: str | None = None,
    extra_query_params=None,
    tmp_file_path: str | None = None,
    progress=None,
) -> Object

# 元数据
client.stat_object(
    bucket_name: str,
    object_name: str,
    ssec=None,
    version_id: str | None = None,
    extra_headers=None,
) -> Object
```

---

## 列出对象

```python
client.list_objects(
    bucket_name: str,
    prefix: str | None = None,
    recursive: bool = False,
    start_after: str | None = None,
    include_user_meta: bool = False,
    include_version: bool = False,
    use_api_v1: bool = False,
    use_url_encoding_type: bool = True,
    fetch_owner: bool = False,
    extra_headers=None,
    extra_query_params=None,
) -> Iterator[Object]
```

---

## 删除

```python
client.remove_object(
    bucket_name: str,
    object_name: str,
    version_id: str | None = None,
) -> None

from minio.deleteobjects import DeleteObject

client.remove_objects(
    bucket_name: str,
    delete_object_list: Iterable[DeleteObject],
    bypass_governance_mode: bool = False,
) -> Iterator[DeleteError]
```

---

## 预签名 URL

```python
from datetime import timedelta

client.presigned_get_object(
    bucket_name: str,
    object_name: str,
    expires: timedelta = timedelta(days=7),   # 最长 7 天
    response_headers: dict | None = None,
    request_date=None,
    version_id: str | None = None,
    extra_query_params=None,
) -> str

client.presigned_put_object(
    bucket_name: str,
    object_name: str,
    expires: timedelta = timedelta(days=7),
) -> str
```

---

## 复制

```python
from minio.commonconfig import CopySource

client.copy_object(
    bucket_name: str,                       # 目标 bucket
    object_name: str,                       # 目标 key
    source: CopySource,                     # CopySource(src_bucket, src_key, version_id=None)
    sse=None,
    metadata: dict[str, str] | None = None,
    tags=None,
    retention=None,
    legal_hold: bool = False,
    metadata_directive: str | None = None,  # "COPY" | "REPLACE"
    tagging_directive: str | None = None,
) -> ObjectWriteResult
```

---

## 常见错误

- `S3Error.code == "NoSuchKey"`：对象不存在（`stat_object` 常用于判断）。
- `S3Error.code == "AccessDenied"`：鉴权失败。
- `S3Error.code == "BucketAlreadyOwnedByYou"`：`make_bucket` 时 bucket 已存在且为本账号。

适配器层必须把 `S3Error` 及其他异常包装为 `Match3Exception.of_code(codes.MINIO_ERROR, ...)`。
