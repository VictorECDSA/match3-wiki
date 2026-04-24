# 分片上传（Multipart Upload）

**分片上传（Multipart Upload）** 是 S3/MinIO 处理大文件上传的协议：将大文件切分为多个固定大小的分片（Part），分片并行上传后在服务端合并为完整对象。适用于文件大小超过几十 MB 的场景。

## 为什么需要分片上传

| 问题 | 单次上传 | 分片上传 |
|------|----------|----------|
| 大文件上传中断 | 需从头重传 | 只需重传失败的分片 |
| 内存占用 | 需整个文件在内存 | 每次只处理一个分片 |
| 上传速度 | 串行 | 多分片并行 |
| 最大文件大小 | 受限（通常 5GB） | 理论无上限（5TB） |

## 分片上传流程

```
1. InitiateMultipartUpload → get upload_id
2. UploadPart(part_1, upload_id) ─┐
3. UploadPart(part_2, upload_id)  ├── parallel
4. UploadPart(part_N, upload_id) ─┘
5. CompleteMultipartUpload(upload_id, [part_etags])
```

## MinIO Python SDK 的自动分片

`fput_object`（文件路径上传）和 `put_object`（流上传）在文件大于 `part_size` 时自动触发分片上传，无需手动管理：

```python
client.fput_object(
    bucket_name="match3-raw",
    object_name="raw/ws-123/large-video.mp4",
    file_path="/tmp/large-video.mp4",
    part_size=10 * 1024 * 1024,    # 10 MB per part
    num_parallel_uploads=4,         # 4 parts upload in parallel
)
```

## 本项目的配置

```python
# In ObjectStorage Protocol implementation
PART_SIZE = 10 * 1024 * 1024    # 10 MB
NUM_PARALLEL = 4

async def put_object(self, key: str, data: bytes, content_type: str) -> str:
    self._client.put_object(
        bucket_name=self._bucket,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
        part_size=PART_SIZE,
    )
```

小文件（< `part_size`）单次上传，大文件自动分片，对调用方透明。
