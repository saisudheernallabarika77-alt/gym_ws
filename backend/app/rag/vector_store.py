"""
Fitora RAG - Vector Store

ChromaDB persistent collection over the gym corpus, embedded locally with
sentence-transformers (all-MiniLM-L6-v2: 384-dim, fast, CPU-friendly, free).

The store is a singleton - the embedding model is loaded once per process.
"""
from __future__ import annotations
import json, logging, os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# Once the model is in the local HF cache, skip the network round-trips
# sentence-transformers makes on every load - they add ~10s to each boot.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_IMPL", "chromadb.telemetry.product.NoopProductTelemetryClient")

log = logging.getLogger(__name__)

EMBED_MODEL = "all-MiniLM-L6-v2"
COLLECTION = "fitora_gyms"

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
CHROMA_DIR = BACKEND_DIR / "chroma_db"
GYMS_JSON = PROJECT_DIR / "data" / "processed" / "gyms.json"


class GymVectorStore:
    _instance: "GymVectorStore | None" = None

    def __init__(self) -> None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine", "description": "Fitora gym corpus"},
        )

    # ------------------------------------------------------------- singleton
    @classmethod
    def get(cls) -> "GymVectorStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------- indexing
    def index_gyms(self, gyms: list[dict[str, Any]], *, reset: bool = False) -> int:
        """Embed and upsert gym documents. `reset=True` rebuilds from scratch."""
        from .document_builder import build_document, build_metadata

        if reset:
            try:
                self.client.delete_collection(COLLECTION)
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION,
                embedding_function=self.embed_fn,
                metadata={"hnsw:space": "cosine", "description": "Fitora gym corpus"},
            )

        ids = [g["gym_id"] for g in gyms]
        docs = [build_document(g) for g in gyms]
        metas = [build_metadata(g) for g in gyms]

        BATCH = 64
        for i in range(0, len(ids), BATCH):
            self.collection.upsert(
                ids=ids[i:i + BATCH],
                documents=docs[i:i + BATCH],
                metadatas=metas[i:i + BATCH],
            )
            log.info("indexed %d/%d", min(i + BATCH, len(ids)), len(ids))
        return len(ids)

    def index_one(self, gym: dict[str, Any]) -> None:
        """Upsert a single gym - used when a gym owner saves their profile."""
        from .document_builder import build_document, build_metadata
        self.collection.upsert(
            ids=[gym["gym_id"]],
            documents=[build_document(gym)],
            metadatas=[build_metadata(gym)],
        )

    def remove(self, gym_id: str) -> None:
        self.collection.delete(ids=[gym_id])

    # ------------------------------------------------------------- querying
    def search(
        self,
        query: str,
        *,
        where: dict[str, Any] | None = None,
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        res = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out: list[dict[str, Any]] = []
        for i, gid in enumerate(res["ids"][0]):
            dist = res["distances"][0][i]
            out.append({
                "gym_id": gid,
                "document": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": dist,
                "score": round(1.0 - dist, 4),   # cosine similarity
            })
        return out

    def count(self) -> int:
        return self.collection.count()


def load_gyms_json() -> list[dict[str, Any]]:
    return json.loads(GYMS_JSON.read_text())
