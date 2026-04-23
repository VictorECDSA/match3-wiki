> **Nav:** [Overview](overview.md) | [方案 A 全栈定制](solution-a-fullstack.md) | [方案 B Dify ⭐](solution-b-dify.md) | [方案 C RAGFlow](solution-c-ragflow.md) | **方案 D 轻量本地栈 (current)**

---

# 方案 D — 轻量本地栈
## 零成本快速起步方案

**Solution D · Lightweight Local Stack**

LlamaIndex + Chroma + Streamlit + MkDocs — 全部运行在本地，无需云账号，一天内完成部署，作为 Phase 1 最低摩擦切入点

**Tags:** 💰 零云端成本 · ⚡ 1-2 周上线 · 🏠 完全本地化 · 🔍 Hybrid Search · 📚 BGE 本地向量 · 🛠 1 人可完成

---

## Quick Stats

| 指标 | 数值 |
|------|------|
| 月度云端费用 | $0 |
| 完整部署时间 | 1-2 周 |
| 所需开发人力 | 1 人 |
| RAG 技术集成 | 5 种 |
| 数据本地留存 | 100% |

---

## Architecture

### 整体架构：三层轻量结构

所有组件运行在同一台开发机或内网服务器上，通过 Python 进程通信，无需 Docker Compose 编排（可选），最小化运维复杂度。

```text
📝 编辑层 · Content Layer
┌─────────────────────┐   ┌────────────────────┐   ┌─────────────────────┐
│  🗂️ Obsidian Vault  │ + │  📁 Raw Resources  │ → │  🔄 Watcher Script  │
│  match3-wiki/       │   │  PDF / Image / URL  │   │  watchdog 文件监听  │
│  Markdown           │   │                    │   │                     │
└─────────────────────┘   └────────────────────┘   └─────────────────────┘

─────────────────────────────────────────────────────────────────────────

🧠 RAG 引擎层 · LlamaIndex Core
┌──────────────────────┐   ┌──────────────────────┐   ┌───────────────────┐   ┌────────────────────────┐
│  📦 Document Loader  │ → │  ✂️ Semantic Chunker  │ → │  🧮 BGE Embedder  │ → │  🗃️ Hybrid Index       │
│  SimpleDirectory     │   │  SemanticSplitter    │   │  bge-m3 (local)   │   │  Chroma + BM25Retriever│
│  Reader              │   │  NodeParser          │   │                   │   │                        │
└──────────────────────┘   └──────────────────────┘   └───────────────────┘   └────────────────────────┘

─────────────────────────────────────────────────────────────────────────

🖥 前端层 · Interface Layer
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│  💬 Streamlit Chat   │ + │  📖 MkDocs Site       │ + │  📊 Admin Panel      │
│  问答 + 来源展示     │   │  Wiki 浏览 + 搜索     │   │  Streamlit 摄入管理  │
└──────────────────────┘   └──────────────────────┘   └──────────────────────┘
```

---

## RAG Pipeline

### 5 种 RAG 技术集成方案

在轻量级框架内实现最核心的高召回技术，不引入外部 API 依赖，全部本地推理。

#### 🔍 查询阶段 Pipeline

```text
Step 1        Step 2              Step 3                Step 4              Step 5          Step 6
用户查询  →  Multi-Query      →  Hybrid Search      →  P-C Retrieval  →  BGE Reranker →  生成答案
自然语言      本地 LLM            Chroma + BM25 → RRF   小 chunk 匹配        精排 Top 5       本地 Ollama
              生成 3 变体                               →大段返回                             LLM
```

#### 📥 摄入阶段 Pipeline

```text
Step 1        Step 2          Step 3          Step 4          Step 5
文件检测  →  解析提取      →  语义分块      →  向量化        →  双路索引
watchdog      PyMuPDF /         Semantic        bge-m3           Chroma +
监听          Pillow            Splitter        embedding        BM25 json
```

### RAG 技术对照表

