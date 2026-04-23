# 导入流水线

## 概述

导入流水线将任意原始文件（PDF、图片、视频、音频、HTML、CSV、Markdown）转换为可搜索、向量化、图索引的知识。整个流程通过 Celery 异步执行。

---

## 文件类型 → 处理路径

| 文件类型 | 扩展名 | 处理路径 | 说明 |
|-----------|-----------|--------------|---------|
| 长 PDF（≥20 页） | .pdf | markitdown → 语义分块 **＋** PageIndex 建树 | 两条路径同时执行：正常分块写入 Milvus/ES/Neo4j，同时向 PageIndex 提交建树供 doc-navigate 检索路径使用 |
| 短 PDF（<20 页） | .pdf | markitdown → 语义分块 | — |
| DOCX / PPTX | .docx .pptx | markitdown → 语义分块 | — |
| HTML / 网页剪藏 | .html .htm | markitdown → 语义分块 | — |
| Markdown | .md | 直接解析 → 语义分块 | — |
| CSV / TSV | .csv .tsv | 表格解析 → 行级块 | — |
| 图片 | .jpg .jpeg .png .webp .gif | CLIP 嵌入 + GPT-4V 描述 | — |
| 视频 | .mp4 .mov .avi .mkv | ffmpeg → 关键帧 + Whisper ASR | — |
| 音频 | .mp3 .wav .m4a .ogg | Whisper ASR → 文本块 | — |
| JSON | .json | 结构感知解析 → 块 | 直接文本块 |

---

## 阶段一：上传（API 层）

```python
# app/api/ingest/handler.py
from app.common.constants import constants, codes

async def upload_file(
    file: UploadFile,
    workspace_id: str,
    tags: list[str],
    current_user: User,
    rt: Match3Runtime,
) -> ApiResp[UploadResponse]:
    """处理文件上传：保存至 MinIO，创建 RawFile 记录，入队任务。"""

    # 校验文件大小
    if file.size and file.size > 500 * 1024 * 1024:  # 500 MB 限制
        raise Match3Exception.of_code(
            codes.FILE_TOO_LARGE,
            "invalid file size exceeds 500MB"
        ).ctx(filename=file.filename, size_mb=file.size // (1024 * 1024))

    # 校验文件类型
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise Match3Exception.of_code(
            codes.UNSUPPORTED_FILE_TYPE,
            "invalid file extension not supported"
        ).ctx(filename=file.filename, ext=ext)

    # 上传至 MinIO
    object_key = f"{workspace_id}/{uuid4()}{ext}"
    file_bytes = await file.read()
    try:
        rt.storage.put_object(object_key, io.BytesIO(file_bytes), len(file_bytes))
    except Exception as e:
        raise Match3Exception.of("failed to put_object").ctx(object_key=object_key).as_ex(e)

    # 创建 RawFile 记录
    raw_file = RawFile(
        id=str(uuid4()),
        workspace_id=workspace_id,
        filename=file.filename,
        object_key=object_key,
        file_type=ext.lstrip("."),
        size_bytes=len(file_bytes),
        tags=tags,
        status=RawFileStatus.PENDING,
        created_by=current_user.id,
    )
    raw_file_repo = RawFileRepository(rt.db_engine)
    inserted = raw_file_repo.insert(raw_file)

    # 入队异步任务
    task = ingest_task.apply_async(
        args=[inserted.id],
        queue=constants.QUEUE_INGEST,
    )

    return ApiResp.ok(UploadResponse(raw_file_id=inserted.id, task_id=task.id))
```

---

## 阶段二：导入任务（Celery Worker）

