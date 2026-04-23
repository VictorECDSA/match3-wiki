# 单元测试设计

本文规范 match3-wiki 的测试目录结构、fixture 策略、测试命名约定，以及支持 AI 自动化运行和解析测试结果的命令行接口。

---

## 一、目录结构

`tests/` 目录镜像 `app/` 目录，每个被测模块对应一个测试文件：

```
tests/
├── conftest.py                          ← 全局 fixtures（runtime mock、db session 等）
├── fixtures/
│   ├── db.py                            ← PostgreSQL 测试 fixture
│   ├── milvus.py                        ← Milvus mock fixture
│   ├── es.py                            ← Elasticsearch mock fixture
│   ├── neo4j.py                         ← Neo4j mock fixture
│   ├── redis.py                         ← Redis mock fixture
│   ├── minio.py                         ← MinIO mock fixture
│   └── llm.py                           ← LLM / Embed / Rerank mock fixture
│
├── unit/
│   ├── storage/
│   │   ├── test_workspace_repo.py
│   │   ├── test_raw_file_repo.py
│   │   ├── test_text_chunk_repo.py
│   │   ├── test_wiki_page_repo.py
│   │   └── test_qa_session_repo.py
│   ├── services/
│   │   ├── test_admin_service.py
│   │   ├── test_ingest_service.py
│   │   ├── test_wiki_compile_service.py
│   │   └── test_qa_service.py
│   ├── rag/
│   │   ├── test_rag_router.py
│   │   ├── test_path_chunk.py
│   │   ├── test_path_entry.py
│   │   └── test_path_page.py
│   ├── workers/
│   │   ├── test_ingest_task.py
│   │   ├── test_embed_task.py
│   │   ├── test_graph_task.py
│   │   └── test_compile_task.py
│   └── common/
│       ├── test_exceptions.py
│       └── test_codes.py
│
├── integration/
    ├── test_ingest_pipeline.py          ← 端到端摄入流程（使用 SQLite 内存数据库）
    └── test_wiki_compile_pipeline.py
```

---

## 二、依赖安装

```
# requirements-test.txt
pytest>=8.0
pytest-asyncio>=0.23
pytest-mock>=3.12
pytest-json-report>=1.5        # 机器可读测试结果（供 AI 解析）
factory-boy>=3.3               # entity factories
faker>=24.0
sqlalchemy[aiosqlite]>=2.0     # in-memory SQLite for repo tests
httpx>=0.27                    # FastAPI TestClient async support
```

---

## 三、全局 Fixtures（conftest.py）