| RAG 技术 | 来自 yupi.md | 本方案实现方式 | 召回提升 |
|----------|-------------|--------------|---------|
| **Hybrid Search** | ✓ yupi 核心 | `ChromaRetriever` + `BM25Retriever` → `QueryFusionRetriever(RRF)` | +25-35% |
| **Semantic Chunking** | ✓ yupi 核心 | `SemanticSplitterNodeParser`，threshold=0.85，bge-m3 作为 embed model | +15-20% |
| **Parent-Child Retrieval** | ✓ yupi 核心 | `AutoMergingRetriever` + `HierarchicalNodeParser`（512→128 tokens） | +10-15% |
| **Multi-Query RAG** | ✓ yupi 核心 | Ollama 本地生成 3 个查询变体，`QueryFusionRetriever(mode=reciprocal_rerank)` | +15-20% |
| **Reranking** | ✓ yupi 核心 | `SentenceTransformerRerank`，使用 `BAAI/bge-reranker-v2-m3`，Top N=5 | +20-30% |
| **PageIndex（长文档推理检索）** | repo-deep-dive | `pageindex` pip 包（VectifyAI Apache-2.0）；对 ≥20 页 PDF 构建章节树，LLM 推理导航定位段落，无需向量化 | GDC PDF 精准率 +40% |

---

## Core Implementation

### 核心代码实现

```python
# hybrid_index.py — Hybrid Search + Reranker 核心配置
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SemanticSplitterNodeParser, HierarchicalNodeParser
from llama_index.core.retrievers import AutoMergingRetriever, QueryFusionRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.postprocessor.flag_embedding_reranker import FlagEmbeddingReranker
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb

# -- Embedding: local BGE-M3 (bilingual, 1024 dims) --
embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-m3",
    device="mps",  # use "cuda" on Linux GPU, "cpu" as fallback
    embed_batch_size=32
)

# -- Vector store: persistent Chroma --
chroma_client = chromadb.PersistentClient(path="./data/chroma_db")
chroma_collection = chroma_client.get_or_create_collection("match3_wiki")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

# -- Hierarchical chunker: parent 512t / child 128t --
node_parser = HierarchicalNodeParser(
    chunk_sizes=[512, 128],
    chunk_overlap=20
)

# -- Semantic splitter (overrides above for wiki docs) --
semantic_splitter = SemanticSplitterNodeParser(
    buffer_size=1,
    breakpoint_percentile_threshold=85,
    embed_model=embed_model,
)

def build_hybrid_retriever(index, nodes, top_k=60):
    """Build a Hybrid (vector + BM25) retriever with RRF fusion."""
    vector_retriever = index.as_retriever(similarity_top_k=top_k)
    bm25_retriever = BM25Retriever.from_defaults(
        nodes=nodes, similarity_top_k=top_k
    )
    hybrid = QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        similarity_top_k=top_k,
        num_queries=3,   # Multi-Query: generate 3 variants
        mode="reciprocal_rerank",
        use_async=True,
    )
    return hybrid

# -- BGE Reranker: precision re-scoring --
reranker = FlagEmbeddingReranker(
    model="BAAI/bge-reranker-v2-m3",
    top_n=5,
    use_fp16=True,
)

# -- Query Engine: retriever + reranker --
def build_query_engine(index, nodes, llm):
    retriever = build_hybrid_retriever(index, nodes)
    auto_merge = AutoMergingRetriever(retriever, index.storage_context)
    return index.as_query_engine(
        retriever=auto_merge,
        node_postprocessors=[reranker],
        llm=llm,
        response_mode="compact",
    )
```

