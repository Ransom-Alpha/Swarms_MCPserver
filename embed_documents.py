from __future__ import annotations
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Any  # Added Any for type annotations

from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PythonLoader, NotebookLoader, TextLoader
from langchain_community.document_loaders.markdown import UnstructuredMarkdownLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# ==== Setup ====
BASE_DIR = Path(__file__).resolve().parent
CORPUS_DIR = BASE_DIR / "corpora"
INDEX_DIR = CORPUS_DIR / "index"
COLL_NAME = "swarms_docs"

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("embedder")

# These can now be overridden via CLI
EMBED_MODEL = "text-embedding-3-large"
CHUNK_SIZE = 500
OVERLAP = 50

LOADER_SPECS = [
    ("**/*.py", PythonLoader, {}),
    ("**/*.ipynb", NotebookLoader, {"include_outputs": False}),
    ("**/*.md", "dynamic_md", {}),
    ("**/*.txt", TextLoader, {}),
    ("**/*.yml", TextLoader, {}),
    ("**/*.yaml", TextLoader, {}),
]

# ==== Helpers ====

def _dynamic_md_loader(filepath: Path):
    """
    Dynamically select loader for markdown files based on size.
    Uses UnstructuredMarkdownLoader for small files, TextLoader for large files.
    """
    size_kb = filepath.stat().st_size / 1024
    if size_kb < 50:
        log.info(f"Using UnstructuredMarkdownLoader for small .md file ({size_kb:.1f} KB): {filepath}")
        return UnstructuredMarkdownLoader(str(filepath), mode="single")
    else:
        log.info(f"Using TextLoader fallback for large .md file ({size_kb:.1f} KB): {filepath}")
        return TextLoader(str(filepath))

def embed_and_save_documents(skip_prompt: bool = False, chunk_size: int = 500, overlap: int = 50, embed_model: str = "text-embedding-3-small") -> bool:
    """
    Loads, embeds, and saves all documents in CORPUS_DIR to the Chroma index.
    Returns True if embedding was successful, False otherwise.
    """
    log.info("\U0001F4DA Starting document load...")
    docs, total, skipped, file_chunk_counts = _load_documents(chunk_size, overlap)
    log.info(f"\n✨ Loading summary:\n  Files attempted: {total}\n  Files succeeded: {total - skipped}\n  Files skipped:   {skipped}\n  Total chunks:    {len(docs)}")

    if not docs:
        log.error("No valid documents found. Exiting.")
        return False

    if not skip_prompt:
        try:
            proceed = input("\nProceed with embedding and building index? (y/n): ").strip().lower()
            if proceed != "y":
                log.warning("Cancelled by user.")
                return False
        except EOFError:
            log.warning("No input available; cancelling embedding.")
            return False

    try:
        # Use the specified embedding model
        embeddings = OpenAIEmbeddings(model=embed_model)
        # Clear previous index if exists (optional, but recommended)
        import shutil
        if Path(INDEX_DIR).exists():
            shutil.rmtree(INDEX_DIR)
        Chroma.from_documents(docs, embeddings, persist_directory=str(INDEX_DIR), collection_name=COLL_NAME)
        log.info("✅ Embeddings and index built!")
        log.info("\nFile chunk counts:")
        for fname, count in file_chunk_counts.items():
            log.info(f"  {fname}: {count} chunks")
        return True
    except Exception as e:
        log.error(f"❌ Failed to build Chroma index: {e}")
        return False

