"""Complete FAISS knowledge base - REFERENCE SOLUTION"""
from pathlib import Path
from typing import List, Dict, Any
import faiss
import numpy as np
import pickle
from src.knowledge.embeddings import EmbeddingGenerator
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class KnowledgeBase:
    def __init__(self):
        self.embedding_generator = EmbeddingGenerator()
        self.index = None
        self.documents = []
        self.dimension = 1536
    
    def load_documents(self, knowledge_base_path: str) -> List[Dict[str, Any]]:
        """Load and chunk documents."""
        docs = []
        kb_path = Path(knowledge_base_path)
        
        for md_file in kb_path.rglob("*.md"):
            content = md_file.read_text(encoding='utf-8')
            category = md_file.parent.name
            
            # Chunk document (simple chunking)
            chunks = self._chunk_text(content, chunk_size=1000, overlap=200)
            
            for i, chunk in enumerate(chunks):
                docs.append({
                    "content": chunk,
                    "source": md_file.name,
                    "category": category,
                    "chunk_id": i
                })
        
        return docs
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Simple text chunking."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return chunks
    
    def build_index(self, documents: List[Dict[str, Any]]):
        """Build FAISS index."""
        self.documents = documents
        
        # Generate embeddings
        texts = [doc["content"] for doc in documents]
        embeddings = self.embedding_generator.generate_embeddings(texts)
        
        # Create FAISS index
        embeddings_array = np.array(embeddings).astype('float32')
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings_array)
        
        logger.info(f"Built index with {len(documents)} documents")
    
    def save_index(self, path: str):
        """Save index and documents."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, f"{path}.index")
        with open(f"{path}.docs", 'wb') as f:
            pickle.dump(self.documents, f)
    
    def load_index(self, path: str):
        """Load index and documents."""
        self.index = faiss.read_index(f"{path}.index")
        with open(f"{path}.docs", 'rb') as f:
            self.documents = pickle.load(f)