```python
# pageindex_retriever.py — 长 PDF 推理导航检索（第 4 条检索路径）
# pageindex: pip install pageindex  (VectifyAI, Apache-2.0)
# Ideal for GDC talk PDFs >= 20 pages: builds chapter tree,
# uses LLM to navigate to the relevant section — no chunking needed.
from pageindex import PageIndex
from llama_index.core.schema import NodeWithScore, TextNode
import fitz  # PyMuPDF — page count check

LONG_PDF_THRESHOLD = 20  # pages; GDC talks typically 30-80 pages

class PageIndexRetriever:
    """Wrapper around pageindex for retrieval inside LlamaIndex pipelines."""

    def __init__(self, pdf_dir: str, llm_model: str = "qwen2.5:14b"):
        self.pdf_dir = pdf_dir
        self.llm_model = llm_model
        self._indexes: dict[str, PageIndex] = {}

    def _get_or_build(self, pdf_path: str) -> PageIndex:
        if pdf_path not in self._indexes:
            idx = PageIndex(pdf_path, llm=self.llm_model)
            idx.build()  # builds chapter tree once, cached to disk
            self._indexes[pdf_path] = idx
        return self._indexes[pdf_path]

    def retrieve(self, query: str, top_k: int = 5) -> list[NodeWithScore]:
        """Query all indexed long PDFs, return matching passages."""
        results = []
        import os
        for fname in os.listdir(self.pdf_dir):
            if not fname.endswith(".pdf"):
                continue
            pdf_path = os.path.join(self.pdf_dir, fname)
            # Only use PageIndex for long PDFs
            if fitz.open(pdf_path).page_count < LONG_PDF_THRESHOLD:
                continue
            idx = self._get_or_build(pdf_path)
            passages = idx.query(query, top_k=top_k)
            for p in passages:
                results.append(NodeWithScore(
                    node=TextNode(
                        text=p.text,
                        metadata={
                            "file_name": fname,
                            "page": p.page_num,
                            "section": p.section_title,
                            "retrieval_method": "pageindex",
                        }
                    ),
                    score=p.score,
                ))
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]


def build_query_engine_with_pageindex(index, nodes, llm, pdf_dir: str):
    """Extended query engine: hybrid retriever + PageIndex for long GDC PDFs."""
    from hybrid_index import build_hybrid_retriever, reranker
    from llama_index.core.retrievers import RouterRetriever
    from llama_index.core.tools import RetrieverTool

    hybrid = build_hybrid_retriever(index, nodes)
    page_idx = PageIndexRetriever(pdf_dir=pdf_dir, llm_model="qwen2.5:14b")

    # Merge results from both paths before reranking
    class MergedRetriever:
        def retrieve(self, query: str):
            hybrid_results = hybrid.retrieve(query)
            pi_results = page_idx.retrieve(query, top_k=10)
            return hybrid_results + pi_results  # reranker will re-score all

    return index.as_query_engine(
        retriever=MergedRetriever(),
        node_postprocessors=[reranker],
        llm=llm,
        response_mode="compact",
    )
```

```python
# app.py — Streamlit 问答界面（含来源展示）
import streamlit as st
from llama_index.llms.ollama import Ollama
from hybrid_index import build_query_engine
from auth import check_credentials   # simple YAML-based auth

st.set_page_config(page_title="Match-3 Knowledge Base", layout="wide")

# -- Authentication --
if "authenticated" not in st.session_state:
    with st.form("login"):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            role = check_credentials(user, pwd)
            if role:
                st.session_state.authenticated = True
                st.session_state.user = user
                st.session_state.role = role
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# -- Load query engine (cached) --
@st.cache_resource
def get_engine():
    llm = Ollama(model="qwen2.5:14b", request_timeout=120)
    index, nodes = load_index()          # loads from ./data/chroma_db
    return build_query_engine(index, nodes, llm)

engine = get_engine()

# -- Chat UI --
st.title("🎮 Match-3 Knowledge Base Q&A")
st.caption(f"Logged in as: {st.session_state.user} ({st.session_state.role})")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if query := st.chat_input("Ask about Match-3 mechanics, market data, competitors..."):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Searching knowledge base..."):
            response = engine.query(query)

        st.markdown(str(response))

        # Show source documents
        with st.expander(f"📚 Sources ({len(response.source_nodes)} chunks)"):
            for i, node in enumerate(response.source_nodes):
                meta = node.node.metadata
                st.markdown(f"**[{i+1}] {meta.get('file_name', 'Unknown')}** (score: {node.score:.3f})")
                st.text(node.node.text[:300] + "...")
                st.divider()

        st.session_state.messages.append({
            "role": "assistant",
            "content": str(response)
        })
```

