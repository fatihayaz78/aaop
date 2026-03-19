"""ChromaDB persistent client wrapper. GCP migration: swap to Vertex AI VS adaptor."""

from __future__ import annotations

from typing import Any

import chromadb
import structlog

from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)

COLLECTIONS = ("code", "docs", "incidents")


class ChromaClient:
    def __init__(self, persist_dir: str | None = None) -> None:
        self._persist_dir = persist_dir or get_settings().chromadb_path
        self._client: chromadb.ClientAPI | None = None

    def connect(self) -> None:
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        logger.info("chroma_connected", path=self._persist_dir)

    @property
    def client(self) -> chromadb.ClientAPI:
        if self._client is None:
            msg = "ChromaClient not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._client

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        return self.client.get_or_create_collection(name=name)

    def init_collections(self) -> None:
        """Create the three standard collections: code, docs, incidents."""
        for name in COLLECTIONS:
            self.client.get_or_create_collection(name=name)
        logger.info("chroma_collections_initialized", collections=COLLECTIONS)

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        coll = self.get_or_create_collection(collection_name)
        coll.add(documents=documents, ids=ids, metadatas=metadatas)  # type: ignore[arg-type]

    def query(
        self,
        collection_name: str,
        query_texts: list[str],
        n_results: int = 5,
    ) -> dict[str, Any]:
        coll = self.get_or_create_collection(collection_name)
        return dict(coll.query(query_texts=query_texts, n_results=n_results))
