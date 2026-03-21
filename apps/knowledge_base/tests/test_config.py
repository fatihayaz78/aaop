"""Tests for Knowledge Base config."""

from __future__ import annotations

from apps.knowledge_base.config import KnowledgeBaseConfig


def test_defaults():
    cfg = KnowledgeBaseConfig()
    assert cfg.chunk_size_tokens == 500
    assert cfg.chunk_overlap_tokens == 50
    assert cfg.embedding_model == "all-MiniLM-L6-v2"
    assert "incidents" in cfg.collections
    assert "runbooks" in cfg.collections
    assert "platform" in cfg.collections
    assert cfg.search_top_k == 5


def test_custom():
    cfg = KnowledgeBaseConfig(chunk_size_tokens=300, search_top_k=10)
    assert cfg.chunk_size_tokens == 300
    assert cfg.search_top_k == 10
