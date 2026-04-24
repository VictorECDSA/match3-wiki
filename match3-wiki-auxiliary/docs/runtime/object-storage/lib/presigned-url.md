# 预签名 URL（Presigned URL）

**预签名 URL（Presigned URL）** 是对象存储服务器签发的临时授权访问地址：URL 中内嵌了访问凭证和过期时间，持有该 URL 的任何人都可以在有效期内直接访问指定对象，无需知道真实的 Access Key。

## 核心用途

预签名 URL 解决"让未认证用户临时访问私有对象"的问题：

- **前端直传**：生成预签名上传 URL，浏览器直接上传到 MinIO，绕过后端，减少服务器带宽消耗
- **临时下载**：生成预签名下载 URL，前端可直接下载文件，后端不作为代理中转
- **安全共享**：分享文件给外部用户，URL 到期后自动失效

## 生成方式

```python
from minio import Minio
from datetime import timedelta

client = Minio(...)

# Generate presigned GET URL (valid for 1 hour)
download_url = client.presigned_get_object(
    bucket_name="match3-raw",
    object_name="raw/ws-123/uuid.pdf",
    expires=timedelta(hours=1),
)

# Generate presigned PUT URL (for direct upload from browser)
upload_url = client.presigned_put_object(
    bucket_name="match3-raw",
    object_name="raw/ws-123/uuid.pdf",
    expires=timedelta(minutes=15),
)
```

## URL 结构

预签名 URL 的关键查询参数（以 MinIO/S3 为例）：

```
https://storage.example.com/match3-raw/raw/ws-123/uuid.pdf
  ?X-Amz-Algorithm=AWS4-HMAC-SHA256
  &X-Amz-Credential=...
  &X-Amz-Date=20260424T000000Z
  &X-Amz-Expires=3600          ← validity in seconds
  &X-Amz-SignedHeaders=host
  &X-Amz-Signature=...         ← HMAC signature, tamper-proof
```

## 本项目的使用场景

本项目中，预签名 URL 主要用于前端展示图片和下载原始文件，不通过后端 API 中转。后端内部操作（Worker 读取原始文件）直接用 `get_object()` 而不用预签名 URL。
