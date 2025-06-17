[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/ransom-alpha-swarms-mcpserver-badge.png)](https://mseep.ai/app/ransom-alpha-swarms-mcpserver)

# 🐝 Swarms MCP Documentation Server

<p align="center">
  <img src="https://img.shields.io/badge/Windsurf_Ready-✅-orange" alt="IDE Ready">
  <img src="https://img.shields.io/badge/Error_Tolerant-✅-green" alt="Error Tolerant">
  <img src="https://img.shields.io/badge/Dynamic_MD_Loader-✅-blue" alt="Dynamic MD Loader">
  <img src="https://img.shields.io/badge/Healthcheck_Tool-✅-success" alt="Healthcheck Tool">
  <img src="https://img.shields.io/badge/Smart_Load_Logs-✅-purple" alt="Smart Load Logs">
</p>

![Version 2.2](https://img.shields.io/badge/Version-2.2-blueviolet)

---

## 📖 Description

This program is an **Agent Framework** Documentation MCP Server built on **FastMCP**, designed to enable **AI agents** to efficiently retrieve information from your documentation database. It combines hybrid semantic (vector) and keyword (BM25) search, chunked indexing, and a robust FastMCP tools API for seamless agent integration.

**Key Capabilities:**
- Efficient, chunk-level retrieval using both semantic and keyword search
- Agents can query, list, and retrieve documentation using FastMCP tools
- Local-first, low-latency design (all data indexed and queried locally)
- Automatic reindexing on file changes
- Modular: add any repos to `corpora/`, support for all major filetypes
- Extensible: add new tools, retrievers, or corpora as needed

**Main modules:**
- `embed_documents.py` → Loads, chunks, and embeds documents
- `swarms_server.py` → Brings up the MCP server and FastMCP tools

---

---

## 🌟 Key Features

- **Hybrid Retriever** 🔍: Combines semantic and keyword search.
- **Dynamic Markdown Handling** 📄: Smart loader based on file size.
- **Specialized Loaders** ⚙️: `.py`, `.ipynb`, `.md`, `.txt`, `.yaml`, `.yml`.
- **Chunk and File Summaries** 📈: Displays chunk counts along with file counts.
- **Live Watchdog** 🔥: Instantly responds to any changes in `corpora/`.
- **User Confirmation for Costs** ✅: Confirms before expensive embeddings.
- **Healthcheck Endpoint** 🚑: Ensure server is ready for use.
- **Local-First** 🗂️: All repos indexed locally without external dependencies.
- **Safe Deletion Helper** 🔥: Auto-delete broken/mismatched indexes.

---

## 🏗️ Version History

| Version | Date       | Highlights                                                              |
| ------- | ---------- | ---------------------------------------------------------------------- |
| **2.2** | 2025‑04‑25 | Split embed/load from server; full chunk counting in loading summaries |
| **1.0** | 2025‑04‑25 | Dynamic Markdown loader, color logs, Healthcheck tool                  |
| **0.7** | 2025‑04‑25 | Specialized file loaders for `.py`, `.ipynb`, `.md`                    |
| **0.5** | 2025‑04‑10 | OpenAI large model embeddings, extended MCP tools                      |
| **0.1** | 2025‑04‑10 | Initial version with generic loaders                                   |

---

## 📚 Managing Your Corpora (Local Repos)

Because Swarms and other frameworks are **very large**, full corpora are **not** pushed to GitHub.

Instead, you **clone** them manually under `corpora/`:

```bash
# Inside your project folder:
cd corpora/

# Clone useful frameworks:
git clone https://github.com/SwarmsAI/Swarms
git clone https://github.com/SwarmsAI/Swarms-Examples
git clone https://github.com/microsoft/autogen
git clone https://github.com/langchain-ai/langgraph
git clone https://github.com/openai/openai-agent-sdk
```

✅ **Notes:**
- Add **any repo** — public, private, custom.
- Build your own custom AI knowledge base locally.
- **Large repos** (>500MB) are fine; all indexing is local.

---

## 🚀 Quick Start

```powershell
# 1. Activate virtual environment
venv\Scripts\Activate.ps1

# 2. Install all dependencies
pip install -r requirements.txt

# 3. Configure OpenAI API Key
echo OPENAI_API_KEY=sk-... > .env

# 4. (Load and embed documents
python embed_documents.py

# 5. Start MCP server
python swarms_server.py
# If no index is found, the server will prompt you to embed documents automatically.
```

---

## ⚙️ Configuration

- **Corpus**: Drop repos inside `corpora/`
- **Environment Variables**:
  - `.env` must contain `OPENAI_API_KEY`
- **Index File Support**:
  - Both `chroma-collections.parquet` and `chroma.sqlite3` are supported. `.parquet` is preferred if both exist.
- **Auto-Embedding**:
  - If no index is found, the server will prompt you to embed and index your documents automatically.
- **Optional**:
  - Disable Chroma compaction if you prefer:
    ```powershell
    setx CHROMA_COMPACTION_SERVICE__COMPACTOR__DISABLED_COLLECTIONS "swarms_docs"
    ```
- **Command-Line Flags**:
  - `--reindex` → trigger a refresh reindex during server run.

---

## 🔄 File Watching & Auto Reindexing

The MCP Server watches `corpora/` for any file changes:
- Any modification, creation, or deletion triggers a **live** reindex.
- No need to restart the server.

---

## 🛠️ Available FastMCP Tools

| Tool                      | Description                                          |
| ------------------------- | ---------------------------------------------------- |
| `swarm_docs.search`       | Search relevant documentation chunks                |
| `swarm_docs.list_files`   | List all indexed files                               |
| `swarm_docs.get_chunk`    | Get a specific chunk by path and index               |
| `swarm_docs.reindex`      | Force reindex (full or incremental)                  |
| `swarm_docs.healthcheck`  | Check MCP Server status                              |

---

## ❓ Troubleshooting

- **Q: I get 'No valid existing index found' when starting the server.**
  - A: The server will now prompt you to embed and index documents. Accept the prompt to proceed, or run `python embed_documents.py` manually first.
- **Q: Which index file is used?**
  - A: The server will use `chroma-collections.parquet` if available, otherwise `chroma.sqlite3`.
- **Q: I want to force a reindex.**
  - A: Run `python swarms_server.py --reindex` or use the `swarm_docs.reindex` tool.

---

## 📋 Example Usage

```python
# Search the documentation
result = swarm_docs.search("How do I load a notebook?")
print(result)

# List all available files
files = swarm_docs.list_files()
print(files)

# Get a specific document chunk
chunk = swarm_docs.get_chunk(path="examples/agent.py", chunk_idx=2)
print(chunk["content"])
```

---

## 🧰 Extending & Rebuilding

- **Add new docs** → drop into `corpora/`, then:
  ```bash
  python swarms_server.py --reindex
  ```
- **Schema changes** → (e.g. different metadata structure):
  ```bash
  python swarms_server.py --reindex --full
  ```
- **Add new repo** → Drop folder under `corpora/`, reindex.

- **Recommended for mostly read-only repos**:
  ```powershell
  setx CHROMA_COMPACTION_SERVICE__COMPACTOR__DISABLED_COLLECTIONS "swarms_docs"
  ```

---

## 🔗 IDE Integration

Plug directly into Windsurf Cascade:

```jsonc
"swarms": {
  "command": "C:/…/Swarms/venv/Scripts/python.exe",
  "args": ["swarms_server.py"]
}
```

Then you can access `swarm_docs.*` tools from Cascade automations.

---

## 📦 Requirements

### 💡 Python 3.11 Environment Required

Create your environment explicitly:

```bash
python3.11 -m venv venv
```

Then install with:

```bash
pip install -r requirements.txt
```

---

## ✅ MCP Server Ready

After boot:
- Proper loading summaries
- Safe confirmation before expensive actions
- Auto file watching and reindexing
- Windsurf plug-in ready
- Full tool coverage

**You're good to cascade it!** 🏄‍♂️

---

## 📈 Flow Diagram

```
                          +------------------+
                          |    🖥️ MCP Server  |
                          +------------------+
                                  |
     +---------------------------------------------------+
     |                                                   |
+-------------+                                     +-----------------+
|  📁 Corpora |                                     | 🔎 FastMCP Tools |
|  Folder     |                                     | (search, list,   |
|  (markdown, |                                     | get_chunk, etc.) |
|  code, etc) |                                     +-----------------+
+-------------+                                               |
      |                                                       |
+-----------------+                                   +----------------+
|  📚 Loaders      |                                   | 🧠 Ensemble    |
| (Python, MD, TXT)|                                   | Retriever (BM25|
|  Split into Chunks|                                  | + Chroma)      |
+-----------------+                                   +----------------+
      |                                                       |
+-----------------+                                   +----------------+
| ✂️ Text Splitter |                                   | 🧩 Similarity   |
| (RecursiveCharacter) |                              | Search (chunks) |
+-----------------+                                   +----------------+
      |                                                       |
+-----------------+                                   +----------------+
| 💾 Embed chunks  |  —OpenAI Embedding (small)—>    | 🛢️ Chroma Vector |
| via OpenAI API  |                                   | DB (Local Store) |
+-----------------+                                   +----------------+
      |                                                       |
+-----------------+                                   +----------------+
| 📡 Reindex Watcher|                                  | 👀 File Watchdog |
| (Auto detect      |                                  | (Auto reindex   |
| new/modified files|                                  | on file events) |
+-----------------+                                   +----------------+
```
