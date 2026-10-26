"""
Embeddings and FAISS vector store for RAG.

Supports two backends:
  1. Ollama embedding models — auto-detects /api/embed (v0.3+) or /api/embeddings (older)
     Falls back to sentence-transformers if the model is not found in Ollama.
  2. sentence-transformers (any HuggingFace model) — always available offline

Auto-fallback logic:
  - If embedding model name is in OLLAMA_EMBED_MODELS → try Ollama first
  - If Ollama returns 404 (model not pulled) → fall back to sentence-transformers
    using 'all-MiniLM-L6-v2' which is bundled with the sentence-transformers package
  - Sentence-transformers is always the ultimate fallback

Uses small batches to avoid Ollama timeouts.
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import faiss

from core.models import FunctionUnit
from config.settings import settings

logger = logging.getLogger(__name__)

# Model names that route to Ollama's local embedding API
OLLAMA_EMBED_MODELS = {
    "nomic-embed-text",
    "nomic-embed-text:latest",
    "mxbai-embed-large",
    "mxbai-embed-large:latest",
    "all-minilm",
    "all-minilm:latest",
    "snowflake-arctic-embed",
    "snowflake-arctic-embed:latest",
    "bge-m3",
}

# Fallback sentence-transformers model — small, fast, always available
FALLBACK_ST_MODEL = "all-MiniLM-L6-v2"

OLLAMA_BATCH_SIZE = 16
OLLAMA_BASE_URL = "http://localhost:11434"


@dataclass
class ChunkMetadata:
    chunk_id: str
    file_path: str
    class_name: Optional[str]
    function_name: str
    start_line: int
    end_line: int
    source_code: str


@dataclass
class RetrievedChunk:
    metadata: ChunkMetadata
    score: float  # cosine similarity (higher = more similar)


def _is_ollama_model(model_name: str) -> bool:
    return model_name.lower() in OLLAMA_EMBED_MODELS


def _probe_ollama_endpoint() -> Optional[str]:
    """
    Detect which Ollama embedding endpoint is available.
    Ollama ≥0.3: /api/embed (batch, 'input' key)
    Ollama <0.3:  /api/embeddings (single, 'prompt' key)
    Returns the working endpoint path, or None if neither works.
    """
    import httpx
    # Try new endpoint first
    try:
        r = httpx.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": "dummy_probe", "input": ["test"]},
            timeout=5.0,
        )
        # 404 with "model not found" means endpoint exists but model isn't pulled
        # 404 with "not found" (no model mention) means endpoint doesn't exist
        if r.status_code == 200:
            return "/api/embed"
        body = r.text.lower()
        if r.status_code == 404 and "not found" in body and "model" in body:
            return "/api/embed"   # endpoint exists, model missing
    except Exception:
        pass

    # Try old endpoint
    try:
        r = httpx.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": "dummy_probe", "prompt": "test"},
            timeout=5.0,
        )
        if r.status_code in (200, 404):
            body = r.text.lower()
            if "model" in body or r.status_code == 200:
                return "/api/embeddings"
    except Exception:
        pass

    return None


# Cache the probed endpoint so we don't re-probe on every batch
_OLLAMA_ENDPOINT_CACHE: Optional[str] = None


def _get_ollama_endpoint() -> Optional[str]:
    global _OLLAMA_ENDPOINT_CACHE
    if _OLLAMA_ENDPOINT_CACHE is None:
        _OLLAMA_ENDPOINT_CACHE = _probe_ollama_endpoint()
    return _OLLAMA_ENDPOINT_CACHE


def _embed_single_with_ollama(text: str, model_name: str, endpoint: str) -> Optional[list]:
    """Embed one text using the old /api/embeddings endpoint."""
    import httpx
    try:
        r = httpx.post(
            f"{OLLAMA_BASE_URL}{endpoint}",
            json={"model": model_name, "prompt": text},
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("embedding", [])
    except Exception as exc:
        logger.warning("Ollama single embed failed: %s", exc)
        return None


def _embed_batch_with_ollama_new(texts: List[str], model_name: str) -> Optional[np.ndarray]:
    """Embed using /api/embed (Ollama ≥0.3, batch input)."""
    import httpx
    all_vectors: List[List[float]] = []
    for i in range(0, len(texts), OLLAMA_BATCH_SIZE):
        batch = [t[:2000] for t in texts[i: i + OLLAMA_BATCH_SIZE]]
        for attempt in range(3):
            try:
                r = httpx.post(
                    f"{OLLAMA_BASE_URL}/api/embed",
                    json={"model": model_name, "input": batch},
                    timeout=120.0,
                )
                r.raise_for_status()
                data = r.json()
                embeddings = data.get("embeddings", [])
                all_vectors.extend(embeddings)
                break
            except Exception as exc:
                logger.warning("Ollama /api/embed batch %d attempt %d: %s", i, attempt, exc)
                if attempt == 2:
                    raise
                time.sleep(1)
    return _normalize(np.array(all_vectors, dtype=np.float32))


def _embed_batch_with_ollama_old(texts: List[str], model_name: str) -> Optional[np.ndarray]:
    """Embed using /api/embeddings (Ollama <0.3, one request per text)."""
    import httpx
    all_vectors: List[List[float]] = []
    for i, text in enumerate(texts):
        for attempt in range(3):
            try:
                r = httpx.post(
                    f"{OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": model_name, "prompt": text[:2000]},
                    timeout=30.0,
                )
                r.raise_for_status()
                data = r.json()
                vec = data.get("embedding", [])
                all_vectors.append(vec)
                break
            except Exception as exc:
                logger.warning("Ollama /api/embeddings item %d attempt %d: %s", i, attempt, exc)
                if attempt == 2:
                    raise
                time.sleep(0.5)
        if i % 20 == 0 and i > 0:
            logger.debug("Embedded %d/%d", i, len(texts))
    return _normalize(np.array(all_vectors, dtype=np.float32))


def _embed_with_ollama(texts: List[str], model_name: str) -> Optional[np.ndarray]:
    """
    Try Ollama embedding.  Returns None if the model is not available
    so the caller can fall back to sentence-transformers.
    """
    import httpx

    # First verify the model is pulled
    try:
        r = httpx.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": model_name, "input": [texts[0][:200]]},
            timeout=15.0,
        )
        if r.status_code == 404:
            body = r.text.lower()
            if "not found" in body:
                logger.warning(
                    "Ollama model %r not found (not pulled). Falling back to sentence-transformers.",
                    model_name,
                )
                return None
        if r.status_code == 200:
            # New endpoint works
            logger.info("Using Ollama /api/embed for %s", model_name)
            return _embed_batch_with_ollama_new(texts, model_name)
    except Exception as exc:
        logger.warning("Ollama /api/embed probe failed: %s", exc)

    # Try old endpoint
    try:
        r = httpx.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": model_name, "prompt": texts[0][:200]},
            timeout=15.0,
        )
        if r.status_code == 404:
            body = r.text.lower()
            if "not found" in body:
                logger.warning(
                    "Ollama model %r not found on /api/embeddings either. Falling back.",
                    model_name,
                )
                return None
        if r.status_code == 200:
            logger.info("Using Ollama /api/embeddings for %s", model_name)
            return _embed_batch_with_ollama_old(texts, model_name)
    except Exception as exc:
        logger.warning("Ollama /api/embeddings probe failed: %s", exc)

    return None


def _embed_with_sentence_transformers(texts: List[str], model_name: str) -> np.ndarray:
    """Embed with sentence-transformers. Lazy-loads model on first call."""
    from sentence_transformers import SentenceTransformer
    logger.info("Loading sentence-transformers model: %s", model_name)
    model = SentenceTransformer(model_name)
    vecs = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return vecs.astype(np.float32)


def _normalize(arr: np.ndarray) -> np.ndarray:
    """L2-normalise rows for cosine similarity via inner-product."""
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    return (arr / norms).astype(np.float32)


class CodeVectorStore:
    """
    FAISS-backed vector store for function-level code chunks.

    Embedding backend selection:
      1. If model name is in OLLAMA_EMBED_MODELS and Ollama is reachable:
         use Ollama (new /api/embed endpoint, fallback to old /api/embeddings).
      2. If Ollama model is not pulled → automatic fallback to sentence-transformers
         with FALLBACK_ST_MODEL.
      3. For any non-Ollama model name → sentence-transformers directly.

    The fallback model used is recorded in self.actual_model_used for
    transparent reporting in the dashboard.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.embedding_model
        self._index: Optional[faiss.IndexFlatIP] = None
        self._metadata: List[ChunkMetadata] = []
        self._dim: int = 0
        self._use_ollama = _is_ollama_model(self.model_name)
        self.actual_model_used: str = self.model_name
        self.backend_used: str = "pending"
        logger.info(
            "CodeVectorStore: configured model=%s ollama_preferred=%s",
            self.model_name, self._use_ollama,
        )

    def _embed(self, texts: List[str]) -> np.ndarray:
        if self._use_ollama:
            result = _embed_with_ollama(texts, self.model_name)
            if result is not None:
                self.backend_used = f"ollama/{self.model_name}"
                return result
            # Ollama model not available → fall back
            logger.warning(
                "Ollama model %r not available. Using sentence-transformers/%s as fallback.",
                self.model_name, FALLBACK_ST_MODEL,
            )
            self.actual_model_used = FALLBACK_ST_MODEL
            self.backend_used = f"sentence-transformers/{FALLBACK_ST_MODEL} (fallback)"

        st_model = FALLBACK_ST_MODEL if self._use_ollama else self.model_name
        result = _embed_with_sentence_transformers(texts, st_model)
        if not self._use_ollama:
            self.actual_model_used = st_model
            self.backend_used = f"sentence-transformers/{st_model}"
        return result

    def build(self, functions: List[FunctionUnit]) -> None:
        """Build FAISS index. Each function = one chunk."""
        if not functions:
            logger.warning("No functions to index.")
            return

        start = time.time()
        texts: List[str] = []
        metas: List[ChunkMetadata] = []

        for unit in functions:
            embed_text = (
                f"File: {unit.file_path}\n"
                f"Function: {unit.qualified_name}\n"
                f"{unit.source_code[:1500]}"
            )
            texts.append(embed_text)
            metas.append(ChunkMetadata(
                chunk_id=unit.chunk_id,
                file_path=unit.file_path,
                class_name=unit.class_name,
                function_name=unit.function_name,
                start_line=unit.start_line,
                end_line=unit.end_line,
                source_code=unit.source_code,
            ))

        logger.info("Embedding %d chunks (model: %s)...", len(texts), self.model_name)
        vectors = self._embed(texts)
        self._dim = vectors.shape[1]

        self._index = faiss.IndexFlatIP(self._dim)
        self._index.add(vectors)
        self._metadata = metas

        elapsed = (time.time() - start) * 1000
        logger.info(
            "FAISS index built: %d chunks, dim=%d, backend=%s, %.1fs",
            len(metas), self._dim, self.backend_used, elapsed / 1000,
        )

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedChunk]:
        """Retrieve top-K most similar chunks for a query string."""
        if self._index is None or not self._metadata:
            raise RuntimeError("Vector store not built. Call build() first.")

        query_vec = self._embed([query[:2000]])
        scores, indices = self._index.search(query_vec, min(top_k, len(self._metadata)))

        results: List[RetrievedChunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            results.append(RetrievedChunk(
                metadata=self._metadata[idx],
                score=float(score),
            ))
        return results

    @property
    def size(self) -> int:
        return len(self._metadata)
