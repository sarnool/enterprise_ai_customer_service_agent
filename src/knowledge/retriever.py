"""
RAG retrieval implementation.
"""
from typing import List, Dict, Any
import numpy as np
from src.knowledge.knowledge_base import KnowledgeBase
from src.knowledge.embeddings import EmbeddingGenerator

class Retriever:
    """Semantic retrieval using FAISS."""

    def __init__(self, knowledge_base: KnowledgeBase):
        self.kb = knowledge_base
        self.embedding_generator = EmbeddingGenerator()

    def retrieve(self, query: str, top_k: int = 5, threshold: float = 0.4) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for query.

        FAISS returns L2 distances; each is converted to a similarity score
        of 1 / (1 + distance), and documents scoring below `threshold` are
        dropped.

        Args:
            query: User query
            top_k: Number of documents to retrieve
            threshold: Similarity threshold

        Returns:
            List of retrieved documents with scores
        """
        if not self.kb.index:
            return []

        query_embedding = self.embedding_generator.generate_embedding(query)
        query_vector = np.array([query_embedding]).astype('float32')
        distances, indices = self.kb.index.search(query_vector, top_k)

        results = []
        for distance, idx in zip(distances[0], indices[0]):
            # FAISS pads with -1 when the index holds fewer than top_k vectors.
            if idx < 0 or idx >= len(self.kb.documents):
                continue
            doc = self.kb.documents[idx]
            score = 1 / (1 + distance)
            if score >= threshold:
                results.append({
                    "content": doc["content"],
                    "source": doc["source"],
                    "category": doc["category"],
                    "score": float(score)
                })
        return results
