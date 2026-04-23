# MinIO RELEASE.2025-09-07T16-13-09Z

**Version**: RELEASE.2025-09-07T16-13-09Z  
**Release Date**: 2025-09-07  
**Category**: Object Storage (S3-Compatible)  
**License**: GNU AGPL v3.0

---

## API Interface Overview

### 1. Client Connection

```python
from minio import Minio

def connect(
    endpoint: str,                 # MinIO server endpoint (host:port)
    access_key: str,               # Access key (like AWS_ACCESS_KEY_ID)
    secret_key: str,               # Secret key (like AWS_SECRET_ACCESS_KEY)
    secure: bool = True,           # Use HTTPS (True) or HTTP (False)
    region: str | None = None,     # Region name (optional)
    session_token: str | None = None, # Session token for temporary credentials
    http_client: Any | None = None # Custom HTTP client (for connection pooling)
) -> Minio:
    """Create MinIO client connection"""
```

### 2. Bucket Operations

```python
def bucket_exists(
    bucket_name: str               # Bucket name to check
) -> bool:
    """Check if bucket exists"""

def make_bucket(
    bucket_name: str,              # Bucket name (3-63 chars, lowercase)
    location: str | None = None,   # Region for bucket
    object_lock: bool = False      # Enable object locking
) -> None:
    """Create a new bucket"""

def remove_bucket(
    bucket_name: str               # Bucket name to remove (must be empty)
) -> None:
    """Remove an empty bucket"""

def list_buckets() -> list[Bucket]:
    """List all buckets"""
```

### 3. Object Upload Operations

```python
def put_object(
    bucket_name: str,              # Target bucket name
    object_name: str,              # Object key/path in bucket
    data: BinaryIO,                # File-like object to upload
    length: int,                   # Size of data in bytes (-1 for unknown)
    content_type: str = "application/octet-stream", # MIME type
    metadata: dict | None = None,  # Custom metadata key-value pairs
    sse: Any | None = None,        # Server-side encryption
    progress: callable | None = None, # Progress callback function
    part_size: int = 0             # Part size for multipart upload (0=auto)
) -> ObjectWriteResult:
    """Upload object from file-like object"""

def fput_object(
    bucket_name: str,              # Target bucket name
    object_name: str,              # Object key/path in bucket
    file_path: str,                # Local file path to upload
    content_type: str = "application/octet-stream", # MIME type
    metadata: dict | None = None,  # Custom metadata
    sse: Any | None = None,        # Server-side encryption
    progress: callable | None = None, # Progress callback
    part_size: int = 0             # Part size for multipart upload
) -> ObjectWriteResult:
    """Upload object from local file"""
```

### 4. Object Download Operations

```python
def get_object(
    bucket_name: str,              # Source bucket name
    object_name: str,              # Object key/path
    offset: int = 0,               # Start byte position
    length: int = 0,               # Number of bytes to read (0=all)
    request_headers: dict | None = None, # Custom request headers
    ssec: Any | None = None,       # Server-side encryption (for encrypted objects)
    version_id: str | None = None  # Object version ID
) -> HTTPResponse:
    """Download object as stream"""

def fget_object(
    bucket_name: str,              # Source bucket name
    object_name: str,              # Object key/path
    file_path: str,                # Local file path to save
    request_headers: dict | None = None, # Custom headers
    ssec: Any | None = None,       # Server-side encryption
    version_id: str | None = None, # Object version ID
    progress: callable | None = None # Progress callback
) -> ObjectWriteResult:
    """Download object to local file"""
```

### 5. Object Info & Listing

```python
def stat_object(
    bucket_name: str,              # Bucket name
    object_name: str,              # Object key/path
    ssec: Any | None = None,       # Server-side encryption
    version_id: str | None = None  # Object version ID
) -> Object:
    """Get object metadata (size, etag, content-type, etc.)"""

def list_objects(
    bucket_name: str,              # Bucket name
    prefix: str | None = None,     # Filter by prefix (folder path)
    recursive: bool = False,       # List recursively (True) or top-level only
    start_after: str | None = None, # Start listing after this key
    include_user_meta: bool = False, # Include custom metadata
    include_version: bool = False, # Include all versions
    use_api_v1: bool = False       # Use API v1 (legacy)
) -> Iterator[Object]:
    """List objects in bucket (returns iterator)"""
```

### 6. Object Deletion

