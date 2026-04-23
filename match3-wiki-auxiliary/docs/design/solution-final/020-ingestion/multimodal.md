# 多模态处理

## 概述

系统支持五种纯文本以外的模态：图片、视频、音频、内嵌图片的 PDF，以及包含截图的 HTML。每种模态遵循双路径模式：
1. **嵌入路径**：提取向量表示，用于语义搜索
2. **描述路径**：通过 LLM 生成文本描述，用于 BM25 + RAG 上下文

---

## 图片处理

### 流水线

```
image file
    │
    ├─ CLIP ViT-L/14 encode ──────────────────► image_chunks (Milvus, dim=768)
    │
    └─ GPT-4V / Claude Vision describe ──────► text description
            │
            ├─ text-embedding-3-small embed ──► text_chunks (Milvus, dim=1536)
            └─ Elasticsearch index ───────────► text_chunks (BM25)
```

### 实现

```python
# app/workers/ingest_task.py  (inside _parse_image)

import io
import base64
from PIL import Image as PILImage
from app.common.constants import constants

def _parse_image(rt: Match3Runtime, raw_file: RawFile, file_bytes: bytes) -> list[Chunk]:
    """处理图片：CLIP 嵌入 + Vision 模型描述 → 生成两类 Chunk。"""

    # 若图片过大（超过 2048px），则缩放（兼容 CLIP 和 Vision 模型）
    img = PILImage.open(io.BytesIO(file_bytes))
    img = _resize_image(img, max_size=2048)

    # 将缩放后的图片转回字节供后续使用
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    # CLIP 嵌入
    clip_embedding = _embed_image_clip(img)

    # Vision 模型描述
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    description = _describe_image_vision(rt, b64, raw_file.filename)

    # 将缩放后的图片保存到 MinIO 以供展示
    resized_key = f"{raw_file.workspace_id}/resized/{raw_file.id}.png"
    try:
        rt.storage.put_object(
            resized_key,
            io.BytesIO(img_bytes), len(img_bytes)
        )
    except Exception as e:
        raise Match3Exception.of("failed to put_object resized image").ctx(
            raw_file_id=raw_file.id,
        ).as_ex(e)

    return [
        Chunk(
            id=str(uuid4()),
            raw_file_id=raw_file.id,
            workspace_id=raw_file.workspace_id,
            chunk_type=ChunkType.IMAGE,
            content=description,              # 图片描述文本，用于 RAG 上下文
            metadata={
                "image_path": resized_key,
                "clip_embedding": clip_embedding,  # 此处暂存，后续写入 Milvus image_chunks 集合
                "original_filename": raw_file.filename,
            },
        )
    ]


def _resize_image(img: PILImage.Image, max_size: int) -> PILImage.Image:
    """若图片最长边超过 max_size，则等比缩放。"""
    w, h = img.size
    if max(w, h) <= max_size:
        return img
    ratio = max_size / max(w, h)
    return img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)


def _embed_image_clip(img: PILImage.Image) -> list[float]:
    """生成 CLIP 图片嵌入（768 维，已归一化）。"""
    import torch
    import clip

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = _get_clip_model(device)

    img_tensor = preprocess(img).unsqueeze(0).to(device)
    with torch.no_grad():
        embedding = model.encode_image(img_tensor)
    embedding = embedding / embedding.norm(dim=-1, keepdim=True)
    return embedding.squeeze().cpu().tolist()


_clip_model_cache: dict = {}

def _get_clip_model(device: str):
    """延迟加载 CLIP 模型（按设备缓存）。"""
    if device not in _clip_model_cache:
        import clip
        _clip_model_cache[device] = clip.load("ViT-L/14", device=device)
    return _clip_model_cache[device]


IMAGE_DESCRIPTION_PROMPT = """Describe this image in detail for a match-3 mobile game knowledge base.

Include:
- What type of image this is (screenshot, advertisement, chart, logo, artwork, etc.)
- All visible text (OCR)
- Key visual elements (UI components, game mechanics shown, characters, metrics)
- If it's an advertisement: hook type, emotional appeal, CTA text
- If it's a chart/graph: the metrics, values, and trends shown
- If it's a game screenshot: game name if visible, game state, mechanics in play

Be specific and factual. Include all numbers and text you can read.
"""

def _describe_image_vision(rt: Match3Runtime, b64_image: str, filename: str) -> str:
    """使用视觉模型（通过 rt.llm）生成图片的文字描述。"""
    try:
        description = rt.llm.complete(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": IMAGE_DESCRIPTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                    },
                ],
            }],
        )
    except Exception as e:
        raise Match3Exception.of("failed to vision describe image").ctx(
            filename=filename,
        ).as_ex(e)

    return description
```

