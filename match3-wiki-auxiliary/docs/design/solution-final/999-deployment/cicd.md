# 云服务器配置与部署

本文说明 match3-wiki 生产部署所需的云服务器硬件规格、Docker Compose 生产配置、远程管理脚本 `remote.sh`，以及 Nginx 配置与日常运维命令。

---

## 一、云服务器配置推荐

### 1.1 选型原则

本系统运行以下计算密集型本地模型：

| 模型 | 显存需求 | 备注 |
|------|---------|------|
| Whisper large-v3 | ~3 GB VRAM | 音视频转录 |
| CLIP ViT-L/14 | ~1.5 GB VRAM | 图像向量化 |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | ~0.5 GB VRAM | 重排序 |
| text-embedding-3-small | 无（OpenAI API） | 文本向量化 |
| GPT-4o / Claude | 无（云 API） | LLM 推理 |

本地模型合计约需 **5–6 GB VRAM**。若使用 GPU 推理，选 16 GB VRAM 规格留有余量；若 GPU 不可用，可切换至 `faster-whisper`（CPU 可用，速度可接受）。

---

### 1.2 推荐配置（GPU 版本）

适用于**生产 + 开发共用**一台机器的场景：

| 资源 | 规格 | 说明 |
|------|------|------|
| CPU | 8 vCPU（e.g., AMD EPYC / Intel Xeon） | Celery workers 并发 |
| 内存 | 32 GB RAM | PostgreSQL(4G) + Milvus(8G) + ES(6G) + Neo4j(4G) + 应用层 |
| GPU | 1× NVIDIA A10G（24 GB VRAM） 或 RTX 3090/4090 | Whisper + CLIP + 重排序 |
| 系统盘 | 100 GB SSD | 系统 + Docker 镜像 |
| 数据盘 | 500 GB SSD（独立挂载至 `/data`） | PostgreSQL/Milvus/ES/MinIO 持久化 |
| 网络 | 100 Mbps 上行 | 文件上传 |

推荐云厂商实例型号（参考）：

| 厂商 | 实例型号 | 配置 |
|------|---------|------|
| AWS | g5.2xlarge | 8 vCPU / 32 GB RAM / A10G 24GB |
| 阿里云 | gn6i.2xlarge | 8 vCPU / 32 GB RAM / V100 16GB |
| 腾讯云 | GN10Xp.2XLARGE40 | 8 vCPU / 40 GB RAM / V100 32GB |
| 华为云 | p2s.2xlarge.8 | 8 vCPU / 64 GB RAM / V100 16GB |

---

### 1.3 最低配置（CPU 版本 / 开发测试）

若无 GPU 预算，使用 `faster-whisper` 替代 Whisper large-v3，CLIP/reranker 仍可 CPU 推理（速度较慢）：

| 资源 | 规格 |
|------|------|
| CPU | 8 vCPU |
| 内存 | 32 GB RAM |
| 存储 | 200 GB SSD |
| GPU | 无 |

将 `docker-compose.prod.yml` 中 `deploy.resources.reservations.devices` 部分移除即可退回 CPU 模式。

---

## 二、服务器初始化

```bash
# 1. Install Docker + Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 2. Install NVIDIA Container Toolkit (GPU servers only)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# 3. Mount data disk (assuming device is /dev/vdb)
sudo mkfs.ext4 /dev/vdb
sudo mkdir -p /data
echo '/dev/vdb /data ext4 defaults 0 0' | sudo tee -a /etc/fstab
sudo mount -a

# 4. Create data directories
sudo mkdir -p /data/{postgres,redis,milvus,elasticsearch,neo4j,minio,logs}
sudo chown -R 1000:1000 /data

# 5. Create project directory and copy .env
sudo mkdir -p /opt/match3-wiki
# Copy .env.example to /opt/match3-wiki/.env and fill in real values
```

---

## 三、生产 Docker Compose

生产配置在 `docker-compose.prod.yml`，与开发版的主要差异：