```python
def remove_object(
    bucket_name: str,              # Bucket name
    object_name: str,              # Object key/path to delete
    version_id: str | None = None  # Version ID (for versioned buckets)
) -> None:
    """Remove a single object"""

def remove_objects(
    bucket_name: str,              # Bucket name
    delete_object_list: Iterator[DeleteObject], # Iterator of objects to delete
    bypass_governance_mode: bool = False # Bypass governance retention
) -> Iterator[DeleteError]:
    """Remove multiple objects (batch delete)"""
```

### 7. Presigned URLs

```python
def presigned_get_object(
    bucket_name: str,              # Bucket name
    object_name: str,              # Object key/path
    expires: timedelta = timedelta(days=7), # URL expiration time
    response_headers: dict | None = None, # Override response headers
    request_date: datetime | None = None, # Request date
    version_id: str | None = None  # Object version ID
) -> str:
    """Generate presigned URL for downloading object"""

def presigned_put_object(
    bucket_name: str,              # Bucket name
    object_name: str,              # Object key/path
    expires: timedelta = timedelta(days=7) # URL expiration time
) -> str:
    """Generate presigned URL for uploading object"""
```

### 8. Copy Operations

```python
def copy_object(
    bucket_name: str,              # Destination bucket
    object_name: str,              # Destination object key
    source: CopySource,            # Source object (bucket + key)
    sse: Any | None = None,        # Server-side encryption for destination
    metadata: dict | None = None,  # New metadata (replaces source metadata)
    tags: dict | None = None       # Object tags
) -> ObjectWriteResult:
    """Copy object from source to destination"""
```

### 9. Runtime Interface (Match3 Project)

```python
from typing import Protocol, BinaryIO
from minio import Minio
from datetime import timedelta

class IMinioClient(Protocol):
    """MinIO client interface for dependency injection"""
    
    def bucket_exists(self, bucket_name: str) -> bool:
        """Check if bucket exists"""
    
    def make_bucket(self, bucket_name: str, location: str | None = None) -> None:
        """Create bucket"""
    
    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None
    ) -> Any:
        """Upload object"""
    
    def get_object(
        self,
        bucket_name: str,
        object_name: str
    ) -> Any:
        """Download object"""
    
    def fput_object(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str,
        content_type: str = "application/octet-stream"
    ) -> Any:
        """Upload file"""
    
    def fget_object(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str
    ) -> Any:
        """Download file"""
    
    def stat_object(
        self,
        bucket_name: str,
        object_name: str
    ) -> Any:
        """Get object metadata"""
    
    def remove_object(
        self,
        bucket_name: str,
        object_name: str
    ) -> None:
        """Delete object"""
    
    def presigned_get_object(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta = timedelta(days=7)
    ) -> str:
        """Generate download URL"""
```

---

## Detailed Interface Usage

### 1. Client Connection

#### Basic Connection

```python
from minio import Minio

# Local development (HTTP)
client = Minio(
    endpoint="localhost:9000",     # MinIO server address
    access_key="minioadmin",       # Default access key
    secret_key="minioadmin",       # Default secret key
    secure=False                   # Use HTTP (not HTTPS)
)

# Production (HTTPS)
client = Minio(
    endpoint="minio.example.com",
    access_key="your-access-key",
    secret_key="your-secret-key",
    secure=True,                   # Use HTTPS
    region="us-east-1"
)
```

#### S3-Compatible (AWS S3)

```python
# Connect to AWS S3
from minio import Minio

client = Minio(
    endpoint="s3.amazonaws.com",
    access_key="AWS_ACCESS_KEY_ID",
    secret_key="AWS_SECRET_ACCESS_KEY",
    secure=True,
    region="us-west-2"
)
```

#### Connection Pooling (urllib3)

```python
import urllib3
from minio import Minio

# Create HTTP client with connection pooling
http_client = urllib3.PoolManager(
    maxsize=10,                    # Max connections in pool
    cert_reqs='CERT_REQUIRED',
    ca_certs='/path/to/ca.crt',
    timeout=urllib3.Timeout.DEFAULT_TIMEOUT
)

client = Minio(
    endpoint="minio.example.com",
    access_key="access_key",
    secret_key="secret_key",
    secure=True,
    http_client=http_client        # Use custom HTTP client
)
```

---

### 2. Bucket Operations

#### Create Bucket

```python
# Check if bucket exists
bucket_name = "my-bucket"

if not client.bucket_exists(bucket_name):
    # Create bucket
    client.make_bucket(bucket_name, location="us-east-1")
    print(f"Bucket '{bucket_name}' created")
else:
    print(f"Bucket '{bucket_name}' already exists")
```

#### List All Buckets

```python
buckets = client.list_buckets()

for bucket in buckets:
    print(f"Bucket: {bucket.name}, Created: {bucket.creation_date}")
```