### Milvus：image_chunks 集合创建

```python
# scripts/init_milvus.py

from pymilvus import MilvusClient, DataType

def create_image_chunks_collection(client: MilvusClient):
    schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field("chunk_id", DataType.VARCHAR, max_length=64, is_primary=True)
    schema.add_field("raw_file_id", DataType.VARCHAR, max_length=64)
    schema.add_field("workspace_id", DataType.VARCHAR, max_length=64)
    schema.add_field("image_path", DataType.VARCHAR, max_length=512)
    schema.add_field("gpt4v_description", DataType.VARCHAR, max_length=4096)
    schema.add_field("clip_embedding", DataType.FLOAT_VECTOR, dim=768)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="clip_embedding",
        index_type="IVF_FLAT",
        metric_type="IP",
        params={"nlist": 1024},
    )
    index_params.add_index(
        field_name="workspace_id",
        index_type="Trie",
    )

    client.create_collection(
        collection_name=constants.MILVUS_COLLECTION_IMAGES,
        schema=schema,
        index_params=index_params,
    )
```

---

## 视频处理

### 流水线

```
video file
    │
    ├─ ffmpeg extract audio ──► Whisper ASR ──► transcript text
    │       │                                       │
    │       │                               semantic chunk → embed
    │       │
    └─ ffmpeg extract keyframes (1fps, max 50 frames)
            │
            └─ CLIP + GPT-4V (per keyframe) ──► image chunks
```

### 实现

```python
def _parse_video(rt: Match3Runtime, raw_file: RawFile, file_bytes: bytes) -> list[Chunk]:
    """从视频中提取音频转录文本和关键帧。"""
    import subprocess
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        # 将视频写入临时文件
        video_path = os.path.join(tmpdir, "input.mp4")
        with open(video_path, "wb") as f:
            f.write(file_bytes)

        # 提取音频
        audio_path = os.path.join(tmpdir, "audio.wav")
        try:
            subprocess.run(
                ["ffmpeg", "-i", video_path, "-ar", "16000", "-ac", "1", audio_path, "-y"],
                capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise Match3Exception.of("failed to ffmpeg extract audio").ctx(
                raw_file_id=raw_file.id,
            ).as_ex(e)

        # 转录音频
        transcript = _transcribe_audio(rt, audio_path)

        # 提取关键帧（最多 50 帧）
        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir)
        try:
            subprocess.run(
                ["ffmpeg", "-i", video_path, "-vf", "fps=1", "-frames:v", "50",
                 os.path.join(frames_dir, "frame_%04d.png"), "-y"],
                capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise Match3Exception.of("failed to ffmpeg extract keyframes").ctx(
                raw_file_id=raw_file.id,
            ).as_ex(e)

        chunks = []

        # 处理转录文本
        if transcript.strip():
            text_chunks = _semantic_chunk(raw_file, transcript)
            chunks.extend(text_chunks)

        # 处理关键帧（最多 10 帧以限制 Vision 模型调用次数）
        frame_files = sorted(os.listdir(frames_dir))[:10]
        for fname in frame_files:
            frame_path = os.path.join(frames_dir, fname)
            with open(frame_path, "rb") as f:
                frame_bytes = f.read()
            frame_chunks = _parse_image(rt, raw_file, frame_bytes)
            chunks.extend(frame_chunks)

        return chunks
```

---

## 音频处理