- 显式资源限制（防止单个服务耗尽内存）
- 数据目录挂载到 `/data/`（持久化）
- `restart: unless-stopped`（自动重启）
- 移除 flower（监控可接 Grafana 替代）
- API 服务通过 Nginx 反向代理暴露
- `APP_ENV=production`（控制错误链暴露行为，详见 `090-error/error-design.md`）

```yaml
# docker-compose.prod.yml
version: "3.9"

x-common-env: &common-env
  POSTGRES_URL: postgresql+psycopg2://match3:${POSTGRES_PASSWORD}@postgres:5432/match3
  REDIS_URL: redis://redis:6379/0
  MILVUS_URI: http://milvus:19530
  ELASTICSEARCH_URL: http://elasticsearch:9200
  NEO4J_URI: bolt://neo4j:7687
  NEO4J_USER: neo4j
  NEO4J_PASSWORD: ${NEO4J_PASSWORD}
  MINIO_ENDPOINT: minio:9000
  MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY}
  MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}
  MINIO_BUCKET: match3-raw
  OPENAI_API_KEY: ${OPENAI_API_KEY}
  ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
  LLM_MODEL: gpt-4o
  EMBED_MODEL: text-embedding-3-small
  RERANK_MODEL: cross-encoder/ms-marco-MiniLM-L-6-v2
  PAGEINDEX_API_KEY: ${PAGEINDEX_API_KEY}
  JWT_SECRET: ${JWT_SECRET}
  CELERY_BROKER_URL: redis://redis:6379/1
  CELERY_RESULT_BACKEND: redis://redis:6379/2
  APP_ENV: production
  LOG_LEVEL: info

services:

  postgres:
    image: postgres:18-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: match3
      POSTGRES_USER: match3
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - /data/postgres:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 4G

  redis:
    image: redis:8.6.2-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - /data/redis:/data
    deploy:
      resources:
        limits:
          memory: 2G

  minio:
    image: minio/minio:RELEASE.2025-10-15
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    volumes:
      - /data/minio:/data
    deploy:
      resources:
        limits:
          memory: 2G

  milvus:
    image: milvusdb/milvus:v2.6.14
    restart: unless-stopped
    command: milvus run standalone
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    volumes:
      - /data/milvus:/var/lib/milvus
    depends_on:
      - etcd
      - minio
    deploy:
      resources:
        limits:
          memory: 8G

  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    restart: unless-stopped
    environment:
      ETCD_AUTO_COMPACTION_MODE: revision
      ETCD_AUTO_COMPACTION_RETENTION: "1000"
      ETCD_QUOTA_BACKEND_BYTES: "4294967296"
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd
    volumes:
      - /data/milvus/etcd:/etcd

  neo4j:
    image: neo4j:2026.03.1
    restart: unless-stopped
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - /data/neo4j:/data
    deploy:
      resources:
        limits:
          memory: 4G

  elasticsearch:
    image: elasticsearch:9.3.3
    restart: unless-stopped
    environment:
      discovery.type: single-node
      xpack.security.enabled: "false"
      ES_JAVA_OPTS: "-Xms2g -Xmx2g"
    volumes:
      - /data/elasticsearch:/usr/share/elasticsearch/data
    deploy:
      resources:
        limits:
          memory: 6G

  api:
    build:
      context: .
      dockerfile: docker/api/Dockerfile
    restart: unless-stopped
    environment:
      <<: *common-env
    ports:
      - "127.0.0.1:8000:8000"   # localhost only — exposed externally via Nginx reverse proxy
    depends_on:
      - postgres
      - redis
      - milvus
      - elasticsearch
      - neo4j
    deploy:
      resources:
        limits:
          memory: 2G

  worker-ingest:
    build:
      context: .
      dockerfile: docker/worker/Dockerfile
    restart: unless-stopped
    command: celery -A app.workers.celery_app worker -Q ingest,embed --concurrency=4 --loglevel=info
    environment:
      <<: *common-env
    volumes:
      - /tmp/match3-ingest:/tmp/match3-ingest
    depends_on:
      - redis
      - postgres
      - minio
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  worker-graph:
    build:
      context: .
      dockerfile: docker/worker/Dockerfile
    restart: unless-stopped
    command: celery -A app.workers.celery_app worker -Q graph --concurrency=2 --loglevel=info
    environment:
      <<: *common-env
    depends_on:
      - redis
      - neo4j
    deploy:
      resources:
        limits:
          memory: 4G

  worker-compile:
    build:
      context: .
      dockerfile: docker/worker/Dockerfile
    restart: unless-stopped
    command: celery -A app.workers.celery_app worker -Q compile --concurrency=2 --loglevel=info
    environment:
      <<: *common-env
    depends_on:
      - redis
      - postgres
    deploy:
      resources:
        limits:
          memory: 4G

  worker-rag:
    build:
      context: .
      dockerfile: docker/worker/Dockerfile
    restart: unless-stopped
    command: celery -A app.workers.celery_app worker -Q rag --concurrency=4 --loglevel=info
    environment:
      <<: *common-env
    depends_on:
      - redis
      - milvus
      - elasticsearch
    deploy:
      resources:
        limits:
          memory: 4G

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - /data/ssl:/etc/ssl/match3:ro
    depends_on:
      - api
```

