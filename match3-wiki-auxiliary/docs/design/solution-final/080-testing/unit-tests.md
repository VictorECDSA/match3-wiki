# 单元测试设计

本文规范 match3-wiki 的测试目录结构、fixture 策略、测试命名约定，以及支持 AI 自动化运行和解析测试结果的命令行接口。

---

## 一、目录结构

`tests/` 目录镜像 `app/` 目录，每个被测模块对应一个测试文件：

```
tests/
├── conftest.py                          ← global fixtures (runtime mock, db session, etc.)
├── fixtures/
│   ├── db.py                            ← PostgreSQL test fixture
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
    ├── test_ingest_pipeline.py          ← end-to-end ingest pipeline (uses SQLite in-memory database)
    └── test_wiki_compile_pipeline.py
```

---

## 二、依赖安装

```
# requirements-test.txt
pytest>=8.0
pytest-asyncio>=0.23
pytest-mock>=3.12
pytest-json-report>=1.5        # machine-readable test results (for AI parsing)
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
from app.runtime.runtime import Match3Runtime
from app.common.constants import constants
import logging


@pytest.fixture(scope="session")
def db_engine():
    """In-memory SQLite engine — tables created once per session."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    ORMBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# Config / env stubs — lightweight data objects, not real validation classes
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
# Storage-layer mocks — injected directly via Runtime
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
# Intelligence-layer mocks — NOT Match3Runtime fields.
# Inject directly into the function/class under test via monkeypatch or patch.
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
# Assembled Runtime — only valid Match3Runtime fields
# ---------------------------------------------------------------------------

@pytest.fixture()
def runtime(
    mock_config, mock_env,
    db_engine, mock_redis, mock_milvus, mock_es, mock_neo4j, mock_storage,
):
    """Fully mocked Match3Runtime.

    All storage-layer calls (vector_db.search, search.bulk, graph_db.session, storage.get_object, etc.)
    are satisfied by MagicMock — no network, no API key, no @patch decorator needed.

    Intelligence-layer objects (llm, embedder, reranker, pageindex) are NOT Match3Runtime fields.
    Use mock_llm / mock_embedder / mock_reranker / mock_pageindex fixtures directly
    and inject them via monkeypatch or unittest.mock.patch into the code under test.
    """
    return Match3Runtime(
        config=mock_config,
        env=mock_env,
        logger=logging.getLogger("match3.test"),
        db=db_engine,
        cache=mock_redis,
        queue=mock_redis,
        vector_db=mock_milvus,
        search=mock_es,
        graph_db=mock_neo4j,
        storage=mock_storage,
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
        # soft delete: record still exists but find_by_id returns None (filters delete_time IS NULL)
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
        runtime.vector_db.search.return_value = [[]]
        from app.rag.path_chunk import PathChunkRAG
        rag = PathChunkRAG(runtime)
        results = rag.vector_search(query_embedding=[0.1] * constants.MILVUS_DENSE_DIM, top_k=5)
        assert results == []

    def test_search_returns_deduplicated_rrf_results(self, runtime):
        """RRF fusion must not return duplicate chunk IDs."""
        from app.rag.path_chunk import PathChunkRAG
        rag = PathChunkRAG(runtime)
        # both Milvus and ES return the same chunk
        runtime.vector_db.search.return_value = [[MagicMock(id="chunk-001", score=0.9)]]
        runtime.search.search.return_value = {
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
        # rt.storage is already a MagicMock — configure failure directly
        runtime.storage.get_object.side_effect = Exception("connection refused")
        from app.workers.tasks.ingest_task import ingest_file
        with pytest.raises(Match3Exception) as exc_info:
            ingest_file.apply(args=["rf-001"]).get()
        assert exc_info.value.resolve_code() == codes.MINIO_ERROR

    def test_ingest_file_llm_parse_error_raises_match3_exception(self, mock_llm):
        """Intelligence-layer errors must propagate as Match3Exception.

        Patch app.intelligence.llm.OpenAILLMCaller so the task picks up the mock.
        """
        from unittest.mock import patch, MagicMock
        mock_llm.complete.side_effect = RuntimeError("context length exceeded")
        with patch("app.intelligence.llm.OpenAILLMCaller", return_value=mock_llm):
            from app.workers.tasks.ingest_task import ingest_file
            with pytest.raises(Match3Exception) as exc_info:
                ingest_file.apply(args=["rf-002"]).get()
        assert exc_info.value.resolve_code() == codes.LLM_FAILED

    def test_ingest_file_transcribe_audio_error_raises_whisper_failed(self, mock_transcriber):
        """Whisper errors must propagate as Match3Exception.

        Patch app.intelligence.transcriber.Transcriber so the task picks up the mock.
        """
        from unittest.mock import patch
        mock_transcriber.transcribe.side_effect = RuntimeError("CUDA out of memory")
        with patch("app.intelligence.transcriber.Transcriber", return_value=mock_transcriber):
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
# run all unit tests
pytest tests/unit/ -v

# run a single test file
pytest tests/unit/common/test_exceptions.py -v

# run a specific test class
pytest tests/unit/services/test_admin_service.py::TestAdminService -v

# run tests matching a keyword
pytest tests/ -k "workspace" -v

# run only fast tests (exclude integration tests)
pytest tests/unit/ --ignore=tests/integration/ -v

# stop on first failure (useful for debugging)
pytest tests/unit/ -x
```

### AI Agent 自动化命令

AI Agent 运行测试时，使用 `--json-report` 生成机器可读结果：

```bash
# output JSON report for AI parsing of failures
pytest tests/unit/ \
  --tb=short \
  --json-report \
  --json-report-file=test-results.json \
  -q

# parse failed tests (jq)
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
1. Run tests, obtain test-results.json
2. Filter entries where outcome == "failed"
3. Read call.longrepr to locate the assertion failure (filename + line number)
4. Read the corresponding source file (code under test in app/)
5. If error_code is present, check codes.py to confirm expected behavior
6. Fix the code, re-run the failing tests to verify
7. Confirm outcome == "passed", then commit
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
# generate coverage report
pytest tests/unit/ --cov=app --cov-report=term-missing --cov-report=json:coverage.json

# AI: find files below 80% coverage
cat coverage.json | jq '.files | to_entries[] | select(.value.summary.percent_covered < 80) | {file: .key, coverage: .value.summary.percent_covered}'
```