```python
# app/workers/ingest_task.py
from celery import Task
from pathlib import Path
from app.common.constants import constants, codes

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue=constants.QUEUE_INGEST,
    name="match3.ingest",
)
def ingest_task(self: Task, raw_file_id: str) -> None:
    """从 MinIO 下载文件，解析，分块，入队 embed + graph 任务。

    对于 ≥20 页的 PDF，_parse_pdf 会在分块的同时额外向 PageIndex 提交建树（additive，不替代分块）。
    """
    rt = get_worker_runtime()
    raw_file_repo = RawFileRepository(rt.db_engine)

    raw_file = raw_file_repo.find_by_id(raw_file_id)
    if raw_file is None:
        rt.logger.error(f"raw_file not found: raw_file_id={raw_file_id}")
        return

    # 标记为处理中
    raw_file_repo.update_status(raw_file_id, RawFileStatus.PROCESSING)

    # 从 MinIO 下载
    try:
        obj = rt.storage.get_object(raw_file.object_key)
    except Exception as e:
        self.retry(exc=Match3Exception.of("failed to get_object").ctx(
            object_key=raw_file.object_key
        ).as_ex(e))
        return

    file_bytes = obj.read()
    ext = Path(raw_file.filename).suffix.lower()

    # 分发至对应解析器
    try:
        chunks = _parse_file(rt, raw_file, file_bytes, ext)
    except Match3Exception as e:
        raw_file_repo.update_status(raw_file_id, RawFileStatus.FAILED, error=str(e))
        raise

    # 保存 chunk 至 PostgreSQL
    chunk_repo = ChunkRepository(rt.db_engine)
    chunk_ids = []
    for chunk in chunks:
        inserted_chunk = chunk_repo.insert(chunk)
        chunk_ids.append(inserted_chunk.id)

    # 始终入队嵌入任务（文本块 → Milvus + Elasticsearch）
    embed_task.apply_async(args=[chunk_ids], queue=constants.QUEUE_EMBED)

    # 始终入队图谱抽取任务（实体关系 → Neo4j）
    graph_task.apply_async(args=[raw_file_id], queue=constants.QUEUE_GRAPH)

    # 标记为已完成
    raw_file_repo.update_status(raw_file_id, RawFileStatus.DONE)


def _parse_file(
    rt: Match3Runtime,
    raw_file: RawFile,
    file_bytes: bytes,
    ext: str,
) -> list[Chunk]:
    """将文件路由至对应解析器。返回 Chunk 对象列表。"""

    if ext == ".pdf":
        return _parse_pdf(rt, raw_file, file_bytes)
    elif ext in {".docx", ".pptx", ".html", ".htm"}:
        return _parse_markitdown(rt, raw_file, file_bytes, ext)
    elif ext == ".md":
        return _parse_markdown(rt, raw_file, file_bytes)
    elif ext in {".csv", ".tsv"}:
        return _parse_tabular(rt, raw_file, file_bytes, ext)
    elif ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return _parse_image(rt, raw_file, file_bytes)
    elif ext in {".mp4", ".mov", ".avi", ".mkv"}:
        return _parse_video(rt, raw_file, file_bytes)
    elif ext in {".mp3", ".wav", ".m4a", ".ogg"}:
        return _parse_audio(rt, raw_file, file_bytes)
    elif ext == ".json":
        return _parse_json(rt, raw_file, file_bytes)
    else:
        raise Match3Exception.of_code(
            codes.UNSUPPORTED_FILE_TYPE,
            "invalid file extension not supported in parser"
        ).ctx(ext=ext, raw_file_id=raw_file.id)
```

---

## 阶段三：PDF 解析

```python
def _parse_pdf(rt: Match3Runtime, raw_file: RawFile, file_bytes: bytes) -> list[Chunk]:
    """解析 PDF：所有 PDF 均走 markitdown 分块；≥20 页的 PDF 额外提交 PageIndex 建树。"""

    # 写入临时文件（markitdown 和 PageIndex 均需要文件路径）
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        # 统计页数
        import pypdf
        reader = pypdf.PdfReader(tmp_path)
        page_count = len(reader.pages)
        raw_file.page_count = page_count

        # 所有 PDF 均走 markitdown 正常分块，写入 Milvus / ES / Neo4j
        chunks = _parse_pdf_markitdown(rt, raw_file, tmp_path)

        # ≥20 页的 PDF 额外提交 PageIndex 建树，存储 doc_id 供 doc-navigate 检索路径使用
        if page_count >= 20:
            _register_pageindex(rt, raw_file, tmp_path, page_count)

        return chunks
    finally:
        os.unlink(tmp_path)


def _register_pageindex(
    rt: Match3Runtime,
    raw_file: RawFile,
    pdf_path: str,
    page_count: int,
) -> None:
    """将 PDF 上传至 PageIndex，将 doc_id 和目录树写入 raw_file 元数据。

    此调用独立于分块流水线之外，不影响分块结果。
    """
    client = rt.pageindex

    try:
        doc_id = client.add(pdf_path)
    except Exception as e:
        raise Match3Exception.of("failed to pageindex_client.add").ctx(
            raw_file_id=raw_file.id,
            page_count=page_count,
        ).as_ex(e)

    try:
        tree = client.get_tree(doc_id)
    except Exception as e:
        raise Match3Exception.of("failed to pageindex_client.get_tree").ctx(
            doc_id=doc_id,
        ).as_ex(e)

    # 将 doc_id 和目录树写入 raw_file 元数据（RawFileRepository 在 ingest_task 中负责持久化）
    raw_file.pageindex_doc_id = doc_id
    raw_file.pageindex_tree = tree


def _parse_pdf_markitdown(
    rt: Match3Runtime,
    raw_file: RawFile,
    pdf_path: str,
) -> list[Chunk]:
    """用 markitdown 解析短 PDF，再进行语义分块。"""
    from markitdown import MarkItDown

    md = MarkItDown()
    try:
        result = md.convert(pdf_path)
    except Exception as e:
        raise Match3Exception.of("failed to markitdown.convert").ctx(
            raw_file_id=raw_file.id,
        ).as_ex(e)

    return _semantic_chunk(raw_file, result.text_content)
```

