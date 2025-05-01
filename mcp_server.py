# Ensure all dependencies (agents, langchain_chroma, langchain_openai) are installed.
# Ensure the 'corpora/index' directory exists and is initialized by embed_documents.py.
import asyncio
from agents.mcp import MCPServer
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from pathlib import Path
import logging

# ==== Setup logging for tracing tool calls ====
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("mcp_server")

# ==== Healthcheck Tool ====
async def healthcheck(params=None):
    """
    Return server health, index stats, and summary info.
    Args: None
    Returns: dict with status, doc count, chunk count, file types, tags, last update, etc.
    """
    log.info("[healthcheck] called")
    all_docs = vectorstore.get()
    doc_count = len(set(meta.get('filename') for meta in all_docs['metadatas']))
    chunk_count = len(all_docs['documents'])
    file_types = list(set(meta.get('file_type') for meta in all_docs['metadatas']))
    tags = set()
    for meta in all_docs['metadatas']:
        tags.update(meta.get('tags', []))
    return {
        "status": "ok",
        "doc_count": doc_count,
        "chunk_count": chunk_count,
        "file_types": file_types,
        "tags": list(tags),
    }

# ==== List Files Tool ====
async def list_files(params=None):
    """
    List all files indexed, with metadata and tags.
    Args: None
    Returns: list of {filename, source, file_type, file_size, tags}
    """
    log.info("[list_files] called")
    all_docs = vectorstore.get()
    files = {}
    for meta in all_docs['metadatas']:
        fname = meta.get('filename')
        if fname not in files or meta.get('is_full_file'):
            files[fname] = {
                'filename': fname,
                'source': meta.get('source'),
                'file_type': meta.get('file_type'),
                'file_size': meta.get('file_size'),
                'tags': meta.get('tags', []),
            }
    return {'files': list(files.values())}

# ==== Get File Info Tool ====
async def get_file_info(params):
    """
    Get metadata for a given filename.
    Args: params: {filename: str}
    Returns: dict with metadata or error
    """
    log.info(f"[get_file_info] params: {params}")
    fname = params.get('filename')
    if not fname:
        return {"error": "filename is required"}
    all_docs = vectorstore.get()
    for meta in all_docs['metadatas']:
        if meta.get('filename') == fname and meta.get('is_full_file'):
            return {"metadata": meta}
    return {"error": f"File {fname} not found"}

# ==== Get Chunk By ID Tool ====
async def get_chunk_by_id(params):
    """
    Retrieve a chunk by (filename, chunk_index) or by unique id.
    Args: params: {filename: str, chunk_index: int} OR {id: str}
    Returns: dict with content and metadata or error
    """
    log.info(f"[get_chunk_by_id] params: {params}")
    fname = params.get('filename')
    idx = params.get('chunk_index')
    chunk_id = params.get('id')
    all_docs = vectorstore.get()
    for doc, meta in zip(all_docs['documents'], all_docs['metadatas']):
        if chunk_id and meta.get('id') == chunk_id:
            return {"content": doc.page_content, "metadata": meta}
        if fname and idx is not None and meta.get('filename') == fname and meta.get('chunk_index') == idx:
            return {"content": doc.page_content, "metadata": meta}
    return {"error": "Chunk not found"}

# ==== Search Files Tool ====
async def search_files(params):
    """
    Search files by filename, file_type, or tags (OR logic).
    Args: params: {filename: str (optional), file_type: str (optional), tag: str (optional)}
    Returns: list of matching files (with metadata)
    """
    log.info(f"[search_files] params: {params}")
    fname = params.get('filename', '').lower()
    ftype = params.get('file_type', '').lower()
    tag = params.get('tag', '').lower()
    all_docs = vectorstore.get()
    files = {}
    for meta in all_docs['metadatas']:
        match = False
        if fname and fname in meta.get('filename', '').lower():
            match = True
        if ftype and ftype == (meta.get('file_type') or '').lower():
            match = True
        if tag and tag in [t.lower() for t in meta.get('tags', [])]:
            match = True
        if match and (meta.get('is_full_file') or meta.get('chunk_index') == -1):
            files[meta.get('filename')] = {
                'filename': meta.get('filename'),
                'source': meta.get('source'),
                'file_type': meta.get('file_type'),
                'file_size': meta.get('file_size'),
                'tags': meta.get('tags', []),
            }
    return {'files': list(files.values())}