def _load_documents(chunk_size: int, overlap: int) -> tuple[List[Any], int, int, dict]:
    """
    Loads and splits all supported files in CORPUS_DIR.
    Returns (chunks, total_files, skipped_files, file_chunk_counts).
    Each chunk includes document-level metadata for aggregation.
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    docs, total_files, skipped = [], 0, 0
    file_chunk_counts = {}
    import uuid
    import mimetypes
    from pathlib import Path

    def get_loader_for_file(filepath: Path):
        ext = filepath.suffix.lower()
        if ext == ".py":
            return PythonLoader(str(filepath))
        elif ext == ".ipynb":
            return NotebookLoader(str(filepath), include_outputs=False)
        elif ext == ".md":
            return _dynamic_md_loader(filepath)
        elif ext in [".txt", ".yml", ".yaml"]:
            return TextLoader(str(filepath))
        else:
            return None

    for pattern, _, _ in LOADER_SPECS:
        for filepath in CORPUS_DIR.glob(pattern):
            total_files += 1
            try:
                loader = get_loader_for_file(filepath)
                if loader is None:
                    log.warning(f"No loader for {filepath}, skipping.")
                    skipped += 1
                    continue
                file_docs = loader.load()
                # Add full-file chunk
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    full_content = f.read()
                file_size = filepath.stat().st_size
                mimetype, _ = mimetypes.guess_type(str(filepath))
                file_type = mimetype or filepath.suffix[1:] or "unknown"
                tags = [filepath.suffix[1:], filepath.parent.name]
                full_file_meta = {
                    "filename": str(filepath.name),
                    "source": str(filepath),
                    "file_type": file_type,
                    "file_size": file_size,
                    "tags": tags,
                    "chunk_index": -1,
                    "is_full_file": True,
                    "id": str(uuid.uuid4()),
                }
                docs.append(type(file_docs[0])(page_content=full_content, metadata=full_file_meta))
                # Chunked content
                chunked = splitter.split_documents(file_docs)
                for idx, chunk in enumerate(chunked):
                    chunk.metadata.update({
                        "filename": str(filepath.name),
                        "source": str(filepath),
                        "file_type": file_type,
                        "file_size": file_size,
                        "tags": tags,
                        "chunk_index": idx,
                        "is_full_file": False,
                        "id": str(uuid.uuid4()),
                    })
                docs.extend(chunked)
                file_chunk_counts[str(filepath.name)] = len(chunked)
                log.info(f"✅ Loaded {len(chunked)} chunks from {filepath} in 0.00s (tags={tags})")
            except Exception as e:
                log.error(f"❌ Failed loading {filepath}: {e}")
                skipped += 1
    return docs, total_files, skipped, file_chunk_counts
    files = [f for f in CORPUS_DIR.rglob("*") if f.is_file()]

    for file in files:
        total_files += 1
        loader = None
        for pattern, loader_class, kwargs in LOADER_SPECS:
            if file.match(pattern):
                if loader_class == "dynamic_md":
                    loader = _dynamic_md_loader(file)
                elif loader_class == "generic":
                    loader = TextLoader(str(file))
                else:
                    loader = loader_class(str(file), **kwargs)
                break
        if not loader:
            log.warning(f"Skipping unsupported file: {file}")
            skipped += 1
            continue
        try:
            start = time.time()
            # --- Load and split file into chunks ---
            chunks = loader.load_and_split(splitter)
            elapsed = time.time() - start
            if not chunks:
                raise ValueError("Empty chunks")
            # Add document-level metadata to each chunk
            tags = []
            # Tag by extension
            if file.suffix:
                tags.append(file.suffix.lstrip('.').lower())
            # Tag by top-level directory if relevant
            try:
                rel_path = file.relative_to(CORPUS_DIR)
                if len(rel_path.parts) > 1:
                    tags.append(rel_path.parts[0].lower())
            except Exception:
                pass
            for idx, chunk in enumerate(chunks):
                chunk.metadata = chunk.metadata or {}
                chunk.metadata['source'] = str(file)
                chunk.metadata['filename'] = file.name
                chunk.metadata['file_size'] = file.stat().st_size
                chunk.metadata['file_type'] = file.suffix
                chunk.metadata['chunk_index'] = idx
                chunk.metadata['is_full_file'] = False
                chunk.metadata['tags'] = tags
            docs.extend(chunks)
            file_chunk_counts[file.name] = len(chunks)
            log.info(f"✅ Loaded {len(chunks)} chunks from {file} in {elapsed:.2f}s (tags={tags})")
            # --- Add a special chunk containing the full file content ---
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                full_content = f.read()
            full_chunk = type(chunks[0]).from_text(full_content, metadata={
                'source': str(file),
                'filename': file.name,
                'file_size': file.stat().st_size,
                'file_type': file.suffix,
                'chunk_index': -1,
                'is_full_file': True,
                'tags': tags
            })
            docs.append(full_chunk)
            log.info(f"  ➕ Added full-file chunk for {file.name} (is_full_file=True, tags={tags})")
        except Exception as e:
            log.error(f"❌ Failed loading {file}: {e}")
            skipped += 1
    return docs, total_files, skipped, file_chunk_counts

# ==== Main ====

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="Skip prompt and immediately proceed with embedding.")
    parser.add_argument("--chunk-size", type=int, default=500, help="Chunk size for text splitting (default: 500)")
    parser.add_argument("--overlap", type=int, default=50, help="Chunk overlap for text splitting (default: 50)")
    parser.add_argument("--embed-model", type=str, default="text-embedding-3-small", help="OpenAI embedding model (default: text-embedding-3-small)")
    args = parser.parse_args()

    success = embed_and_save_documents(skip_prompt=args.yes, chunk_size=args.chunk_size, overlap=args.overlap, embed_model=args.embed_model)
    if not success:
        sys.exit(1)