---

## 阶段四：语义分块

语义分块在自然语义边界处切割文本（基于嵌入相似度下降），而非固定字符数。

```python
# app/rag/chunker.py

from sentence_transformers import SentenceTransformer

_sent_model = SentenceTransformer("all-MiniLM-L6-v2")  # 快速，仅用于分块

def semantic_chunk(
    raw_file: RawFile,
    text: str,
    max_chunk_size: int = 512,      # tokens
    similarity_threshold: float = 0.5,
    overlap_sentences: int = 1,
) -> list[Chunk]:
    """基于嵌入相似度下降将文本切割为语义 chunk。

    算法：
    1. 将文本切分为句子（spacy 或正则）
    2. 用快速本地模型对每个句子做嵌入
    3. 计算相邻句子间的余弦相似度
    4. 相似度低于阈值时开启新 chunk
    5. 合并小 chunk 直到达到 max_chunk_size
    6. 在每个新 chunk 开头添加前一 chunk 的 overlap_sentences 句
    """
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if not sentences:
        return []

    # 对所有句子做嵌入
    embeddings = _sent_model.encode(sentences, show_progress_bar=False)

    # 计算相邻句子间的相似度
    from numpy import dot
    from numpy.linalg import norm

    def cosine(a, b):
        return dot(a, b) / (norm(a) * norm(b) + 1e-10)

    # 将句子分组为 chunk
    chunks_text = []
    current_group = [sentences[0]]

    for i in range(1, len(sentences)):
        sim = cosine(embeddings[i - 1], embeddings[i])
        if sim < similarity_threshold or _approx_tokens(current_group) >= max_chunk_size:
            chunks_text.append(" ".join(current_group))
            # 添加 overlap
            current_group = sentences[max(0, i - overlap_sentences):i] + [sentences[i]]
        else:
            current_group.append(sentences[i])

    if current_group:
        chunks_text.append(" ".join(current_group))

    return [
        Chunk(
            id=str(uuid4()),
            raw_file_id=raw_file.id,
            workspace_id=raw_file.workspace_id,
            chunk_type=ChunkType.TEXT,
            content=ct,
            metadata={"chunk_index": idx},
        )
        for idx, ct in enumerate(chunks_text)
        if ct.strip()
    ]


def _approx_tokens(sentences: list[str]) -> int:
    """粗略 token 数：1 token ≈ 4 字符。"""
    return sum(len(s) for s in sentences) // 4
```

---

## 阶段五：嵌入任务

```python
# app/workers/embed_task.py
from app.common.constants import constants

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    queue=constants.QUEUE_EMBED,
    name="match3.embed",
)
def embed_task(self: Task, chunk_ids: list[str]) -> None:
    """对 chunk 进行嵌入并插入 Milvus + Elasticsearch。"""
    rt = get_worker_runtime()
    chunk_repo = ChunkRepository(rt.db_engine)

    chunks = chunk_repo.find_by_ids(chunk_ids)
    if not chunks:
        return

    text_chunks = [c for c in chunks if c.chunk_type in (ChunkType.TEXT, ChunkType.TABLE)]
    image_chunks = [c for c in chunks if c.chunk_type == ChunkType.IMAGE]

    if text_chunks:
        _embed_text_chunks(rt, text_chunks)
    if image_chunks:
        _embed_image_chunks(rt, image_chunks)


def _embed_text_chunks(rt: Match3Runtime, chunks: list[Chunk]) -> None:
    """批量嵌入文本 chunk → Milvus + Elasticsearch。"""
    texts = [c.content for c in chunks]

    # 批量嵌入（每次最多 2048 条，通过 rt.embedder）
    BATCH_SIZE = 256
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        try:
            dense_vecs, _ = rt.embedder.embed_both(batch)
        except Exception as e:
            raise Match3Exception.of("failed to embedder.embed_both").ctx(
                batch_size=len(batch),
            ).as_ex(e)
        all_embeddings.extend(dense_vecs)

    # 插入 Milvus
    milvus_data = [
        {
            "chunk_id": c.id,
            "raw_file_id": c.raw_file_id,
            "workspace_id": c.workspace_id,
            "content": c.content,
            "embedding": emb,
            "chunk_type": c.chunk_type.value,
            "metadata_json": json.dumps(c.metadata or {}),
        }
        for c, emb in zip(chunks, all_embeddings)
    ]
    try:
        rt.milvus.insert(collection_name=constants.MILVUS_COLLECTION, data=milvus_data)
    except Exception as e:
        raise Match3Exception.of("failed to milvus.insert text_chunks").ctx(
            count=len(milvus_data),
        ).as_ex(e)

    # 在 Elasticsearch 中建立索引
    es_ops = []
    for c in chunks:
        es_ops.append({"index": {"_index": constants.ES_INDEX_CHUNKS, "_id": c.id}})
        es_ops.append({
            "content": c.content,
            "workspace_id": c.workspace_id,
            "raw_file_id": c.raw_file_id,
            "chunk_type": c.chunk_type.value,
            "tags": c.tags or [],
        })
    try:
        rt.es.bulk(operations=es_ops)
    except Exception as e:
        raise Match3Exception.of("failed to es.bulk index text_chunks").ctx(
            count=len(chunks),
        ).as_ex(e)
```

