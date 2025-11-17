"""Knowledge base service with RAG (Retrieval-Augmented Generation) support."""

import pickle
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings


class Document:
    """Document class for storing text chunks with metadata."""

    def __init__(self, content: str, metadata: Optional[dict[str, Any]] = None):
        """Initialize document.

        Args:
            content: Document text content
            metadata: Optional metadata dictionary
        """
        self.content = content
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"Document(content='{self.content[:50]}...', metadata={self.metadata})"


class VectorStore:
    """Vector store for similarity search using FAISS."""

    def __init__(self, embedding_model: SentenceTransformer):
        """Initialize vector store.

        Args:
            embedding_model: Sentence transformer model for embeddings
        """
        try:
            import faiss

            self.faiss = faiss
            self.embedding_model = embedding_model
            self.index: Optional[Any] = None
            self.documents: list[Document] = []
            self.dimension: Optional[int] = None

            logger.info("Vector store initialized")

        except ImportError:
            raise ImportError("FAISS not installed. Install with: pip install faiss-cpu")

    def add_documents(self, documents: list[Document]) -> None:
        """Add documents to the vector store.

        Args:
            documents: List of documents to add
        """
        if not documents:
            logger.warning("No documents to add")
            return

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(documents)} documents")
        texts = [doc.content for doc in documents]
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True)

        # Initialize index if needed
        if self.index is None:
            self.dimension = embeddings.shape[1]
            self.index = self.faiss.IndexFlatL2(self.dimension)
            logger.info(f"Created FAISS index with dimension {self.dimension}")

        # Add to index
        self.index.add(embeddings.astype(np.float32))
        self.documents.extend(documents)

        logger.info(f"Added {len(documents)} documents. Total: {len(self.documents)}")

    def search(self, query: str, top_k: int = 3) -> list[tuple[Document, float]]:
        """Search for similar documents.

        Args:
            query: Query text
            top_k: Number of results to return

        Returns:
            List of tuples (document, similarity_score)
        """
        if self.index is None or len(self.documents) == 0:
            logger.warning("Vector store is empty")
            return []

        # Generate query embedding
        query_embedding = self.embedding_model.encode([query])

        # Search
        distances, indices = self.index.search(query_embedding.astype(np.float32), top_k)

        # Prepare results
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < len(self.documents):
                # Convert L2 distance to similarity score (lower is better, so invert)
                similarity = 1 / (1 + distance)
                results.append((self.documents[idx], float(similarity)))

        return results

    def save(self, path: Path) -> None:
        """Save vector store to disk.

        Args:
            path: Directory path to save to
        """
        path.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        if self.index is not None:
            self.faiss.write_index(self.index, str(path / "index.faiss"))

        # Save documents
        with open(path / "documents.pkl", "wb") as f:
            pickle.dump(self.documents, f)

        logger.info(f"Vector store saved to {path}")

    def load(self, path: Path) -> None:
        """Load vector store from disk.

        Args:
            path: Directory path to load from
        """
        index_path = path / "index.faiss"
        docs_path = path / "documents.pkl"

        if not index_path.exists() or not docs_path.exists():
            logger.warning(f"Vector store files not found at {path}")
            return

        # Load FAISS index
        self.index = self.faiss.read_index(str(index_path))
        self.dimension = self.index.d

        # Load documents
        with open(docs_path, "rb") as f:
            self.documents = pickle.load(f)

        logger.info(f"Vector store loaded from {path}. Total documents: {len(self.documents)}")


class KnowledgeBase:
    """Knowledge base service for document loading and retrieval."""

    def __init__(self):
        """Initialize knowledge base service."""
        settings = get_settings()
        self.settings = settings

        # Load embedding model
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        self.embedding_model = SentenceTransformer(settings.embedding_model)

        # Initialize vector store
        self.vector_store = VectorStore(self.embedding_model)

        # Try to load existing vector store
        vector_store_path = Path("vector_store")
        if vector_store_path.exists():
            self.vector_store.load(vector_store_path)
        else:
            logger.info("No existing vector store found. Will create new one when documents are loaded.")

        logger.info("Knowledge base initialized")

    def load_documents_from_directory(self, directory: str | Path) -> None:
        """Load documents from a directory.

        Args:
            directory: Path to directory containing text files
        """
        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"Knowledge base directory not found: {directory}")
            return

        documents = []
        supported_extensions = {".txt", ".md", ".text"}

        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Split into chunks
                    chunks = self._split_text(content)

                    for i, chunk in enumerate(chunks):
                        doc = Document(
                            content=chunk,
                            metadata={
                                "source": str(file_path),
                                "chunk_index": i,
                                "total_chunks": len(chunks)
                            }
                        )
                        documents.append(doc)

                    logger.info(f"Loaded {len(chunks)} chunks from {file_path.name}")

                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")

        if documents:
            self.vector_store.add_documents(documents)
            # Save vector store
            self.vector_store.save(Path("vector_store"))
            logger.info(f"Loaded {len(documents)} total document chunks")
        else:
            logger.warning("No documents loaded")

    def _split_text(self, text: str) -> list[str]:
        """Split text into chunks.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        chunk_size = self.settings.chunk_size
        chunk_overlap = self.settings.chunk_overlap

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for delimiter in [".", "!", "?", "\n\n"]:
                    last_delimiter = chunk.rfind(delimiter)
                    if last_delimiter != -1:
                        chunk = chunk[:last_delimiter + 1]
                        end = start + len(chunk)
                        break

            chunks.append(chunk.strip())
            start = end - chunk_overlap

        return [c for c in chunks if c]  # Filter empty chunks

    def search(self, query: str, top_k: Optional[int] = None) -> list[tuple[str, float, dict]]:
        """Search knowledge base for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return (uses config default if None)

        Returns:
            List of tuples (content, score, metadata)
        """
        if top_k is None:
            top_k = self.settings.top_k_results

        results = self.vector_store.search(query, top_k)

        return [(doc.content, score, doc.metadata) for doc, score in results]

    def get_context(self, query: str, top_k: Optional[int] = None) -> str:
        """Get formatted context for a query.

        Args:
            query: Search query
            top_k: Number of results to include

        Returns:
            Formatted context string
        """
        results = self.search(query, top_k)

        if not results:
            return "لا توجد معلومات متاحة في قاعدة المعرفة."

        context_parts = []
        for i, (content, score, metadata) in enumerate(results, 1):
            source = metadata.get("source", "Unknown")
            context_parts.append(f"[{i}] من {Path(source).name}:\n{content}")

        return "\n\n".join(context_parts)