# ==== New Tools for Whole-Document and Full-File Search ====
async def get_full_document(params):
    """
    Aggregate and return all chunks for a given document by filename or source.
    Args:
        params: dict with 'filename' or 'source' (at least one required)
    Returns:
        dict: { 'full_content': str, 'chunks': list, 'metadata': dict }
    """
    log.info(f"[get_full_document] params: {params}")
    filename = params.get('filename')
    source = params.get('source')
    if not filename and not source:
        return {"error": "Must provide 'filename' or 'source'"}
    all_docs = vectorstore.get()
    # Aggregate all chunks for this document
    matched_chunks = []
    for doc, meta in zip(all_docs['documents'], all_docs['metadatas']):
        if filename and meta.get('filename') == filename:
            matched_chunks.append((meta.get('chunk_index', 0), doc.page_content, meta))
        elif source and meta.get('source') == source:
            matched_chunks.append((meta.get('chunk_index', 0), doc.page_content, meta))
    # Sort by chunk_index (if present) for correct order
    matched_chunks.sort(key=lambda x: x[0])
    full_content = "\n".join([c[1] for c in matched_chunks])
    return {
        "full_content": full_content,
        "chunks": [dict(content=c[1], metadata=c[2]) for c in matched_chunks],
        "metadata": matched_chunks[0][2] if matched_chunks else {},
    }

async def full_file_content_search(params):
    """
    Case-insensitive substring search over original file content only (not chunks).
    Args:
        params: dict with key 'keyword': str
    Returns:
        dict: { 'results': [ { 'content': str, 'metadata': dict } ] }
    """
    log.info(f"[full_file_content_search] params: {params}")
    keyword = params.get('keyword', '').lower()
    all_docs = vectorstore.get()
    results = []
    for doc, meta in zip(all_docs['documents'], all_docs['metadatas']):
        if meta.get('is_full_file'):
            if keyword in doc.page_content.lower():
                results.append({"content": doc.page_content, "metadata": meta})
    return {"results": results}

BASE_DIR = Path(__file__).resolve().parent
INDEX_DIR = BASE_DIR / "corpora" / "index"
COLL_NAME = "swarms_docs"
EMBED_MODEL = "text-embedding-3-small"
EMBEDDINGS = OpenAIEmbeddings(model=EMBED_MODEL)

# Load persistent ChromaDB (must be created by embed_documents.py)
try:
    vectorstore = Chroma(
        collection_name=COLL_NAME,
        persist_directory=str(INDEX_DIR),
        embedding_function=EMBEDDINGS,
    )
except Exception as e:
    raise RuntimeError(f"Failed to initialize vectorstore: {e}. Ensure 'corpora/index' exists and is initialized by embed_documents.py.")

async def query_database(params):
    """
    Query the persistent vector database (ChromaDB) for top-k relevant chunks.
    Args:
        params: dict with keys:
            - 'query': str (query string)
            - 'k': int (optional, default 5)
    Returns:
        dict: { 'results': [ { 'content': str, 'score': float } ] }
    """
    log.info(f"[query_database] params: {params}")
    query = params.get('query', '')
    k = params.get('k', 5)
    docs_and_scores = vectorstore.similarity_search_with_score(query, k=k)
    results = [
        {"content": doc.page_content, "score": score, "metadata": doc.metadata}
        for doc, score in docs_and_scores
    ]
    return {"results": results}

async def filtered_search(params):
    """
    Semantic search with optional filename filter.
    Args:
        params: dict with keys:
            - 'query': str
            - 'filename': str (optional, substring match)
            - 'k': int (optional, default 5)
    Returns:
        dict: { 'results': [ { 'content': str, 'metadata': dict, 'score': float } ] }
    """
    log.info(f"[filtered_search] params: {params}")
    query = params.get('query', '')
    filename = params.get('filename')
    k = params.get('k', 5)
    docs_and_scores = vectorstore.similarity_search_with_score(query, k=k)
    filtered = []
    for doc, score in docs_and_scores:
        if filename:
            if filename.lower() in doc.metadata.get('source', '').lower():
                filtered.append({"content": doc.page_content, "metadata": doc.metadata, "score": score})
        else:
            filtered.append({"content": doc.page_content, "metadata": doc.metadata, "score": score})
    return {"results": filtered}