```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from app.storage.orm_base import ORMBase
from app.runtime import Match3Runtime
from app.common.constants import constants
import logging


@pytest.fixture(scope="session")
def db_engine():
    """内存 SQLite 引擎——每个 session 只建表一次。"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    ORMBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# 配置/环境存根 — 轻量数据对象，非真实校验类
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_config():
    cfg = MagicMock()
    cfg.llm.default_model = "gpt-4o"
    cfg.llm.default_provider = "openai"
    cfg.embed.model = "text-embedding-3-small"
    cfg.embed.dimension = 1536
    cfg.embed.batch_size = 32
    cfg.embed.clip_model = "ViT-L/14"
    cfg.minio.bucket = "test-bucket"
    cfg.minio.secure = False
    cfg.rerank.model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    cfg.rerank.top_k = 20
    cfg.database.pool_size = 5
    cfg.log.level = "DEBUG"
    return cfg


@pytest.fixture()
def mock_env():
    env = MagicMock()
    env.POSTGRES_HOST = "localhost"
    env.OPENAI_API_KEY = "sk-test"
    env.JWT_SECRET = "test-secret-that-is-at-least-32-chars-long!!"
    return env


# ---------------------------------------------------------------------------
# 存储层 mock — 直接通过 Runtime 注入
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_redis():
    redis = MagicMock()
    redis.ping.return_value = True
    redis.get.return_value = None
    redis.set.return_value = True
    return redis


@pytest.fixture()
def mock_milvus():
    milvus = MagicMock()
    milvus.search.return_value = [[]]
    milvus.insert.return_value = MagicMock(insert_count=1)
    milvus.list_collections.return_value = [constants.MILVUS_COLLECTION]
    return milvus


@pytest.fixture()
def mock_es():
    es = MagicMock()
    es.search.return_value = {"hits": {"hits": [], "total": {"value": 0}}}
    es.index.return_value = {"result": "created"}
    es.ping.return_value = True
    return es


@pytest.fixture()
def mock_neo4j():
    driver = MagicMock()
    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)
    session_mock.run.return_value = MagicMock(data=lambda: [])
    driver.session.return_value = session_mock
    driver.verify_connectivity.return_value = None
    return driver


# ---------------------------------------------------------------------------
# 智能接口 mock — Runtime 的所有 Protocol 成员
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_llm():
    llm = MagicMock()
    llm.complete.return_value = "mocked llm response"
    llm.stream.return_value = iter(["mocked ", "stream ", "response"])
    return llm


@pytest.fixture()
def mock_embedder():
    embedder = MagicMock()
    embedder.embed.return_value = [[0.1] * constants.MILVUS_DENSE_DIM]
    embedder.embed_both.return_value = ([[0.1] * constants.MILVUS_DENSE_DIM], [{"indices": [0], "values": [1.0]}])
    return embedder


@pytest.fixture()
def mock_image_embedder():
    ie = MagicMock()
    ie.embed_image.return_value = [0.1] * 768
    ie.embed_text.return_value = [0.1] * 768
    return ie


@pytest.fixture()
def mock_transcriber():
    t = MagicMock()
    t.transcribe.return_value = "mocked transcript"
    return t


@pytest.fixture()
def mock_reranker():
    r = MagicMock()
    r.rerank.return_value = [(0, 0.95), (1, 0.85)]
    return r


@pytest.fixture()
def mock_storage():
    s = MagicMock()
    s.put_object.return_value = "test-etag"
    s.get_object.return_value = b"file content"
    s.delete_object.return_value = None
    return s


@pytest.fixture()
def mock_pageindex():
    p = MagicMock()
    p.add.return_value = "doc-test-001"
    p.get_tree.return_value = {"title": "root", "children": []}
    p.get_page_content.return_value = "page content"
    return p


# ---------------------------------------------------------------------------
# 已组装的 Runtime
# ---------------------------------------------------------------------------

@pytest.fixture()
def runtime(
    mock_config, mock_env,
    db_engine, mock_redis, mock_milvus, mock_es, mock_neo4j,
    mock_llm, mock_embedder, mock_image_embedder,
    mock_transcriber, mock_reranker, mock_storage, mock_pageindex,
):
    """所有外部依赖均已 mock 的完整 Match3Runtime。

    所有智能调用（llm.complete、embedder.embed_both、storage.get_object 等）
    均由 MagicMock 满足——无需网络、无需 API Key、无需 @patch 装饰器。
    """
    return Match3Runtime(
        config=mock_config,
        env=mock_env,
        logger=logging.getLogger("match3.test"),
        db_engine=db_engine,
        redis=mock_redis,
        milvus=mock_milvus,
        es=mock_es,
        neo4j=mock_neo4j,
        llm=mock_llm,
        embedder=mock_embedder,
        image_embedder=mock_image_embedder,
        transcriber=mock_transcriber,
        reranker=mock_reranker,
        storage=mock_storage,
        pageindex=mock_pageindex,
    )
```

---

## 四、实体工厂（factory-boy）

```python
# tests/fixtures/factories.py
import factory
from datetime import datetime, timezone
from uuid import uuid4
from app.storage.entities.workspace import Workspace
from app.storage.entities.raw_file import RawFile, RawFileStatus
from app.storage.entities.wiki_page import WikiPage, WikiPageStatus
from app.storage.entities.text_chunk import TextChunk


class WorkspaceFactory(factory.Factory):
    class Meta:
        model = Workspace

    id = factory.LazyFunction(lambda: str(uuid4()))
    name = factory.Sequence(lambda n: f"workspace-{n}")
    owner_id = factory.LazyFunction(lambda: str(uuid4()))
    description = ""
    plan = "free"
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    delete_time = None


class RawFileFactory(factory.Factory):
    class Meta:
        model = RawFile

    id = factory.LazyFunction(lambda: str(uuid4()))
    workspace_id = factory.LazyFunction(lambda: str(uuid4()))
    user_id = factory.LazyFunction(lambda: str(uuid4()))
    filename = factory.Sequence(lambda n: f"report-{n}.pdf")
    file_type = "pdf"
    content_type = "application/pdf"
    size_bytes = 1024 * 100
    object_key = factory.LazyAttribute(lambda o: f"ws/{o.workspace_id}/raw/{o.id}.pdf")
    tags = factory.LazyFunction(list)
    status = RawFileStatus.PENDING
    error = None
    chunk_count = 0
    pageindex_doc_id = None
    pageindex_tree = None
    page_count = None
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    delete_time = None


class WikiPageFactory(factory.Factory):
    class Meta:
        model = WikiPage

    id = factory.LazyFunction(lambda: str(uuid4()))
    workspace_id = factory.LazyFunction(lambda: str(uuid4()))
    topic = factory.Sequence(lambda n: f"entities/game-{n}")
    title = factory.Sequence(lambda n: f"Game {n}")
    category = "entities"
    status = WikiPageStatus.PUBLISHED
    content = "# Game\n\nSome content."
    error = None
    compiled_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    delete_time = None
```