---

## 四、远程 Makefile

`Makefile` 放在项目根目录，随代码一起上传到服务器。`remote.sh` 部署后通过 SSH 调用对应的 make target 完成服务管理。

```makefile
# Makefile — remote service management targets
# All targets are invoked via SSH by remote.sh after code upload.

COMPOSE := docker compose -f docker-compose.prod.yml

.PHONY: deploy deploy-infra deploy-backend deploy-frontend migrate \
        restart restart-backend restart-frontend \
        stop status logs logs-backend logs-workers undeploy

# --- Full deploy (first-time or complete rebuild) ---

deploy: deploy-infra migrate deploy-backend deploy-frontend

deploy-infra:
	$(COMPOSE) up -d postgres redis milvus etcd elasticsearch neo4j minio

deploy-backend:
	$(COMPOSE) up -d --build api worker-ingest worker-graph worker-compile worker-rag

deploy-frontend:
	$(COMPOSE) up -d --build nginx

# --- Database migration ---

migrate:
	$(COMPOSE) run --rm api alembic upgrade head

# --- Restart targets ---

restart:
	$(COMPOSE) restart

restart-backend:
	$(COMPOSE) restart api worker-ingest worker-graph worker-compile worker-rag

restart-frontend:
	$(COMPOSE) restart nginx

# --- Monitoring ---

stop:
	$(COMPOSE) stop

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs --tail=100 -f

logs-backend:
	$(COMPOSE) logs api --tail=100 -f

logs-workers:
	$(COMPOSE) logs worker-ingest worker-graph worker-compile worker-rag --tail=50 -f

# --- Destroy ---

undeploy:
	$(COMPOSE) down -v
```

---

## 五、部署脚本 `remote.sh`

### 5.1 设计说明

`remote.sh` 放在本地开发机的项目 `tools/` 目录下，**不上传到服务器**。流程如下：

```
local: read .env → verify SSH → create tar → scp upload → SSH extract → SSH run make <target>
```

| 操作 | 说明 |
|------|------|
| `--deploy-backend` | 上传代码 + `make deploy-backend`（重建并重启后端容器） |
| `--deploy-frontend` | 上传代码 + `make deploy-frontend`（重建并重启 Nginx/Next.js） |
| `--deploy-all` | 上传代码 + `make deploy`（基础设施 + 迁移 + 后端 + 前端全量部署） |
| `--deploy-frontend --light` | 仅上传代码，跳过 `make deploy-frontend`（代码热更新，无需重启） |
| `--run <target>` | SSH 远程执行 `make <target>`（不上传代码，用于远程控制） |
| `--undeploy` | 确认后执行 `make undeploy`（停止并销毁所有容器和卷） |

### 5.2 .env.example