```python
# watcher.py — 文件监听自动摄入
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ingestion import ingest_file
import logging, time

WATCH_PATHS = [
    "./wiki",           # Obsidian vault markdown files
    "./raw/pdf",        # GDC talks, market reports
    "./raw/images",     # screenshots, charts
]

SUPPORTED_EXTS = {".md", ".pdf", ".png", ".jpg", ".jpeg"}

class KnowledgeBaseHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            self._process(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._process(event.src_path)

    def _process(self, path):
        ext = path[path.rfind('.'):]
        if ext in SUPPORTED_EXTS:
            logging.info(f"Detected change: {path}")
            try:
                ingest_file(path)
                logging.info(f"Ingested: {path}")
            except Exception as e:
                logging.error(f"Failed to ingest {path}: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    observer = Observer()
    for path in WATCH_PATHS:
        observer.schedule(KnowledgeBaseHandler(), path, recursive=True)
    observer.start()
    logging.info("Watching for file changes...")
    try:
        while True: time.sleep(1)
    finally:
        observer.stop()
        observer.join()
```

```python
# auth.py — 基于 YAML 的轻量多用户认证
# users.yaml structure:
# users:
#   alice:
#     password_hash: "bcrypt_hash_here"
#     role: admin        # admin | editor | reader
#   bob:
#     password_hash: "bcrypt_hash_here"
#     role: reader

import yaml, bcrypt
from pathlib import Path

def check_credentials(username: str, password: str) -> str | None:
    """Returns role string if valid, None if invalid."""
    config = yaml.safe_load(Path("users.yaml").read_text())
    user = config["users"].get(username)
    if not user:
        return None
    pw_hash = user["password_hash"].encode()
    if bcrypt.checkpw(password.encode(), pw_hash):
        return user["role"]
    return None

def can_edit(role: str) -> bool:
    return role in {"admin", "editor"}

def can_ingest(role: str) -> bool:
    return role == "admin"
```

---

## Tech Stack

### 完整技术栈清单

| 层级 | 组件 | 版本 / 规格 | 用途 | 成本 |
|------|------|------------|------|------|
| **文档编辑** | Obsidian | 1.7+ | Wiki Markdown 编辑器 | 免费 |
| **RAG 框架** | LlamaIndex | 0.11+ | 文档加载、索引、查询引擎 | 免费 |
| **向量数据库** | ChromaDB | 0.5+, persistent | 向量存储与检索 | 免费 |
| **关键词检索** | BM25Retriever | llama-index-retrievers-bm25 | BM25 关键词召回 | 免费 |
| **Embedding 模型** | BGE-M3 | BAAI/bge-m3 (1024d) | 中英双语向量化 | 本地 |
| **Reranker** | BGE-Reranker-v2-m3 | BAAI/bge-reranker-v2-m3 | 精排 Cross-Encoder | 本地 |
| **LLM 推理** | Ollama | qwen2.5:14b 或 llama3.2:8b | 本地 LLM 生成答案 | 本地 |
| **问答 UI** | Streamlit | 1.38+ | Chat 界面 + 管理面板 | 免费 |
| **Wiki 站点** | MkDocs Material | 9.5+ | 静态 Wiki 浏览站 | 免费 |
| **PDF 解析** | PyMuPDF | 1.24+ | PDF 文本 + 图片提取（短文档） | 免费 |
| **长文档检索** | pageindex | VectifyAI Apache-2.0 | ≥20 页 PDF 的章节树推理导航，零向量切块 | 免费 |
| **图片理解** | LLaVA (via Ollama) | llava:13b | 截图/图表描述生成 | 本地 |
| **文件监听** | watchdog | 4.0+ | 自动检测新文件触发摄入 | 免费 |
| **认证** | YAML + bcrypt | 手动维护 users.yaml | 3 角色轻量权限控制 | 免费 |

> 💻 **最低硬件要求：** 16GB RAM (推荐 32GB) + M1/M2 Mac 或 NVIDIA GPU 8GB VRAM。BGE-M3 + Reranker 同时加载约占用 4-6GB 显存，qwen2.5:14b (Q4_K_M) 约需 8GB VRAM。若资源受限，可换用 `bge-small-zh-v1.5` + `qwen2.5:7b`。

---

## Wiki Site

### MkDocs Wiki 站点配置

将 Obsidian vault 直接作为 MkDocs docs/ 目录，一个命令生成静态 Wiki 站点，支持全文搜索和导航结构。