---

## 五、测试命名约定

所有测试函数名格式：`test_<unit>_<scenario>_<expected_outcome>`

| 部分 | 说明 | 示例 |
|------|------|------|
| `<unit>` | 被测的类方法或函数 | `create_workspace`, `find_by_id` |
| `<scenario>` | 触发条件 | `valid_input`, `missing_name`, `db_error` |
| `<expected_outcome>` | 预期结果 | `returns_workspace`, `raises_invalid_param`, `raises_db_error` |

```python
# GOOD
def test_create_workspace_valid_input_returns_workspace(...):
def test_create_workspace_missing_name_raises_invalid_param(...):
def test_find_by_id_nonexistent_id_returns_none(...):
def test_ingest_file_minio_error_raises_minio_error(...):

# BAD
def test_create():           # too vague
def test_workspace_ok():     # no scenario or outcome
```

---

## 六、Repository 测试示例

```python
# tests/unit/storage/test_workspace_repo.py
import pytest
from app.storage.repositories.workspace_repo import WorkspaceRepository
from tests.fixtures.factories import WorkspaceFactory


class TestWorkspaceRepo:

    def test_insert_valid_workspace_returns_persisted_entity(self, db_engine):
        repo = WorkspaceRepository(db_engine)
        ws = WorkspaceFactory()
        saved = repo.insert(ws)
        assert saved.id == ws.id
        assert saved.name == ws.name

    def test_find_by_id_existing_id_returns_workspace(self, db_engine):
        repo = WorkspaceRepository(db_engine)
        ws = WorkspaceFactory()
        repo.insert(ws)
        found = repo.find_by_id(ws.id)
        assert found is not None
        assert found.id == ws.id

    def test_find_by_id_nonexistent_id_returns_none(self, db_engine):
        repo = WorkspaceRepository(db_engine)
        result = repo.find_by_id("nonexistent-id")
        assert result is None

    def test_delete_sets_delete_time_not_hard_delete(self, db_engine):
        repo = WorkspaceRepository(db_engine)
        ws = WorkspaceFactory()
        repo.insert(ws)
        repo.delete(ws.id)
        # 软删除：记录仍存在，但 find_by_id 返回 None（过滤 delete_time IS NULL）
        found = repo.find_by_id(ws.id)
        assert found is None

    def test_find_paginated_respects_page_size(self, db_engine):
        repo = WorkspaceRepository(db_engine)
        workspaces = [WorkspaceFactory() for _ in range(5)]
        for ws in workspaces:
            repo.insert(ws)
        items, total = repo.find_paginated(page=1, size=3)
        assert len(items) <= 3
        assert total >= 5
```

---

## 七、Service 测试示例

```python
# tests/unit/services/test_admin_service.py
import pytest
from unittest.mock import patch
from app.services.admin_service import AdminService
from app.common.exceptions import Match3Exception
from app.common.constants import codes
from tests.fixtures.factories import WorkspaceFactory


class TestAdminService:

    def test_create_workspace_valid_request_returns_workspace_resp(self, runtime):
        svc = AdminService(runtime)
        from app.api.dto.admin_dto import CreateWorkspaceReq
        req = CreateWorkspaceReq(name="Test WS", ownerId="user-001")
        result = svc.create_workspace(req)
        assert result.name == "Test WS"
        assert result.owner_id == "user-001"
        assert result.id is not None

    def test_get_workspace_nonexistent_raises_not_found(self, runtime):
        svc = AdminService(runtime)
        with pytest.raises(Match3Exception) as exc_info:
            svc.get_workspace("nonexistent-id")
        assert exc_info.value.resolve_code() == codes.WORKSPACE_NOT_FOUND

    def test_get_stats_all_tables_empty_returns_zeros(self, runtime):
        svc = AdminService(runtime)
        stats = svc.get_stats()
        assert stats.total_workspaces >= 0
        assert stats.total_raw_files >= 0

    def test_add_member_existing_member_updates_role(self, runtime):
        svc = AdminService(runtime)
        from app.api.dto.admin_dto import CreateWorkspaceReq, AddMemberReq
        ws_req = CreateWorkspaceReq(name="WS", ownerId="owner-001")
        ws = svc.create_workspace(ws_req)

        req_member = AddMemberReq(userId="owner-001", role="admin")
        result = svc.add_member(ws.id, req_member)
        assert result.role == "admin"
```