```bash
# tools/.env.example — copy to tools/.env and fill in real values

# SSH credentials
SSH_KEY=/path/to/your/ssh/private/key
SSH_USER=ubuntu
SSH_HOST=1.2.3.4

# Paths
REMOTE_PROJECT_DIR=/opt/match3-wiki
LOCAL_PROJECT_DIR=/path/to/local/match3-wiki

# Service URLs (for health checks and info display)
BACKEND_URL=https://api.match3wiki.com
FRONTEND_URL=https://match3wiki.com
```

### 5.3 脚本 `tools/remote.sh`

```bash
#!/bin/bash
# match3-wiki remote management script
# Usage: ./remote.sh [OPTIONS]

set -e

# ============================================================================
# Help text
# ============================================================================

show_help() {
    echo "match3-wiki remote management script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Deploy commands:"
    echo "  --deploy-backend          Upload code + make deploy-backend"
    echo "  --deploy-frontend         Upload code + make deploy-frontend"
    echo "  --deploy-all              Upload code + make deploy (full-stack deploy)"
    echo "  --light                   Upload code only, skip make target (use with --deploy-frontend or --deploy-all)"
    echo ""
    echo "Remote make control:"
    echo "  --run <target> [args...]  Execute on remote server: make <target>"
    echo "                            Examples: --run status, --run logs-backend, --run migrate"
    echo ""
    echo "Destroy commands:"
    echo "  --undeploy                Stop and remove all containers + volumes (requires confirmation)"
    echo "  -f, --force               Skip confirmation prompt for --undeploy"
    echo ""
    echo "Other:"
    echo "  -h, --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --deploy-all                     # First-time full deploy"
    echo "  $0 --deploy-backend                 # Rebuild and restart backend containers"
    echo "  $0 --deploy-frontend                # Rebuild and restart frontend/Nginx"
    echo "  $0 --deploy-frontend --light        # Upload frontend code only (no restart)"
    echo "  $0 --run status                     # Check remote service status"
    echo "  $0 --run logs-backend               # Tail backend API logs"
    echo "  $0 --run migrate                    # Run DB migration only"
    echo "  $0 --run restart-backend            # Restart backend (no rebuild)"
    echo "  $0 --undeploy --force               # Destroy everything without confirmation"
}

# ============================================================================
# Constants (populated after load_environment runs)
# ============================================================================

declare SCRIPT_DIR
declare SSH_KEY SSH_USER SSH_HOST
declare REMOTE_PROJECT_DIR LOCAL_PROJECT_DIR
declare BACKEND_URL FRONTEND_URL

# Package variables (set by create_package)
declare PACKAGE_PATH PACKAGE_NAME TEMP_DIR

# Files that are never uploaded
BACKEND_EXCLUDE="__pycache__ .pytest_cache .mypy_cache"
FRONTEND_EXCLUDE="node_modules .next .env.local"

# Files to preserve on remote during subsequent deploys (never overwritten)
REMOTE_PRESERVE=".env"

IS_FIRST_DEPLOY=false

# ============================================================================
# Main operations
# ============================================================================

main_deploy() {
    local mode="$1"   # backend | frontend | all (fixed values)
    load_environment
    print_banner "match3-wiki deploy ($mode)"
    verify_ssh_connection

    if is_first_deploy; then
        IS_FIRST_DEPLOY=true
        if [ "$ARG_LIGHT" = true ]; then
            echo "Error: --light cannot be used for first-time deploy"
            exit 1
        fi
    fi

    upload_package "$mode"

    if [ "$ARG_LIGHT" = true ]; then
        echo ""
        echo "Light mode: code uploaded, skipping make target"
        echo "Run '$0 --run deploy-frontend' to restart manually"
        print_completion "light deploy ($mode)"
        return
    fi

    case "$mode" in
        backend)  run_remote_make "deploy-backend" ;;
        frontend) run_remote_make "deploy-frontend" ;;
        all)      run_remote_make "deploy" ;;
    esac

    print_completion "deploy ($mode)"
    display_service_info
}

main_run() {
    local target="$1"
    load_environment
    print_banner "match3-wiki remote make: $target"
    verify_ssh_connection
    run_remote_make "$target"
    print_completion "remote make: $target"
}

main_undeploy() {
    load_environment
    print_banner "match3-wiki destroy"

    if [ "$ARG_FORCE" != true ]; then
        echo "WARNING: This will stop and remove all containers, volumes, and data!"
        echo ""
        echo "Includes:"
        echo "  - All running Docker containers (api, workers, nginx, postgres, redis, milvus, etc.)"
        echo "  - All Docker volumes (database data, vector store, file storage)"
        echo "  - This operation is irreversible"
        echo ""
        read -p "Type 'DELETE' to confirm: " confirm
        if [ "$confirm" != "DELETE" ]; then
            echo "Cancelled."
            exit 0
        fi
        echo ""
    fi

    verify_ssh_connection
    run_remote_make "undeploy"
    print_completion "destroy"
}

# ============================================================================
# Helper functions
# ============================================================================

load_environment() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        echo "Error: .env file not found: $SCRIPT_DIR/.env"
        echo "      Copy .env.example to .env and fill in the values"
        exit 1
    fi
    source "$SCRIPT_DIR/.env"

    local missing=""
    [ -z "$SSH_KEY" ]              && missing="$missing SSH_KEY"
    [ -z "$SSH_USER" ]             && missing="$missing SSH_USER"
    [ -z "$SSH_HOST" ]             && missing="$missing SSH_HOST"
    [ -z "$REMOTE_PROJECT_DIR" ]   && missing="$missing REMOTE_PROJECT_DIR"
    [ -z "$LOCAL_PROJECT_DIR" ]    && missing="$missing LOCAL_PROJECT_DIR"

    if [ -n "$missing" ]; then
        echo "Error: missing required .env variables:$missing"
        exit 1
    fi

    echo "Environment loaded"
    echo "  SSH target : $SSH_USER@$SSH_HOST"
    echo "  Remote dir : $REMOTE_PROJECT_DIR"
}

print_banner() {
    local title="$1"
    echo ""
    echo "=========================================="
    echo "  $title"
    echo "=========================================="
    echo "  Target : $SSH_USER@$SSH_HOST"
    echo "  Path   : $REMOTE_PROJECT_DIR"
    echo "  Time   : $(date)"
    echo "=========================================="
    echo ""
}

verify_ssh_connection() {
    echo "Step 1: Verifying SSH connection..."
    if ! ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o BatchMode=yes \
            "$SSH_USER@$SSH_HOST" "echo ok" >/dev/null 2>&1; then
        echo "Error: SSH connection failed"
        echo "  Key  : $SSH_KEY"
        echo "  Host : $SSH_USER@$SSH_HOST"
        exit 1
    fi
    echo "SSH connection OK"
}

is_first_deploy() {
    ssh -i "$SSH_KEY" "$SSH_USER@$SSH_HOST" "[ ! -d '$REMOTE_PROJECT_DIR' ]"
}

upload_package() {
    local mode="$1"
    create_package "$mode"
    push_package
    extract_on_remote
}

create_package() {
    local mode="$1"
    echo "Step 2: Creating package (mode=$mode)..."

    TEMP_DIR=$(mktemp -d)
    PACKAGE_NAME="match3-wiki-$(date +%Y%m%d-%H%M%S).tar.gz"
    PACKAGE_PATH="$TEMP_DIR/$PACKAGE_NAME"

    cd "$LOCAL_PROJECT_DIR"

    # Build exclude arguments
    local exclude_args=""

    # Always exclude backend build artifacts
    for item in $BACKEND_EXCLUDE; do
        exclude_args="$exclude_args --exclude='./$item' --exclude='*/$item'"
    done

    # For frontend-only deploys, also exclude frontend build artifacts
    if [ "$mode" = "frontend" ]; then
        for item in $FRONTEND_EXCLUDE; do
            exclude_args="$exclude_args --exclude='./$item'"
        done
    fi

    # Subsequent deploys: exclude .env (preserved on remote, never overwritten)
    if [ "$IS_FIRST_DEPLOY" = false ]; then
        for item in $REMOTE_PRESERVE; do
            exclude_args="$exclude_args --exclude='./$item'"
        done
    fi

    # Create tar archive — --no-xattrs prevents macOS xattr warnings
    # --exclude='._*' prevents AppleDouble files from polluting the remote
    eval tar --no-xattrs --exclude='._*' $exclude_args -czf "$PACKAGE_PATH" .

    echo "Package ready: $PACKAGE_PATH ($(du -h "$PACKAGE_PATH" | cut -f1))"
}

push_package() {
    echo "Step 3: Uploading package..."

    ssh -i "$SSH_KEY" "$SSH_USER@$SSH_HOST" "mkdir -p '$REMOTE_PROJECT_DIR'"
    if ! scp -i "$SSH_KEY" "$PACKAGE_PATH" "$SSH_USER@$SSH_HOST:$REMOTE_PROJECT_DIR/"; then
        echo "Error: scp upload failed"
        rm -rf "$TEMP_DIR"
        exit 1
    fi

    echo "Upload complete"
}

extract_on_remote() {
    echo "Step 4: Extracting on remote..."

    # Subsequent deploys: stop services before overwriting files
    if [ "$IS_FIRST_DEPLOY" = false ]; then
        echo "Stopping running services..."
        ssh -i "$SSH_KEY" "$SSH_USER@$SSH_HOST" "
            cd '$REMOTE_PROJECT_DIR' 2>/dev/null || exit 0
            if [ -f Makefile ]; then
                make stop 2>/dev/null || true
            fi
        "
    fi

    # Extract (overwrite everything; preserved files were excluded from the package)
    ssh -i "$SSH_KEY" "$SSH_USER@$SSH_HOST" "
        cd '$REMOTE_PROJECT_DIR'
        tar -xzf '$PACKAGE_NAME'
        rm -f '$PACKAGE_NAME'
    "

    rm -rf "$TEMP_DIR"
    echo "Extraction complete"
}

run_remote_make() {
    local target="$1"
    echo "Running: make $target on $SSH_USER@$SSH_HOST..."

    ssh -i "$SSH_KEY" \
        -o ConnectTimeout=60 \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=10 \
        "$SSH_USER@$SSH_HOST" "
        set -e
        cd '$REMOTE_PROJECT_DIR'
        make $target
    " || {
        echo "Error: remote make $target failed"
        exit 1
    }

    echo "make $target completed"
}

print_completion() {
    local op="$1"
    echo ""
    echo "=========================================="
    echo "  $op complete"
    echo "=========================================="
    echo "  Time: $(date)"
    echo ""
}

display_service_info() {
    echo "Service URLs:"
    [ -n "$BACKEND_URL" ]  && echo "  API : $BACKEND_URL/docs"
    [ -n "$FRONTEND_URL" ] && echo "  App : $FRONTEND_URL"
    echo ""
    echo "Common commands:"
    echo "  $0 --run status           # check container status"
    echo "  $0 --run logs-backend     # tail API logs"
    echo "  $0 --run logs-workers     # tail worker logs"
    echo "  ssh -i $SSH_KEY $SSH_USER@$SSH_HOST"
    echo ""
}

# ============================================================================
# Argument parser
# ============================================================================

ACTION=""
ARG_LIGHT=false
ARG_FORCE=false
RUN_TARGET=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --deploy-backend)
            ACTION="deploy-backend"; shift ;;
        --deploy-frontend)
            ACTION="deploy-frontend"; shift ;;
        --deploy-all)
            ACTION="deploy-all"; shift ;;
        --light)
            ARG_LIGHT=true; shift ;;
        --run)
            ACTION="run"
            shift
            RUN_TARGET=""
            while [[ $# -gt 0 ]]; do
                RUN_TARGET="$RUN_TARGET $1"
                shift
            done
            RUN_TARGET="${RUN_TARGET# }"
            ;;
        --undeploy)
            ACTION="undeploy"; shift ;;
        -f|--force)
            ARG_FORCE=true; shift ;;
        -h|--help)
            show_help; exit 0 ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage"
            exit 1 ;;
    esac
done

# Validate --light usage
if [ "$ARG_LIGHT" = true ] && [[ "$ACTION" != "deploy-frontend" && "$ACTION" != "deploy-all" ]]; then
    echo "Error: --light can only be used with --deploy-frontend or --deploy-all"
    exit 1
fi

if [[ -z "$ACTION" ]]; then
    echo "Error: no action specified"
    echo "Run '$0 --help' for usage"
    exit 1
fi

if [[ "$ACTION" == "run" && -z "$RUN_TARGET" ]]; then
    echo "Error: --run requires a make target"
    echo "  Example: $0 --run status"
    exit 1
fi

# Dispatch
case $ACTION in
    deploy-backend)  main_deploy "backend" ;;
    deploy-frontend) main_deploy "frontend" ;;
    deploy-all)      main_deploy "all" ;;
    run)             main_run "$RUN_TARGET" ;;
    undeploy)        main_undeploy ;;
    *)
        echo "Error: invalid action: $ACTION"; exit 1 ;;
esac
```

