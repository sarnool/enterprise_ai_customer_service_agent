"""Test suite for knowledge base and retrieval."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import faiss
from src.knowledge.knowledge_base import KnowledgeBase
from src.knowledge.retriever import Retriever

DIMENSION = 4

def fake_embedding(text):
    """Deterministic stand-in for an OpenAI embedding."""
    rng = np.random.default_rng(abs(hash(text)) % (2**32))
    return rng.random(DIMENSION).tolist()

@pytest.fixture
def kb(monkeypatch):
    """KnowledgeBase with a fake embedding generator - no API calls."""
    generator = MagicMock()
    generator.generate_embedding.side_effect = fake_embedding
    generator.generate_embeddings.side_effect = lambda texts: [fake_embedding(t) for t in texts]
    monkeypatch.setattr("src.knowledge.knowledge_base.EmbeddingGenerator", lambda: generator)
    monkeypatch.setattr("src.knowledge.retriever.EmbeddingGenerator", lambda: generator)
    kb = KnowledgeBase()
    kb.dimension = DIMENSION
    return kb

def make_docs(*contents):
    return [{"content": c, "source": f"doc{i}.md", "category": "test", "chunk_id": 0}
            for i, c in enumerate(contents)]

def test_knowledge_base_structure():
    """Test that knowledge base directory exists."""
    kb_path = Path("data/knowledge_base")
    assert kb_path.exists()
    assert (kb_path / "accounts").exists()
    assert (kb_path / "cards").exists()
    assert (kb_path / "loans").exists()
    assert (kb_path / "operations").exists()

def test_load_documents_from_real_knowledge_base(kb):
    docs = kb.load_documents("data/knowledge_base")
    assert docs
    assert {d["category"] for d in docs} == {"accounts", "cards", "loans", "operations"}
    for doc in docs:
        assert set(doc) == {"content", "source", "category", "chunk_id"}
        assert doc["source"].endswith(".md")
        assert len(doc["content"]) <= 1000

def test_load_documents_chunks_with_overlap(kb, tmp_path):
    (tmp_path / "cards").mkdir()
    text = "".join(str(i % 10) for i in range(2500))
    (tmp_path / "cards" / "long.md").write_text(text, encoding="utf-8")

    docs = kb.load_documents(str(tmp_path))
    assert [d["chunk_id"] for d in docs] == list(range(len(docs)))
    assert all(d["source"] == "long.md" and d["category"] == "cards" for d in docs)
    # Each chunk starts with the last 200 characters of the previous one.
    assert docs[1]["content"][:200] == docs[0]["content"][-200:]

def test_load_documents_ignores_non_markdown(kb, tmp_path):
    (tmp_path / "notes.txt").write_text("not markdown", encoding="utf-8")
    assert kb.load_documents(str(tmp_path)) == []

def test_build_index(kb):
    docs = make_docs("alpha", "beta", "gamma")
    kb.build_index(docs)
    assert kb.index.ntotal == 3
    assert kb.documents == docs

def test_save_and_load_index(kb, tmp_path):
    docs = make_docs("alpha", "beta")
    kb.build_index(docs)
    path = str(tmp_path / "nested" / "kb_index")
    kb.save_index(path)

    loaded = KnowledgeBase()
    loaded.load_index(path)
    assert loaded.index.ntotal == 2
    assert loaded.documents == docs

def test_load_index_missing_files_raises(kb, tmp_path):
    # The agent catches these exception types at startup.
    with pytest.raises((FileNotFoundError, RuntimeError, OSError)):
        kb.load_index(str(tmp_path / "missing"))

def test_retrieve_finds_matching_document(kb):
    kb.build_index(make_docs("alpha", "beta", "gamma"))
    results = Retriever(kb).retrieve("beta", top_k=3, threshold=0.0)
    assert results[0]["source"] == "doc1.md"
    assert results[0]["score"] == pytest.approx(1.0)
    assert set(results[0]) == {"content", "source", "category", "score"}

def test_retrieve_results_sorted_by_score(kb):
    kb.build_index(make_docs("alpha", "beta", "gamma"))
    scores = [r["score"] for r in Retriever(kb).retrieve("alpha", top_k=3, threshold=0.0)]
    assert scores == sorted(scores, reverse=True)

def test_retrieve_applies_threshold():
    kb = MagicMock()
    kb.index = faiss.IndexFlatL2(2)
    kb.index.add(np.array([[0, 0], [10, 10]], dtype="float32"))
    kb.documents = make_docs("near", "far")
    retriever = Retriever.__new__(Retriever)
    retriever.kb = kb
    retriever.embedding_generator = MagicMock()
    retriever.embedding_generator.generate_embedding.return_value = [0.0, 0.0]

    results = retriever.retrieve("q", top_k=2, threshold=0.4)
    assert [r["content"] for r in results] == ["near"]

def test_retrieve_skips_faiss_padding(kb):
    # Asking for more results than there are vectors makes FAISS pad with -1.
    kb.build_index(make_docs("alpha", "beta"))
    results = Retriever(kb).retrieve("alpha", top_k=5, threshold=0.0)
    assert len(results) == 2

def test_retrieve_without_index_returns_empty(kb):
    assert Retriever(kb).retrieve("anything") == []