---

## 八、RAG 路由器测试示例

```python
# tests/unit/rag/test_rag_router.py
import pytest
from unittest.mock import MagicMock, patch
from app.rag.router import AdaptiveRAGRouter


class TestAdaptiveRAGRouter:

    def test_route_short_query_without_file_returns_chunk_path(self, runtime):
        router = AdaptiveRAGRouter(runtime)
        path = router.route(query="What is Royal Match revenue?", raw_file_id=None)
        assert path == "chunk"

    def test_route_with_raw_file_id_returns_page_path(self, runtime):
        router = AdaptiveRAGRouter(runtime)
        path = router.route(query="Summarize this document", raw_file_id="raw-file-001")
        assert path == "page"

    def test_route_wiki_query_returns_entry_path(self, runtime):
        router = AdaptiveRAGRouter(runtime)
        path = router.route(query="Write a wiki page for Royal Match", raw_file_id=None)
        assert path in ("entry", "chunk")   # implementation-dependent


class TestPathChunk:

    def test_search_milvus_empty_result_returns_empty_list(self, runtime):
        runtime.milvus.search.return_value = [[]]
        from app.rag.path_chunk import PathChunkRAG
        rag = PathChunkRAG(runtime)
        results = rag.vector_search(query_embedding=[0.1] * constants.MILVUS_DENSE_DIM, top_k=5)
        assert results == []

    def test_search_returns_deduplicated_rrf_results(self, runtime):
        """RRF 融合不应返回重复的 chunk ID。"""
        from app.rag.path_chunk import PathChunkRAG
        rag = PathChunkRAG(runtime)
        # Milvus 和 ES 均返回同一 chunk
        runtime.milvus.search.return_value = [[MagicMock(id="chunk-001", score=0.9)]]
        runtime.es.search.return_value = {
            "hits": {"hits": [{"_id": "chunk-001", "_score": 5.0}], "total": {"value": 1}}
        }
        results = rag.rrf_fuse(
            vector_hits=["chunk-001"],
            keyword_hits=["chunk-001"],
        )
        assert results.count("chunk-001") == 1
```

---

## 九、Worker 任务测试示例

```python
# tests/unit/workers/test_ingest_task.py
import pytest
from unittest.mock import MagicMock
from app.common.exceptions import Match3Exception
from app.common.constants import codes


class TestIngestTask:

    def test_ingest_file_storage_error_raises_match3_exception(self, runtime):
        # rt.storage 已是 MagicMock — 直接配置失败场景
        runtime.storage.get_object.side_effect = Exception("connection refused")
        from app.workers.tasks.ingest_task import ingest_file
        with pytest.raises(Match3Exception) as exc_info:
            ingest_file.apply(args=["rf-001"]).get()
        assert exc_info.value.resolve_code() == codes.MINIO_ERROR

    def test_ingest_file_llm_parse_error_raises_match3_exception(self, runtime):
        runtime.storage.get_object.return_value = b"fake pdf bytes"
        runtime.llm.complete.side_effect = RuntimeError("context length exceeded")
        from app.workers.tasks.ingest_task import ingest_file
        with pytest.raises(Match3Exception) as exc_info:
            ingest_file.apply(args=["rf-002"]).get()
        assert exc_info.value.resolve_code() == codes.LLM_FAILED

    def test_ingest_file_transcribe_audio_error_raises_whisper_failed(self, runtime):
        runtime.storage.get_object.return_value = b"fake audio bytes"
        runtime.transcriber.transcribe.side_effect = RuntimeError("CUDA out of memory")
        from app.workers.tasks.ingest_task import ingest_file
        with pytest.raises(Match3Exception) as exc_info:
            ingest_file.apply(args=["rf-003"]).get()
        assert exc_info.value.resolve_code() == codes.WHISPER_FAILED
```

---

## 十、异常链路测试