#### Delete Bucket

```python
# Remove bucket (must be empty)
try:
    client.remove_bucket("my-bucket")
    print("Bucket removed")
except Exception as e:
    print(f"Error: {e}")  # Bucket not empty or doesn't exist
```

---

### 3. Object Upload Operations

#### Upload from File-Like Object

```python
import io

# Upload from bytes
data = b"Hello, MinIO!"
data_stream = io.BytesIO(data)

result = client.put_object(
    bucket_name="my-bucket",
    object_name="hello.txt",       # Object key (can include path)
    data=data_stream,
    length=len(data),              # Must provide size
    content_type="text/plain"      # MIME type
)

print(f"Uploaded: {result.object_name}, ETag: {result.etag}")
```

#### Upload from Local File

```python
# Upload local file
result = client.fput_object(
    bucket_name="my-bucket",
    object_name="documents/report.pdf",  # Can include folder path
    file_path="/path/to/local/report.pdf",
    content_type="application/pdf"
)

print(f"Uploaded: {result.object_name}")
```

#### Upload with Custom Metadata

```python
# Add custom metadata
metadata = {
    "x-amz-meta-author": "Alice",   # Custom metadata (must start with x-amz-meta-)
    "x-amz-meta-department": "Engineering",
    "x-amz-meta-version": "1.0"
}

client.fput_object(
    bucket_name="my-bucket",
    object_name="docs/spec.pdf",
    file_path="/path/to/spec.pdf",
    content_type="application/pdf",
    metadata=metadata
)
```

#### Upload with Progress Callback

```python
def progress_callback(current, total):
    """Progress callback function"""
    percentage = (current / total) * 100
    print(f"Progress: {percentage:.2f}% ({current}/{total} bytes)")

# Upload with progress tracking
client.fput_object(
    bucket_name="my-bucket",
    object_name="large-file.zip",
    file_path="/path/to/large-file.zip",
    progress=progress_callback      # Track upload progress
)
```

#### Multipart Upload (Large Files)

```python
# Upload large file (auto multipart)
client.fput_object(
    bucket_name="my-bucket",
    object_name="videos/movie.mp4",
    file_path="/path/to/movie.mp4",
    content_type="video/mp4",
    part_size=10 * 1024 * 1024     # 10MB parts
)
```

---

### 4. Object Download Operations

#### Download as Stream

```python
# Download and read in chunks
response = client.get_object("my-bucket", "documents/report.pdf")

try:
    # Read in chunks
    with open("/tmp/downloaded.pdf", "wb") as f:
        for chunk in response.stream(32 * 1024):  # 32KB chunks
            f.write(chunk)
finally:
    response.close()
    response.release_conn()
```

#### Download to Local File

```python
# Download directly to file
client.fget_object(
    bucket_name="my-bucket",
    object_name="documents/report.pdf",
    file_path="/tmp/report.pdf"     # Local save path
)

print("File downloaded")
```

#### Partial Download (Range)

```python
# Download specific byte range
response = client.get_object(
    bucket_name="my-bucket",
    object_name="large-file.bin",
    offset=1024,                   # Start at byte 1024
    length=2048                    # Read 2048 bytes
)

data = response.read()
response.close()
response.release_conn()
```

#### Download with Progress

```python
def download_progress(current, total):
    print(f"Downloaded: {current}/{total} bytes")

client.fget_object(
    bucket_name="my-bucket",
    object_name="large-file.zip",
    file_path="/tmp/large-file.zip",
    progress=download_progress      # Track download progress
)
```

---

### 5. Object Info & Listing

#### Get Object Metadata

```python
# Get object stats
stat = client.stat_object("my-bucket", "documents/report.pdf")

print(f"Size: {stat.size} bytes")
print(f"ETag: {stat.etag}")
print(f"Content-Type: {stat.content_type}")
print(f"Last Modified: {stat.last_modified}")
print(f"Metadata: {stat.metadata}")
```

#### List Objects (Non-Recursive)

```python
# List top-level objects only
objects = client.list_objects("my-bucket", prefix="documents/")

for obj in objects:
    print(f"Object: {obj.object_name}, Size: {obj.size} bytes")
```

#### List Objects (Recursive)

```python
# List all objects recursively
objects = client.list_objects(
    bucket_name="my-bucket",
    prefix="documents/",           # Filter by prefix
    recursive=True                 # Include subdirectories
)

for obj in objects:
    print(f"{obj.object_name} ({obj.size} bytes)")
```

#### List with Pagination