```yaml
# mkdocs.yml — 站点配置
site_name: Match-3 Knowledge Base
site_description: Internal wiki for Match-3 game industry
docs_dir: wiki   # points to Obsidian vault
site_dir: site

theme:
  name: material
  palette:
    - scheme: slate
      primary: deep purple
  features:
    - navigation.tabs
    - navigation.instant
    - search.highlight
    - content.code.copy

plugins:
  - search
  - tags
  - roamlinks:  # Obsidian [[wikilinks]] support
      enabled: true

nav:
  - Home: index.md
  - Mechanics: mechanics/
  - Games: titles/
  - Market: market/
  - Growth: growth/
  - History: history/

markdown_extensions:
  - admonition
  - pymdownx.highlight
  - pymdownx.superfences
  - tables
  - toc: {permalink: true}
```

```bash
#!/usr/bin/env bash
# serve_wiki.sh — 本地预览
# Serve MkDocs with live reload
mkdocs serve --dev-addr 0.0.0.0:8001 --watch wiki/
```

```bash
#!/usr/bin/env bash
# build_wiki.sh — 构建静态站点
# Build static site to ./site/
mkdocs build --clean --strict

# Optional: serve via nginx or Python
# python -m http.server 8001 --directory site
```

> 📌 **访问地址：**
> - 问答 Chat：`http://localhost:8501`
> - Wiki 站点：`http://localhost:8001`
> - 管理面板：`http://localhost:8501/admin`（Streamlit 多页）

---

## Multimodal Support

### 多模态基础支持

使用本地 LLaVA 模型为图片生成文字描述，将其作为可检索的文本节点加入向量索引。

```python
# ingestion.py — 多模态文件摄入路由
import ollama
from pathlib import Path
from llama_index.core.schema import TextNode
import fitz  # PyMuPDF
import base64, json

def ingest_file(file_path: str) -> list[TextNode]:
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".md":
        return ingest_markdown(path)
    elif ext == ".pdf":
        # Route: long PDFs (>= 20 pages) → PageIndex; short PDFs → PyMuPDF chunks
        doc = fitz.open(file_path)
        page_count = doc.page_count
        doc.close()
        if page_count >= 20:
            # PageIndex handles retrieval at query time — no upfront TextNodes needed
            return []  # registered in PageIndexRetriever's pdf_dir scan
        return ingest_pdf(path)
    elif ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return ingest_image(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def ingest_image(path: Path) -> list[TextNode]:
    """Use LLaVA to generate a text description for image retrieval."""
    with open(path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    prompt = (
        "You are analyzing a Match-3 game screenshot or chart. "
        "Describe: (1) what type of content this is, (2) key UI elements or data shown, "
        "(3) any numbers, labels, or game mechanics visible. Be concise and factual."
    )
    response = ollama.chat(
        model="llava:13b",
        messages=[{
            "role": "user",
            "content": prompt,
            "images": [img_b64]
        }]
    )
    description = response["message"]["content"]

    return [TextNode(
        text=description,
        metadata={
            "file_path": str(path),
            "file_name": path.name,
            "file_type": "image",
            "source": "llava_description",
        }
    )]

def ingest_pdf(path: Path) -> list[TextNode]:
    """Extract text + embedded images from PDF via PyMuPDF."""
    doc = fitz.open(path)
    nodes = []

    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            nodes.append(TextNode(
                text=text,
                metadata={"file_name": path.name, "page": page_num + 1}
            ))
        # Extract embedded images and describe via LLaVA
        for img_info in page.get_images():
            xref = img_info[0]
            img_data = doc.extract_image(xref)
            if img_data["width"] > 200:  # skip tiny icons
                # Save temp, then call ingest_image
                pass  # abbreviated for readability

    return nodes
```

---

## Project Structure

### 项目目录结构