async def full_text_search(params):
    """
    Case-insensitive substring search over all documents.
    Args:
        params: dict with key 'keyword': str
    Returns:
        dict: { 'results': [ { 'content': str, 'metadata': dict } ] }
    """
    log.info(f"[full_text_search] params: {params}")
    keyword = params.get('keyword', '').lower()
    all_docs = vectorstore.get()
    results = []
    for doc, meta in zip(all_docs['documents'], all_docs['metadatas']):
        if keyword in doc.page_content.lower():
            results.append({"content": doc.page_content, "metadata": meta})
    return {"results": results}

async def hybrid_search(params):
    """
    Combine vector and keyword search. Return docs matching either method.
    Args:
        params: dict with keys:
            - 'query': str
            - 'keyword': str
            - 'k': int (optional, default 5)
    Returns:
        dict: { 'results': [ { 'content': str, 'metadata': dict } ] }
    """
    log.info(f"[hybrid_search] params: {params}")
    query = params.get('query', '')
    keyword = params.get('keyword', '').lower()
    k = params.get('k', 5)
    vector_results = set()
    docs_and_scores = vectorstore.similarity_search_with_score(query, k=k)
    for doc, score in docs_and_scores:
        vector_results.add(doc.page_content)
    all_docs = vectorstore.get()
    hybrid = []
    for doc, meta in zip(all_docs['documents'], all_docs['metadatas']):
        if (keyword and keyword in doc.page_content.lower()) or (doc.page_content in vector_results):
            hybrid.append({"content": doc.page_content, "metadata": meta})
    return {"results": hybrid}

async def get_document_by_id(params):
    """
    Retrieve document content and metadata by its unique ID.
    Args:
        params: dict with key 'doc_id': str
    Returns:
        dict: { 'content': str, 'metadata': dict } or error
    """
    log.info(f"[get_document_by_id] params: {params}")
    doc_id = params.get('doc_id')
    if not doc_id:
        return {"error": "doc_id is required"}
    all_docs = vectorstore.get(ids=[doc_id])
    if not all_docs['documents']:
        return {"error": f"No document found with id {doc_id}"}
    return {"content": all_docs['documents'][0].page_content, "metadata": all_docs['metadatas'][0]}

async def list_documents(params):
    """
    List all documents with their IDs and metadata (no full content).
    Args:
        params: dict (not used)
    Returns:
        dict: { 'documents': [ { 'id': str, 'metadata': dict } ] }
    """
    log.info(f"[list_documents] params: {params}")
    all_docs = vectorstore.get()
    results = []
    for doc_id, meta in zip(all_docs['ids'], all_docs['metadatas']):
        results.append({"id": doc_id, "metadata": meta})
    return {"documents": results}

async def get_document_metadata(params):
    """
    Retrieve only metadata for a given document.
    Args:
        params: dict with key 'doc_id': str
    Returns:
        dict: { 'metadata': dict } or error
    """
    log.info(f"[get_document_metadata] params: {params}")
    doc_id = params.get('doc_id')
    if not doc_id:
        return {"error": "doc_id is required"}
    all_docs = vectorstore.get(ids=[doc_id])
    if not all_docs['metadatas']:
        return {"error": f"No metadata found for id {doc_id}"}
    return {"metadata": all_docs['metadatas'][0]}

