"""Local MAP extraction agent using Ollama + Phi-3 Mini.

Replaces Groq calls with local Ollama calls.
Run from project root:
    python -m agents.extraction_agent

Before running:
    ollama pull phi3:mini
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, Iterable, List, Optional

import ollama
import requests
from sentence_transformers import SentenceTransformer

try:
    from .prompts import MAP_EXTRACTION_PROMPT
    from .mpi_engine import score_map
except ImportError:  # allows python agents/extraction_agent.py too
    from prompts import MAP_EXTRACTION_PROMPT
    from mpi_engine import score_map

MODEL_NAME = os.getenv("OLLAMA_MODEL", "phi3:mini")
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def chunk_text(text: str, max_chars: int = 3500, overlap: int = 300) -> List[str]:
    """Split long circular text into overlapping chunks."""
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return [clean]

    chunks = []
    start = 0
    while start < len(clean):
        end = min(start + max_chars, len(clean))
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = max(0, end - overlap)
    return chunks


def extract_json_from_response(content: str) -> Dict[str, Any]:
    """Parse JSON even if model accidentally adds small extra text."""
    content = content.strip()
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            return parsed[0]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model response: {content[:300]}")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON was not an object.")
    return parsed


def validate_map_fields(map_obj: Dict[str, Any]) -> Dict[str, Any]:
    required_keys = [
        "obligation_text",
        "measurable_condition",
        "deadline",
        "penalty_exposure",
        "evidence_required",
        "regulatory_reference",
        "map_type",
    ]
    cleaned = {}
    for key in required_keys:
        value = map_obj.get(key, "Not specified")
        if value is None or str(value).strip() == "":
            value = "Not specified"
        cleaned[key] = str(value).strip()

    valid_types = {"KYC_AML", "Cybersecurity", "Capital_Adequacy", "Grievance", "FEMA", "General_Compliance"}
    if cleaned["map_type"] not in valid_types:
        cleaned["map_type"] = "General_Compliance"

    cleaned["id"] = map_obj.get("id") or f"map_{uuid.uuid4().hex[:8]}"
    return cleaned


def call_ollama_for_map(chunk: str) -> Dict[str, Any]:
    """Call local Phi-3 Mini via Ollama and return one MAP object."""
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": MAP_EXTRACTION_PROMPT},
            {"role": "user", "content": chunk},
        ],
        options={"temperature": 0.1},
    )
    content = response["message"]["content"]
    raw_map = extract_json_from_response(content)
    return validate_map_fields(raw_map)


def deduplicate_maps(maps: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate obligations across chunks using normalized obligation text."""
    seen = set()
    unique = []
    for item in maps:
        key = re.sub(r"\W+", "", item.get("obligation_text", "").lower())[:180]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def post_map_to_backend(map_obj: Dict[str, Any], backend_url: str = "http://localhost:8000") -> Optional[Dict[str, Any]]:
    """POST one MAP to backend if Member A's API is running."""
    url = backend_url.rstrip("/") + "/maps"
    try:
        response = requests.post(url, json=map_obj, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"Backend POST skipped/failed: {exc}")
        return None


def add_embedding_fields(map_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Generate local embedding for obligation_text and attach it.

    If your backend stores embeddings separately, remove this field before POSTing.
    """
    model = get_embedding_model()
    embedding = model.encode(map_obj["obligation_text"]).tolist()
    enriched = dict(map_obj)
    enriched["obligation_embedding"] = embedding
    return enriched


def extract_maps_from_text(
    circular_text: str,
    authority: str = "RBI",
    backend_url: Optional[str] = None,
    attach_embeddings: bool = False,
) -> List[Dict[str, Any]]:
    """Extract, score, optionally embed, and optionally post MAPs."""
    extracted = []
    for chunk in chunk_text(circular_text):
        try:
            map_obj = call_ollama_for_map(chunk)
            scored_map = score_map(map_obj, authority=authority)
            if attach_embeddings:
                scored_map = add_embedding_fields(scored_map)
            extracted.append(scored_map)
        except Exception as exc:
            print(f"Extraction failed for chunk: {exc}")

    unique_maps = deduplicate_maps(extracted)

    if backend_url:
        for map_obj in unique_maps:
            post_map_to_backend(map_obj, backend_url=backend_url)

    return unique_maps


if __name__ == "__main__":
    sample_circular = """
    RBI Circular: Customer Due Diligence and KYC Update Requirements.
    Banks shall ensure that all customer KYC records are updated within 30 days from the date of this circular.
    Banks must maintain documentary evidence of KYC update completion and submit compliance confirmation
    to the Compliance Department. Failure to comply may attract supervisory action under applicable RBI guidelines.
    """

    maps = extract_maps_from_text(sample_circular, authority="RBI", attach_embeddings=False)
    print(json.dumps(maps, indent=2))