```text
match3-kb/
├── wiki/                   # Obsidian vault (same as MkDocs docs_dir)
│   ├── index.md
│   ├── mechanics/
│   ├── titles/
│   ├── market/
│   ├── growth/
│   └── history/
├── raw/                    # raw resources to ingest
│   ├── pdf/                # GDC talks, reports
│   ├── images/             # screenshots, charts
│   └── urls.txt            # URLs to crawl
├── data/
│   ├── chroma_db/          # ChromaDB persistent storage
│   ├── bm25_index.json     # BM25 serialized index
│   └── pageindex_cache/    # PageIndex chapter-tree cache (auto-created)
├── src/
│   ├── app.py              # Streamlit main chat page
│   ├── pages/
│   │   └── admin.py        # Streamlit admin panel
│   ├── hybrid_index.py     # RAG core (vector + BM25)
│   ├── pageindex_retriever.py  # PageIndex path for long GDC PDFs
│   ├── ingestion.py        # Document loading & parsing
│   ├── watcher.py          # File change watcher
│   └── auth.py             # User authentication
├── mkdocs.yml
├── users.yaml              # User credentials (gitignore this!)
├── requirements.txt
└── Makefile
```

```makefile
install:
	pip install -r requirements.txt
	ollama pull qwen2.5:14b
	ollama pull llava:13b

ingest:
	python src/ingestion.py --path ./raw

watch:
	python src/watcher.py

chat:
	streamlit run src/app.py --server.port 8501

wiki:
	mkdocs serve --dev-addr 0.0.0.0:8001

# Run chat + wiki + watcher in parallel
start:
	make -j3 watch chat wiki
```

---

## Implementation Plan

### 1-2 周实施计划

**Day 1-2 — 环境搭建 + 基础索引**

安装 Python 依赖，拉取 Ollama 模型（bge-m3 + reranker + qwen2.5:14b），初始化 ChromaDB，将现有 wiki/ 目录完成首次摄入并验证向量检索结果。

- `pip install requirements`
- `ollama pull models`
- ChromaDB 初始化
- 首次批量摄入
- 基础检索验证

**Day 3-4 — Hybrid Search + Reranker 集成**

配置 BM25Retriever + ChromaRetriever → QueryFusionRetriever(RRF)，集成 BGE-Reranker，实现 AutoMergingRetriever 父子节点回溯，跑 RAGAS 基础评测（5-10 个测试 Q&A 对）。

- BM25 集成
- RRF 融合
- Reranker 配置
- AutoMerging
- RAGAS 初评

**Day 5-7 — Streamlit Chat UI + 认证**

完成问答界面（含来源展示、对话历史），实现 YAML 用户认证（3 角色），搭建管理面板（摄入状态、手动触发、索引统计）。

- Chat UI
- 来源展示
- YAML Auth
- Admin Panel
- 对话历史

**Day 8-9 — MkDocs Wiki + 文件监听**

配置 MkDocs Material 主题，启用 roamlinks 插件兼容 Obsidian 内部链接，部署 watcher.py 自动监听 wiki/ 和 raw/ 目录变化触发重新索引。

- MkDocs 配置
- roamlinks
- watcher 部署
- 自动摄入测试

**Day 10-12 — 多模态 + PDF 摄入 + PageIndex**

接入 LLaVA 本地视觉模型处理截图/图表，配置 PyMuPDF PDF 解析（短文档），为 ≥20 页的 GDC PDF 集成 `pageindex` 推理导航检索（第 4 条检索路径），批量摄入所有资料并验证长文档检索精准率提升。

- LLaVA 集成
- PyMuPDF 解析
- pageindex 集成
- 批量 PDF 摄入
- 图片描述检索

**Day 13-14 — 质量评测 + 文档收尾**

使用 RAGAS 对 20+ 测试问题进行评测（faithfulness、answer relevance、context recall），根据结果调整 Top K / reranker 阈值，完成内部使用文档。

- RAGAS 评测
- 参数调优
- 使用文档
- 团队培训

---

## Evaluation

### 优势与局限

#### ✅ 核心优势

- 零云端成本：所有模型本地运行，无 API 费用
- 数据完全私有：知识库内容不离开本地网络
- 启动速度最快：1-2 天内可完成首次部署
- 技术栈简单：纯 Python，无微服务，易于调试
- Hybrid Search 效果好：vector + BM25 RRF 融合
- BGE 系列双语支持：中英文混合内容表现优秀
- 可离线运行：断网环境下完全可用
- 易于迁移：LlamaIndex 代码可直接复用到方案 B/C

