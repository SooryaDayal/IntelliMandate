"""
IntelliMandate v3 — Local Vector Store
File: agents/vector_store.py

June 16 Member B Task B-3-1
ChromaDB + sentence-transformers, fully local.
Collection: intellimandate_canara_maps

Run:
    python -m agents.vector_store
"""

from __future__ import annotations

from typing import Any, Dict, List

import chromadb
from sentence_transformers import SentenceTransformer

COLLECTION_NAME = "intellimandate_canara_maps"
CHROMA_PATH = "agents/chroma_db"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def initialize_store() -> chromadb.Collection:
    """Create/open the local ChromaDB collection for Canara Bank MAPs."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(name=COLLECTION_NAME)


def add_map_embedding(map_id: str, obligation_text: str, measurable_condition: str) -> None:
    """Add or update one MAP embedding in ChromaDB."""
    if not map_id:
        raise ValueError("map_id is required")

    obligation_text = (obligation_text or "").strip()
    measurable_condition = (measurable_condition or "").strip()

    if not obligation_text and not measurable_condition:
        raise ValueError("obligation_text or measurable_condition is required")

    document = f"Obligation: {obligation_text}\nMeasurable condition: {measurable_condition}".strip()
    embedding = _get_model().encode([document])[0].tolist()
    collection = initialize_store()

    collection.upsert(
        ids=[str(map_id)],
        documents=[document],
        embeddings=[embedding],
        metadatas=[
            {
                "map_id": str(map_id),
                "obligation_text": obligation_text[:500],
                "measurable_condition": measurable_condition[:500],
            }
        ],
    )


def search_similar_maps(query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """Semantic search over stored MAPs."""
    query_text = (query_text or "").strip()
    if not query_text:
        return []

    collection = initialize_store()
    if collection.count() == 0:
        return []

    query_embedding = _get_model().encode([query_text])[0].tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)

    output: List[Dict[str, Any]] = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for idx, map_id in enumerate(ids):
        distance = distances[idx] if idx < len(distances) else None
        similarity = None if distance is None else round(1 - float(distance), 4)
        output.append(
            {
                "map_id": map_id,
                "document": documents[idx] if idx < len(documents) else "",
                "metadata": metadatas[idx] if idx < len(metadatas) else {},
                "distance": distance,
                "similarity": similarity,
            }
        )
    return output


def get_all_map_ids() -> List[str]:
    """Return all MAP IDs stored in the local vector database."""
    collection = initialize_store()
    data = collection.get(include=[])
    return list(data.get("ids", []))


if __name__ == "__main__":
    sample_maps = [
        (
            "map_canara_ckycr_001",
            "Upload all pending customer KYC documents to Central KYC Registry and rectify rejected CKYCR uploads within 7 days.",
            "100% of customer KYC records uploaded to CKYCR with zero rejected uploads pending beyond 7 days.",
        ),
        (
            "map_canara_psl_002",
            "Achieve prescribed priority sector lending targets as per RBI Master Direction on Priority Sector Lending.",
            "Priority sector lending constitutes minimum required share of Adjusted Net Bank Credit by year end.",
        ),
        (
            "map_canara_cic_003",
            "Rectify rejected Credit Information Companies data and upload corrected records within 7 days.",
            "Zero CIC rejection reports pending beyond 7 days in the data upload system.",
        ),
        (
            "map_canara_aml_004",
            "Report suspicious transactions to FIU-IND within the prescribed reporting window under PMLA.",
            "100% of suspicious transactions reported to FIU-IND within required timeline.",
        ),
        (
            "map_canara_bsbda_005",
            "Ensure eligible customers are offered Basic Savings Bank Deposit Account without minimum balance requirement.",
            "Zero instances of BSBDA denial or minimum balance imposition at branches.",
        ),
    ]

    for map_id, obligation, condition in sample_maps:
        add_map_embedding(map_id, obligation, condition)

    print("Vector store initialized.")
    print(f"Collection name: {COLLECTION_NAME}")
    print(f"Stored MAP IDs: {get_all_map_ids()}")

    print("\nSearch: CKYCR compliance")
    for item in search_similar_maps("CKYCR compliance", n_results=3):
        print(item)

    print("\nSearch: priority sector lending")
    for item in search_similar_maps("priority sector lending", n_results=3):
        print(item)