### 5.4 首次部署流程

```bash
# 1. Copy and fill in tools/.env
cp tools/.env.example tools/.env
# Edit tools/.env: fill in SSH_KEY, SSH_USER, SSH_HOST, REMOTE_PROJECT_DIR, LOCAL_PROJECT_DIR

# 2. Ensure the remote server already has a .env with production secrets
#    Copy .env.example to /opt/match3-wiki/.env on the server and fill in the secrets
#    (one-time manual step — remote.sh will never overwrite .env)

# 3. First-time full deploy (infrastructure + migration + backend + frontend)
./tools/remote.sh --deploy-all
```

### 5.5 日常更新流程

```bash
# Update backend only (rebuild API + Workers)
./tools/remote.sh --deploy-backend

# Update frontend only (rebuild Nginx + Next.js)
./tools/remote.sh --deploy-frontend

# Lightweight frontend update (upload source only, no container restart)
./tools/remote.sh --deploy-frontend --light

# Run DB migration only
./tools/remote.sh --run migrate

# Check service status
./tools/remote.sh --run status

# Tail API logs
./tools/remote.sh --run logs-backend

# Restart backend containers (no rebuild)
./tools/remote.sh --run restart-backend
```

---

## 六、Nginx 配置（生产）

```nginx
# docker/nginx/nginx.conf
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    ssl_certificate     /etc/ssl/match3/fullchain.pem;
    ssl_certificate_key /etc/ssl/match3/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # SSE streaming — disable buffering
    location /api/v1/qa/ask {
        proxy_pass          http://api:8000;
        proxy_http_version  1.1;
        proxy_set_header    Connection "";
        proxy_buffering     off;
        proxy_cache         off;
        proxy_read_timeout  300s;
        chunked_transfer_encoding on;
    }

    location / {
        proxy_pass          http://api:8000;
        proxy_set_header    Host $host;
        proxy_set_header    X-Real-IP $remote_addr;
        proxy_set_header    X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header    X-Forwarded-Proto $scheme;
        client_max_body_size 500M;   # allow large file uploads
        proxy_read_timeout  120s;
    }
}
```

---

## 七、日常运维命令

以下命令直接在服务器上执行（SSH 登录后），或通过 `./tools/remote.sh --run <target>` 远程触发。

```bash
# Check status of all services
make status
# Equivalent: docker compose -f docker-compose.prod.yml ps

# Tail API logs
make logs-backend
# Equivalent: docker compose -f docker-compose.prod.yml logs api --tail=100 -f

# View worker failure records
docker compose -f docker-compose.prod.yml logs worker-ingest | grep '"event":"task_failure"' | tail -20

# Run DB migration manually
make migrate
# Equivalent: docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# Restart a single service (no rebuild)
docker compose -f docker-compose.prod.yml restart api

# Back up PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U match3 match3 | gzip > /data/backups/match3-$(date +%Y%m%d).sql.gz

# Clean up old Docker images (free disk space)
docker image prune -f --filter "until=720h"
```