TOOLS = [
    # Healthcheck
    {
        "name": "healthcheck",
        "description": "Return server health, index stats, and summary info.",
        "parameters": {},
        "function": healthcheck,
    },
    # List all files
    {
        "name": "list_files",
        "description": "List all files indexed, with metadata and tags.",
        "parameters": {},
        "function": list_files,
    },
    # Get file info
    {
        "name": "get_file_info",
        "description": "Get metadata for a given filename.",
        "parameters": {"filename": "string"},
        "function": get_file_info,
    },
    # Get chunk by id or (filename, chunk_index)
    {
        "name": "get_chunk_by_id",
        "description": "Retrieve a chunk by (filename, chunk_index) or by unique id.",
        "parameters": {"filename": "string (optional)", "chunk_index": "int (optional)", "id": "string (optional)"},
        "function": get_chunk_by_id,
    },
    # Search files by filename/type/tags
    {
        "name": "search_files",
        "description": "Search files by filename, file_type, or tags (OR logic).",
        "parameters": {"filename": "string (optional)", "file_type": "string (optional)", "tag": "string (optional)"},
        "function": search_files,
    },
    # Existing tools below:
    {
        "name": "query_database",
        "description": "Query the persistent vector database for relevant documents.",
        "parameters": {"query": "string", "k": "int (optional, default 5)"},
        "function": query_database,
    },
    {
        "name": "filtered_search",
        "description": "Semantic search with optional filename filter.",
        "parameters": {"query": "string", "filename": "string (optional)", "k": "int (optional, default 5)"},
        "function": filtered_search,
    },
    {
        "name": "full_text_search",
        "description": "Case-insensitive substring search over all documents. Supports optional filename, file_type, or tag filter.",
        "parameters": {"keyword": "string", "filename": "string (optional)", "file_type": "string (optional)", "tag": "string (optional)"},
        "function": full_text_search,
    },
    {
        "name": "hybrid_search",
        "description": "Combine vector and keyword search for robust retrieval. Supports optional filename, file_type, or tag filter.",
        "parameters": {"query": "string", "keyword": "string", "k": "int (optional, default 5)", "filename": "string (optional)", "file_type": "string (optional)", "tag": "string (optional)"},
        "function": hybrid_search,
    },
    {
        "name": "get_document_by_id",
        "description": "Retrieve document content and metadata by unique ID.",
        "parameters": {"doc_id": "string"},
        "function": get_document_by_id,
    },
    {
        "name": "list_documents",
        "description": "List all documents with IDs and metadata.",
        "parameters": {},
        "function": list_documents,
    },
    {
        "name": "get_document_metadata",
        "description": "Retrieve only metadata for a given document.",
        "parameters": {"doc_id": "string"},
        "function": get_document_metadata,
    },
    # Retrieve all chunks for a document and aggregate as full content
    {
        "name": "get_full_document",
        "description": "Aggregate and return all chunks for a given document by filename or source.",
        "parameters": {"filename": "string (optional)", "source": "string (optional)"},
        "function": get_full_document,
    },
    # Search only the special full-file chunks
    {
        "name": "full_file_content_search",
        "description": "Case-insensitive substring search over original file content only (not chunks).",
        "parameters": {"keyword": "string"},
        "function": full_file_content_search,
    },
]

class CustomMCPServer(MCPServer):
    """
    Custom MCP server exposing advanced search and document retrieval tools for the vector database.
    Implements required MCPServer methods and tool registry.
    """
    def __init__(self):
        super().__init__(name="Custom DB MCP Server")
        self.tools = TOOLS

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.cleanup()

    @property
    def name(self):
        return "Custom DB MCP Server"

    async def connect(self):
        # No connection logic needed for in-process server
        log.info("[CustomMCPServer] connect() called.")
        pass

    async def cleanup(self):
        # No cleanup needed for in-process server
        log.info("[CustomMCPServer] cleanup() called.")
        pass

    async def call_tool(self, tool_name, params):
        log.info(f"[CustomMCPServer] call_tool: {tool_name} params: {params}")
        return await self.run_tool(tool_name, params)

    async def list_tools(self):
        log.info("[CustomMCPServer] list_tools() called.")
        return [
            dict(name=tool["name"], description=tool["description"], parameters=tool["parameters"])
            for tool in self.tools
        ]

    async def run_tool(self, tool_name, params):
        for tool in self.tools:
            if tool["name"] == tool_name:
                return await tool["function"](params)
        log.error(f"Tool {tool_name} not found.")
        raise Exception(f"Tool {tool_name} not found.")

async def main():
    async with CustomMCPServer() as server:
        tools = await server.list_tools()
        print("Available tools:", tools)
        # Example usage
        # Removed invalid tool call: await server.run_tool("embed_documents", ...)
        result = await server.run_tool("query_database", {"query": "fox"})
        print("Query result:", result)

if __name__ == "__main__":
    asyncio.run(main())