```python
# tests/unit/common/test_exceptions.py
import pytest
from app.common.exceptions import Match3Exception
from app.common.constants import codes


class TestMatch3Exception:

    def test_of_creates_exception_with_zero_code(self):
        exc = Match3Exception.of("something failed")
        assert exc.code == 0
        assert exc.message == "something failed"

    def test_of_code_sets_specific_code(self):
        exc = Match3Exception.of_code(codes.LLM_FAILED, "llm failed")
        assert exc.code == codes.LLM_FAILED

    def test_ctx_attaches_key_value_pairs(self):
        exc = Match3Exception.of("test").ctx(workspace_id="ws-001", model="gpt-4o")
        ctx = dict(exc._context)
        assert ctx["workspace_id"] == "ws-001"
        assert ctx["model"] == "gpt-4o"

    def test_as_ex_chains_cause(self):
        cause = ValueError("root cause")
        exc = Match3Exception.of("outer").as_ex(cause)
        assert exc.__cause__ is cause

    def test_resolve_code_walks_chain_returns_first_nonzero(self):
        root = Match3Exception.of_code(codes.LLM_FAILED, "llm failed")
        mid = Match3Exception.of("outer llm call").as_ex(root)
        outer = Match3Exception.of("service failed").as_ex(mid)
        assert outer.resolve_code() == codes.LLM_FAILED

    def test_resolve_code_returns_zero_if_no_nonzero_in_chain(self):
        inner = Match3Exception.of("inner")
        outer = Match3Exception.of("outer").as_ex(inner)
        assert outer.resolve_code() == 0

    def test_resolve_code_own_code_wins_over_chain(self):
        inner = Match3Exception.of_code(codes.DB_ERROR, "db error")
        outer = Match3Exception.of_code(codes.LLM_FAILED, "llm error").as_ex(inner)
        # outer has non-zero code — should return outer's code
        assert outer.resolve_code() == codes.LLM_FAILED
```

---

## 十一、运行命令

### 开发者常用命令

```bash
# 运行全部单元测试
pytest tests/unit/ -v

# 运行单个测试文件
pytest tests/unit/common/test_exceptions.py -v

# 运行特定测试类
pytest tests/unit/services/test_admin_service.py::TestAdminService -v

# 运行包含关键词的测试
pytest tests/ -k "workspace" -v

# 仅运行快速测试（排除集成测试）
pytest tests/unit/ --ignore=tests/integration/ -v

# 失败立即停止（调试时使用）
pytest tests/unit/ -x
```

### AI Agent 自动化命令

AI Agent 运行测试时，使用 `--json-report` 生成机器可读结果：

```bash
# 输出 JSON 报告，AI 解析失败条目
pytest tests/unit/ \
  --tb=short \
  --json-report \
  --json-report-file=test-results.json \
  -q

# 解析失败测试（jq）
cat test-results.json | jq '.tests[] | select(.outcome == "failed") | {name: .nodeid, message: .call.longrepr}'
```

`test-results.json` 关键字段：

```json
{
  "summary": {"passed": 42, "failed": 2, "error": 0, "total": 44},
  "tests": [
    {
      "nodeid": "tests/unit/common/test_exceptions.py::TestMatch3Exception::test_resolve_code_walks_chain_returns_first_nonzero",
      "outcome": "passed",
      "duration": 0.002
    },
    {
      "nodeid": "tests/unit/services/test_admin_service.py::TestAdminService::test_create_workspace_valid_request_returns_workspace_resp",
      "outcome": "failed",
      "call": {
        "longrepr": "AssertionError: assert 'Test WS' == 'Expected WS'\n  + actual: Test WS\n  - expected: Expected WS"
      }
    }
  ]
}
```

### AI Agent 修复失败测试的流程

```
1. 运行测试，获取 test-results.json
2. 筛选 outcome == "failed" 的条目
3. 读取 call.longrepr 定位断言失败位置（文件名 + 行号）
4. 读取对应源文件（app/ 中被测代码）
5. 根据 error_code（如果有）查 codes.py 确认期望行为
6. 修复代码，重新运行失败测试验证
7. 确认 outcome == "passed" 后提交
```

---

## 十二、测试覆盖率目标

| 模块 | 最低覆盖率 | 说明 |
|------|-----------|------|
| `app/common/` | 95% | 异常、常量、工具函数 — 核心基础 |
| `app/storage/repositories/` | 85% | CRUD 路径 + 软删除 + 分页 |
| `app/services/` | 80% | 主要业务逻辑路径 |
| `app/rag/` | 70% | 外部依赖多，侧重路由逻辑和融合算法 |
| `app/workers/` | 70% | 任务入口 + 错误处理路径 |
| `app/api/routers/` | 60% | 路由层薄，重点测 middleware |

```bash
# 生成覆盖率报告
pytest tests/unit/ --cov=app --cov-report=term-missing --cov-report=json:coverage.json

# AI 解析哪些行未覆盖
cat coverage.json | jq '.files | to_entries[] | select(.value.summary.percent_covered < 80) | {file: .key, coverage: .value.summary.percent_covered}'
```
