"""Tests for shared/clients/chroma_client.py."""

from __future__ import annotations

import pytest

from shared.clients.chroma_client import COLLECTIONS, ChromaClient


def test_connect_and_init(chroma_path: str):
    client = ChromaClient(persist_dir=chroma_path)
    client.connect()
    client.init_collections()
    # Verify collections exist
    for name in COLLECTIONS:
        coll = client.get_or_create_collection(name)
        assert coll.name == name


def test_add_and_query(chroma_path: str):
    client = ChromaClient(persist_dir=chroma_path)
    client.connect()
    client.add_documents(
        collection_name="docs",
        documents=["Akamai CDN error rate spike detected"],
        ids=["doc_001"],
        metadatas=[{"source": "log_analyzer"}],
    )
    results = client.query(collection_name="docs", query_texts=["CDN error"], n_results=1)
    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "doc_001"


def test_not_connected_raises():
    client = ChromaClient(persist_dir="/tmp/test_chroma_not_connected")
    with pytest.raises(RuntimeError, match="not connected"):
        _ = client.client