```python
# List objects with pagination
def list_all_objects(bucket: str, prefix: str = "", page_size: int = 1000):
    """List all objects with pagination"""
    
    start_after = ""
    while True:
        objects = client.list_objects(
            bucket_name=bucket,
            prefix=prefix,
            start_after=start_after,
            recursive=True
        )
        
        count = 0
        for obj in objects:
            print(obj.object_name)
            start_after = obj.object_name
            count += 1
            
            if count >= page_size:
                break
        
        if count < page_size:
            break  # No more objects
```

---

### 6. Object Deletion

#### Delete Single Object

```python
# Delete object
client.remove_object("my-bucket", "documents/old-report.pdf")
print("Object deleted")
```

#### Delete Multiple Objects (Batch)

```python
from minio import DeleteObject

# Prepare delete list
delete_list = [
    DeleteObject("file1.txt"),
    DeleteObject("file2.txt"),
    DeleteObject("folder/file3.txt")
]

# Batch delete
errors = client.remove_objects("my-bucket", delete_list)

for error in errors:
    print(f"Error deleting {error.name}: {error.message}")
```

#### Delete All Objects in Prefix

```python
def delete_folder(bucket: str, prefix: str):
    """Delete all objects with given prefix (simulate folder deletion)"""
    
    # List all objects
    objects = client.list_objects(bucket, prefix=prefix, recursive=True)
    
    # Create delete list
    delete_list = [DeleteObject(obj.object_name) for obj in objects]
    
    # Batch delete
    errors = client.remove_objects(bucket, delete_list)
    
    for error in errors:
        print(f"Error: {error}")

# Delete all objects in "documents/" folder
delete_folder("my-bucket", "documents/")
```

---

### 7. Presigned URLs (Temporary Access)

#### Generate Download URL

```python
from datetime import timedelta

# Generate URL valid for 1 hour
url = client.presigned_get_object(
    bucket_name="my-bucket",
    object_name="documents/report.pdf",
    expires=timedelta(hours=1)     # URL expires in 1 hour
)

print(f"Download URL: {url}")
# Share this URL with users (no authentication needed)
```

#### Generate Upload URL

```python
# Generate URL for direct upload
upload_url = client.presigned_put_object(
    bucket_name="my-bucket",
    object_name="uploads/user-file.jpg",
    expires=timedelta(minutes=30)  # Expires in 30 minutes
)

print(f"Upload URL: {upload_url}")
# Users can upload directly to this URL via HTTP PUT
```

#### Custom Response Headers

```python
# Force download with custom filename
url = client.presigned_get_object(
    bucket_name="my-bucket",
    object_name="reports/data.csv",
    expires=timedelta(hours=2),
    response_headers={
        "response-content-type": "text/csv",
        "response-content-disposition": "attachment; filename=report-2026.csv"
    }
)
```

---

### 8. Copy Operations

#### Copy Object Within Same Bucket

```python
from minio import CopySource

# Copy object
source = CopySource("my-bucket", "documents/original.pdf")

client.copy_object(
    bucket_name="my-bucket",
    object_name="documents/copy.pdf",
    source=source
)
```

#### Copy Object Across Buckets

```python
# Copy from one bucket to another
source = CopySource("source-bucket", "path/to/file.txt")

client.copy_object(
    bucket_name="destination-bucket",
    object_name="new-path/file.txt",
    source=source
)
```

#### Copy with New Metadata

```python
# Copy and update metadata
source = CopySource("my-bucket", "old/file.pdf")

client.copy_object(
    bucket_name="my-bucket",
    object_name="new/file.pdf",
    source=source,
    metadata={
        "x-amz-meta-version": "2.0",  # New metadata
        "x-amz-meta-author": "Bob"
    }
)
```

---

### 9. Runtime Integration (Match3 Project)

#### Runtime Interface Implementation

```python
from minio import Minio
from typing import Protocol

class IMinioClient(Protocol):
    """MinIO client interface for dependency injection"""
    def put_object(self, bucket_name: str, object_name: str, data: BinaryIO, length: int, **kwargs) -> Any: ...
    def get_object(self, bucket_name: str, object_name: str) -> Any: ...
    def fput_object(self, bucket_name: str, object_name: str, file_path: str, **kwargs) -> Any: ...
    def fget_object(self, bucket_name: str, object_name: str, file_path: str) -> Any: ...
    def remove_object(self, bucket_name: str, object_name: str) -> None: ...
    def presigned_get_object(self, bucket_name: str, object_name: str, expires: timedelta) -> str: ...

def build_minio_client(config: MinioConfig) -> IMinioClient:
    """Build MinIO client from config"""
    return Minio(
        endpoint=config.endpoint,
        access_key=config.access_key,
        secret_key=config.secret_key,
        secure=config.secure
    )
```