---

## 阶段六：图谱提取任务

```python
# app/workers/graph_task.py
from app.common.constants import constants

ENTITY_EXTRACTION_PROMPT = """Extract all named entities from the following text.
Return JSON with this structure:
{
  "entities": [
    {"name": "Royal Match", "type": "Game", "properties": {"developer": "Dream Games", "genre": "match3"}},
    {"name": "Dream Games", "type": "Company", "properties": {"country": "Turkey"}}
  ],
  "relationships": [
    {"from": "Royal Match", "to": "Dream Games", "type": "MADE_BY"}
  ]
}

Entity types: Game, Company, Developer, Mechanic, Market, UACreative, Hook, Revenue
Relationship types: MADE_BY, HAS_MECHANIC, COMPETING_WITH, INSPIRED_BY, USES_HOOK, TARGETS_MARKET, EARNS_REVENUE, MENTIONED_IN

Text:
{text}
"""

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    queue=constants.QUEUE_GRAPH,
    name="match3.graph",
)
def graph_task(self: Task, raw_file_id: str) -> None:
    """从原始文件中提取实体并插入 Neo4j。"""
    rt = get_worker_runtime()
    chunk_repo = ChunkRepository(rt.db_engine)

    chunks = chunk_repo.find_by_raw_file_id(raw_file_id)
    full_text = " ".join(c.content for c in chunks if c.chunk_type == ChunkType.TEXT)

    if not full_text.strip():
        return

    # 用 LLM 提取实体
    try:
        content = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": ENTITY_EXTRACTION_PROMPT.format(text=full_text[:8000]),
            }],
            model=rt.config.llm.default_model,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise Match3Exception.of("failed to llm.complete for graph extraction").ctx(
            raw_file_id=raw_file_id,
            text_len=len(full_text),
        ).as_ex(e)

    import json
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise Match3Exception.of("failed to parse graph extraction JSON").ctx(
            raw_file_id=raw_file_id,
        ).as_ex(e)

    # 插入 Neo4j
    _insert_graph(rt, data, raw_file_id)


def _insert_graph(rt: Match3Runtime, data: dict, raw_file_id: str) -> None:
    """将提取的实体和关系插入 Neo4j。"""
    with rt.neo4j.session() as session:
        for entity in data.get("entities", []):
            try:
                session.run(
                    f"MERGE (n:{entity['type']} {{name: $name}}) SET n += $props",
                    name=entity["name"],
                    props=entity.get("properties", {}),
                )
            except Exception as e:
                raise Match3Exception.of("failed to neo4j entity merge").ctx(
                    entity_name=entity["name"],
                    entity_type=entity["type"],
                ).as_ex(e)

        for rel in data.get("relationships", []):
            try:
                session.run(
                    f"""
                    MATCH (a {{name: $from_name}})
                    MATCH (b {{name: $to_name}})
                    MERGE (a)-[r:{rel['type']}]->(b)
                    SET r.raw_file_id = $raw_file_id
                    """,
                    from_name=rel["from"],
                    to_name=rel["to"],
                    raw_file_id=raw_file_id,
                )
            except Exception as e:
                raise Match3Exception.of("failed to neo4j relationship merge").ctx(
                    from_name=rel["from"],
                    to_name=rel["to"],
                    rel_type=rel["type"],
                ).as_ex(e)
```
