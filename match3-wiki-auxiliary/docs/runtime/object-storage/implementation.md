# 对象存储实现方案

> **实现**: MinIO RELEASE.2025-09-07T16-13-09Z  
> **Python 客户端**: minio v7.2.12  
> **Protocol**: `ObjectStorage` (见 [protocol.md](./protocol.md))

## 📚 相关文档

- **Protocol 定义**: [protocol.md](./protocol.md) - 抽象接口定义
- **MinIO 技术文档**: [versions/minio-v2025.09.07.md](./versions/minio-v2025.09.07.md) - MinIO API 详细说明

---

## MinIO 适配器实现

### 完整代码

```python
from minio import Minio
from io import BytesIO


class MinioAdapter:
    """MinIO 适配器，实现 ObjectStorage Protocol。"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ):
        """初始化 MinIO 客户端
        
        Args:
            endpoint: MinIO 服务地址（host:port，无协议前缀）
            access_key: 访问密钥
            secret_key: 密钥
            bucket: 存储桶名称
            secure: 是否使用 HTTPS
        """
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self.bucket = bucket
        
        # 确保 bucket 存在
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

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
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_object(self, key: str) -> None:
        """删除对象"""
        self.client.remove_object(
            bucket_name=self.bucket,
            object_name=key,
        )

    def list_objects(self, prefix: str = "") -> list[str]:
        """列出对象"""
        objects = self.client.list_objects(
            bucket_name=self.bucket,
            prefix=prefix,
        )
        return [obj.object_name for obj in objects]
```

## Runtime 集成

### 构建函数

```python
# app/runtime.py
from app.intelligence.object_storage.minio_adapter import MinioAdapter

def build_runtime(config: Config, env: Env, logger: Logger) -> Match3Runtime:
    """构建 Runtime 实例"""
    
    minio_adapter = MinioAdapter(
        endpoint=config.runtime.object_storage.implementations.minio.endpoint,
        access_key=env.MINIO_ACCESS_KEY,
        secret_key=env.MINIO_SECRET_KEY,
        bucket=config.runtime.object_storage.implementations.minio.bucket,
        secure=config.runtime.object_storage.implementations.minio.secure,
    )
    
    logger.info(f"MinIO adapter initialized (bucket: {config.runtime.object_storage.implementations.minio.bucket})")
    
    return Match3Runtime(
        storage=minio_adapter,
        # ... 其他组件
    )
```

## 配置说明

### 环境变量配置 (`.env`)

```bash
# Object Storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### 配置文件 (`config.yaml`)

```yaml
runtime:
  object_storage:
    provider: minio
    implementations:
      minio:
        endpoint: localhost:9000
        bucket: match3-wiki-files
        secure: false  # 生产环境改为 true
```

---

**创建时间**：2026-04-23  
**版本**：2.0

    def get_presigned_url(
        self,
        key: str,
        expires_seconds: int = 3600,
    ) -> str:
        """获取预签名 URL（临时下载链接）。
        
        Args:
            key: 对象键
            expires_seconds: URL 有效期（秒）
        
        Returns:
            预签名 URL
        """
        from datetime import timedelta
        
        url = self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=key,
            expires=timedelta(seconds=expires_seconds),
        )
        
        return url

    def list_objects(self, prefix: str = "") -> list[str]:
        """列出对象键。
        
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

    def object_exists(self, key: str) -> bool:
        """检查对象是否存在。"""
        try:
            self.client.stat_object(
                bucket_name=self.bucket,
                object_name=key,
            )
            return True
        except:
            return False
```

## Runtime 集成

```python
# app/runtime.py (build_runtime 部分)
from app.intelligence.object_storage.minio_adapter import MinioAdapter

return Match3Runtime(
    # ...
    storage=MinioAdapter(rt),
    # ...
)
```

**注意**：`MinioAdapter` 需要访问 `rt.config` 和 `rt.env`，因此在 `build_runtime()` 中**最后**构建。

## 使用示例

### 上传文件