#### Injecting into Runtime

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Match3Runtime:
    """Runtime dependency container (immutable)"""
    
    minio_client: IMinioClient  # MinIO client interface
    # ... other dependencies

def build_runtime(config: Config) -> Match3Runtime:
    """Build runtime with all dependencies"""
    
    minio_client = build_minio_client(config.minio)
    
    return Match3Runtime(
        minio_client=minio_client,
        # ... other dependencies
    )
```

#### Usage in Repository (File Storage)

```python
import io
from datetime import timedelta

class FileStorageRepository:
    """Repository for file storage with MinIO"""
    
    def __init__(self, runtime: Match3Runtime):
        self._minio = runtime.minio_client
        self._bucket = "match3-files"
    
    async def upload_file(
        self,
        file_content: bytes,
        object_key: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """Upload file and return object key"""
        
        # Upload to MinIO
        data_stream = io.BytesIO(file_content)
        self._minio.put_object(
            bucket_name=self._bucket,
            object_name=object_key,
            data=data_stream,
            length=len(file_content),
            content_type=content_type
        )
        
        return object_key
    
    async def get_download_url(
        self,
        object_key: str,
        expires_hours: int = 24
    ) -> str:
        """Generate temporary download URL"""
        
        url = self._minio.presigned_get_object(
            bucket_name=self._bucket,
            object_name=object_key,
            expires=timedelta(hours=expires_hours)
        )
        
        return url
    
    async def delete_file(self, object_key: str):
        """Delete file from storage"""
        
        self._minio.remove_object(
            bucket_name=self._bucket,
            object_name=object_key
        )
```

---

## Why MinIO v2026.04.11?

### Key Features

1. **S3 Compatibility**
   - 100% compatible with AWS S3 API
   - Easy migration from/to AWS
   - Works with S3 tools and SDKs

2. **High Performance**
   - Designed for large-scale data
   - Supports multi-node distributed deployment
   - Optimized for SSD and NVMe storage

3. **Kubernetes Native**
   - Official Kubernetes Operator
   - Auto-scaling support
   - StatefulSet deployment

4. **Multi-Tenancy**
   - User and policy management
   - Bucket-level access control
   - IAM integration

### When to Use MinIO

✅ **Use MinIO when**:
- Storing large binary files (images, videos, documents)
- Need S3-compatible object storage
- Self-hosted solution (not cloud-dependent)
- Large-scale file storage with high availability
- Cost-effective alternative to AWS S3

❌ **Don't use MinIO when**:
- Small structured data (use PostgreSQL)
- Frequent small updates to files (use PostgreSQL BYTEA)
- Need transactional guarantees (use PostgreSQL)
- Text search required (use Elasticsearch)

---

## Integration with Match3 Architecture

```
┌─────────────────────────────────────────────────┐
│                  FastAPI Layer                  │
│           (File Upload Endpoint)                │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│         FileStorageRepository                   │
│  - upload_file()                                │
│  - get_download_url()                           │
│  - delete_file()                                │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│         Match3Runtime.minio_client              │
│       (IMinioClient Protocol)                   │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│            MinIO Server                         │
│    (v2026.04.11, Object Storage)                │
└─────────────────────────────────────────────────┘
```

**Data Flow**:
1. User uploads file via FastAPI multipart/form-data
2. Repository receives file bytes
3. Runtime provides MinIO client interface
4. MinIO stores file and returns ETag
5. Repository returns object key or presigned URL

---

## Configuration Example

```python
from pydantic import BaseModel

class MinioConfig(BaseModel):
    """MinIO configuration"""
    
    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    secure: bool = False
    region: str | None = None
    
    # Bucket settings
    default_bucket: str = "match3-files"
    url_expiry_hours: int = 24
```

---

## Best Practices

1. **Object Naming**
   - Use meaningful keys: `users/{user_id}/avatar.jpg`
   - Include file extension for content-type detection
   - Avoid special characters

2. **Security**
   - Always use presigned URLs for temporary access
   - Don't expose MinIO credentials to frontend
   - Use bucket policies to restrict access

3. **Performance**
   - Use multipart upload for files > 5MB
   - Enable connection pooling
   - Use lifecycle policies to clean old files

4. **Metadata**
   - Store file metadata in PostgreSQL
   - Use MinIO only for binary storage
   - Link files with database records via object key

5. **Backup**
   - Enable bucket versioning for important data
   - Set up regular backups
   - Use lifecycle policies for automatic archiving