#### ⚠️ 已知局限

- 本地 LLM 质量低于 GPT-4：答案精度有明显差距
- 多用户体验差：Streamlit 单进程，并发支持有限
- PDF 解析能力弱：复杂表格/图表布局识别不如 DeepDoc
- 无 GraphRAG：实体关系图谱需要额外集成 Neo4j
- 无 Agentic RAG：无法自动搜索和摄入外部资源
- 认证系统简陋：YAML + bcrypt 不适合大团队
- 硬件要求较高：M1 16GB 最低配，量化模型有精度损失
- 扩展性受限：单机部署，文档量超过 10万 chunks 后性能下降

> ⚠️ **适用场景：** 个人或小团队（≤5人）的 Phase 1 快速验证；知识库总文档量 < 500 个文件；对答案质量要求适中；需要完全离线/私有部署的场景。如果团队超过 5 人或需要更高质量的问答，建议在 2-4 周后迁移到 **方案 B (Dify)**。

---

## Migration Path

### 迁移至方案 B (Dify) 的路径

方案 D 的数据结构与方案 B 兼容——wiki/ 目录结构不变，只需将向量数据库和 UI 层替换即可，迁移成本低。

**1. 保留 Obsidian Wiki 目录结构**

wiki/ 目录 Markdown 文件无需任何修改，frontmatter schema 与 Dify 知识库 metadata 完全兼容 ✓

**2. 部署 Dify + bge-m3 embedding 服务**

运行 `docker-compose up` 启动 Dify，配置与方案 D 相同的 bge-m3 作为 embedding 模型，向量空间保持一致 →

**3. 批量导入至 Dify Knowledge Base**

通过 Dify API 批量上传 wiki/ 文档，选择 Hybrid 检索模式，配置 BGE-reranker，无需重新标注或修改内容 →

**4. 迁移 raw/ 资源并重新摄入**

将 raw/pdf/ 和 raw/images/ 的文件通过 Dify 多模态摄入工作流重新处理，获得更好的 DeepDoc 解析质量 →

**5. 替换 Streamlit UI → Dify 应用**

在 Dify 中配置 Adaptive RAG Workflow，替代 Streamlit Chat UI；原有用户迁移到 Dify 工作空间成员管理 →

**6. 保留 MkDocs Wiki 站点（可选）**

MkDocs 静态 Wiki 浏览站可继续运行，与 Dify 问答系统并行提供服务，两者共享同一个 wiki/ 目录 ✓

> 🎯 **推荐演进路线：** **方案 D**（第 1-2 周，快速搭建基础版） → **方案 B Dify**（第 3-6 周，升级为生产级别，接入 GPT-4o 和 Adaptive RAG） → 视情况考虑 **方案 A**（团队扩大至 10+ 人后的完整定制平台）

---

## Comparison

### 四方案对比速览

| 维度 | 方案 A 全栈 | 方案 B Dify ⭐ | 方案 C RAGFlow | 方案 D 本地栈 |
|------|-----------|--------------|--------------|-------------|
| **启动时间** | 16 周 | 3-4 周 | 4-6 周 | **1-2 周** |
| **月费用** | $90-205 | $46-101 | $75-150 | **$0** |
| **答案质量** | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★☆☆ |
| **PDF 解析** | Unstructured | Dify DeepDoc | **DeepDoc 最强** | PyMuPDF + **PageIndex（长 PDF）** |
| **RAG 技术数** | 12 种 | 9 种 | 7 种 | 6 种（含 PageIndex） |
| **多用户** | 完整 RBAC | 工作空间隔离 | RAGFlow 团队 | YAML 3角色 |
| **数据私有性** | 可自托管 | 可自托管 | **完全本地** | **完全本地** |
| **适合阶段** | Phase 3+ | Phase 2+ | Phase 2 | **Phase 1** |

---

*Match-3 Knowledge Base Design · Solution D — Lightweight Local Stack*

> **Nav:** [← 返回总览](overview.md) | [方案 A 全栈定制](solution-a-fullstack.md) | [方案 B Dify ⭐](solution-b-dify.md) | [方案 C RAGFlow](solution-c-ragflow.md)