```python
from app.runtime import Match3Runtime

def upload_raw_file(rt: Match3Runtime, filename: str, file_data: bytes) -> str:
    """上传用户文件。"""
    key = f"uploads/{filename}"
    storage_url = rt.storage.put_object(
        key=key,
        data=file_data,
        content_type="application/pdf",
    )
    return storage_url
```

### 下载文件

```python
def download_raw_file(rt: Match3Runtime, storage_key: str) -> bytes:
    """下载文件。"""
    return rt.storage.get_object(storage_key)
```

### 删除文件

```python
def delete_raw_file(rt: Match3Runtime, storage_key: str):
    """删除文件。"""
    rt.storage.delete_object(storage_key)
```

### 获取临时下载链接

```python
def get_file_download_url(rt: Match3Runtime, storage_key: str) -> str:
    """获取 1 小时有效的下载链接。"""
    return rt.storage.get_presigned_url(
        key=storage_key,
        expires_seconds=3600,
    )
```

### 列出文件

```python
def list_workspace_files(rt: Match3Runtime, workspace_id: int) -> list[str]:
    """列出工作空间的所有文件。"""
    prefix = f"uploads/workspace-{workspace_id}/"
    return rt.storage.list_objects(prefix=prefix)
```

## 文件组织结构

```
match3-files/                # bucket 名称
├── uploads/                 # 用户上传的原始文件
│   ├── workspace-1/
│   │   ├── file1.pdf
│   │   ├── file2.png
│   │   └── file3.mp4
│   └── workspace-2/
│       └── document.pdf
├── wiki/                    # Wiki 编译生成的 Markdown
│   ├── workspace-1/
│   │   ├── candy-crush.md
│   │   └── match3-mechanics.md
│   └── workspace-2/
│       └── game-design.md
└── temp/                    # 临时处理文件
    ├── video-frames/
    │   └── frame-001.jpg
    └── audio-transcripts/
        └── transcript.txt
```

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  object_storage:
    provider: minio
    implementations:
      minio:
        bucket: match3-wiki-files
        secure: false  # Set to true for HTTPS
```

### Env (.env)

```bash
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

## 性能优化

### 1. 使用分块上传（大文件）

```python
def upload_large_file(rt: Match3Runtime, key: str, file_path: str):
    """上传大文件（> 5MB）。"""
    rt.storage.client.fput_object(
        bucket_name=rt.storage.bucket,
        object_name=key,
        file_path=file_path,
        part_size=10 * 1024 * 1024,  # 10MB 分块
    )
```

### 2. 并发上传

```python
from concurrent.futures import ThreadPoolExecutor

def batch_upload_files(rt: Match3Runtime, files: list[tuple[str, bytes]]):
    """并发上传多个文件。"""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(rt.storage.put_object, key, data)
            for key, data in files
        ]
        results = [f.result() for f in futures]
    return results
```

### 3. 使用对象生命周期策略

```python
from minio import Minio
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration

def set_lifecycle_policy(client: Minio, bucket: str):
    """设置临时文件 30 天后自动删除。"""
    config = LifecycleConfig(
        [
            Rule(
                rule_id="delete-temp-files",
                status="Enabled",
                expiration=Expiration(days=30),
                rule_filter={"Prefix": "temp/"},
            )
        ]
    )
    client.set_bucket_lifecycle(bucket, config)
```

## 部署建议

### 开发环境

使用 Docker 启动 MinIO：

```bash
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  -v /data/minio:/data \
  minio/minio server /data --console-address ":9001"
```

访问 Web UI：`http://localhost:9001`

### 生产环境

- 使用**分布式模式**（多节点集群）
- 启用 **HTTPS**（`secure: true`）
- 配置**访问策略**和**桶策略**
- 定期**备份**重要数据
- 使用**负载均衡器**分发流量

## 相关文档

- **[protocol.md](./protocol.md)** — ObjectStorage Protocol 定义
- **[../../design/solution-final/020-ingestion/](../../design/solution-final/020-ingestion/)** — 文件导入流程
