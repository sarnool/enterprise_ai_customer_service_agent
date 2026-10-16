"""
Vector knowledge base implementation.
"""
from pathlib import Path
from typing import List, Dict, Any
import pickle
import faiss
import numpy as np
from src.knowledge.embeddings import EmbeddingGenerator
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class KnowledgeBase:
    """Manage vector knowledge base with FAISS."""

    def __init__(self):
        self.embedding_generator = EmbeddingGenerator()
        self.index = None
        self.documents = []
        self.dimension = 1536  # OpenAI embedding dimension

    def load_documents(self, knowledge_base_path: str) -> List[Dict[str, Any]]:
        """
        Load documents from knowledge base directory.

        Every .md file under the directory is split into 1000-character
        chunks with 200 characters of overlap. Each chunk's category is the
        name of the folder its file is in.

        Args:
            knowledge_base_path: Path to knowledge base directory

        Returns:
            List of document chunks with metadata
        """
        docs = []
        kb_path = Path(knowledge_base_path)

        for md_file in sorted(kb_path.rglob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            category = md_file.parent.name
            for i, chunk in enumerate(self._chunk_text(content, chunk_size=1000, overlap=200)):
                docs.append({
                    "content": chunk,
                    "source": md_file.name,
                    "category": category,
                    "chunk_id": i
                })

        logger.info(f"Loaded {len(docs)} chunks from {kb_path}")
        return docs

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split text into overlapping chunks. Provided - not part of this activity."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return chunks

    def build_index(self, documents: List[Dict[str, Any]]):
        """
        Build FAISS index from documents.
        """
        self.documents = documents
        texts = [doc["content"] for doc in documents]

        embeddings = self.embedding_generator.generate_embeddings(texts)
        embeddings_array = np.array(embeddings).astype('float32')

        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings_array)
        logger.info(f"Built FAISS index with {self.index.ntotal} vectors")

    def save_index(self, path: str):
        """
        Save FAISS index to disk.

        Writes the index to `{path}.index` and the documents to `{path}.docs`.
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, f"{path}.index")
        with open(f"{path}.docs", "wb") as f:
            pickle.dump(self.documents, f)

    def load_index(self, path: str):
        """
        Load FAISS index from disk.

        Reads `{path}.index` and `{path}.docs`. Exceptions propagate if the
        files don't exist yet - callers are expected to handle that case.
        """
        self.index = faiss.read_index(f"{path}.index")
        with open(f"{path}.docs", "rb") as f:
            self.documents = pickle.load(f)