```python
def _parse_audio(rt: Match3Runtime, raw_file: RawFile, file_bytes: bytes) -> list[Chunk]:
    """使用 Whisper 转录音频文件，然后进行语义分块。"""
    import tempfile
    import os

    ext = Path(raw_file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        transcript = _transcribe_audio(rt, tmp_path)
    finally:
        os.unlink(tmp_path)

    if not transcript.strip():
        return []

    return _semantic_chunk(raw_file, f"[Audio transcript: {raw_file.filename}]\n\n{transcript}")


def _transcribe_audio(rt: Match3Runtime, audio_path: str) -> str:
    """使用 Whisper 转录音频文件。"""
    import whisper

    model = _get_whisper_model()
    try:
        result = model.transcribe(audio_path, language="en")
    except Exception as e:
        raise Match3Exception.of("failed to whisper.transcribe").ctx(
            audio_path=audio_path,
        ).as_ex(e)

    return result["text"]


_whisper_model_cache = None

def _get_whisper_model():
    global _whisper_model_cache
    if _whisper_model_cache is None:
        import whisper
        _whisper_model_cache = whisper.load_model("large-v3")
    return _whisper_model_cache
```

---

## CSV / 表格处理

```python
def _parse_tabular(
    rt: Match3Runtime,
    raw_file: RawFile,
    file_bytes: bytes,
    ext: str,
) -> list[Chunk]:
    """将 CSV/TSV 解析为行级 Chunk 和摘要 Chunk。"""
    import csv
    import io

    sep = "\t" if ext == ".tsv" else ","
    text = file_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=sep)

    rows = list(reader)
    if not rows:
        return []

    headers = list(rows[0].keys())
    chunks = []

    # 摘要 Chunk：列名 + 前 5 行构成 Markdown 表格
    table_preview = _rows_to_markdown(headers, rows[:5])
    summary_text = (
        f"Table: {raw_file.filename}\n"
        f"Columns: {', '.join(headers)}\n"
        f"Row count: {len(rows)}\n\n"
        f"Preview:\n{table_preview}"
    )
    chunks.append(Chunk(
        id=str(uuid4()),
        raw_file_id=raw_file.id,
        workspace_id=raw_file.workspace_id,
        chunk_type=ChunkType.TABLE,
        content=summary_text,
        metadata={"row_count": len(rows), "columns": headers},
    ))

    # 行级 Chunk（每 20 行一组）
    ROWS_PER_CHUNK = 20
    for i in range(0, len(rows), ROWS_PER_CHUNK):
        batch = rows[i:i + ROWS_PER_CHUNK]
        table_text = _rows_to_markdown(headers, batch)
        chunks.append(Chunk(
            id=str(uuid4()),
            raw_file_id=raw_file.id,
            workspace_id=raw_file.workspace_id,
            chunk_type=ChunkType.TABLE,
            content=table_text,
            metadata={"row_start": i, "row_end": i + len(batch)},
        ))

    return chunks


def _rows_to_markdown(headers: list[str], rows: list[dict]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)
```

---

## 图片搜索：文本 → 图片查询

当用户以文本进行搜索时，使用 CLIP 文本嵌入在 image_chunks 中检索：

```python
# app/rag/chunk/hybrid_search.py
from app.common.constants import constants

def search_images_by_text(
    rt: Match3Runtime,
    query: str,
    workspace_id: str,
    top_k: int = 10,
) -> list[dict]:
    """使用 CLIP 文本嵌入在 image_chunks 集合中进行图片检索。"""
    import clip
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _ = _get_clip_model(device)

    tokens = clip.tokenize([query]).to(device)
    with torch.no_grad():
        text_emb = model.encode_text(tokens)
    text_emb = text_emb / text_emb.norm(dim=-1, keepdim=True)
    text_emb_list = text_emb.squeeze().cpu().tolist()

    try:
        results = rt.milvus.search(
            collection_name=constants.MILVUS_COLLECTION_IMAGES,
            data=[text_emb_list],
            anns_field="clip_embedding",
            search_params={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=top_k,
            filter=f'workspace_id == "{workspace_id}"',
            output_fields=["chunk_id", "image_path", "gpt4v_description"],
        )
    except Exception as e:
        raise Match3Exception.of("failed to milvus.search image_chunks").ctx(
            query=query,
            workspace_id=workspace_id,
        ).as_ex(e)

    return [
        {
            "chunk_id": hit["entity"]["chunk_id"],
            "image_path": hit["entity"]["image_path"],
            "description": hit["entity"]["gpt4v_description"],
            "score": hit["distance"],
        }
        for hit in results[0]
    ]
```
