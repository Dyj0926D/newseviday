import hashlib
import math
from collections.abc import Sequence
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    @property
    def model(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding_dimension_mismatch")
    return sum(a * b for a, b in zip(left, right, strict=True))


class HashingEmbedder:
    """A deterministic, dependency-free dense baseline for CI and rollback tests."""

    def __init__(self, dimensions: int = 384, model: str = "hashing-chargram-v1") -> None:
        if dimensions < 32:
            raise ValueError("embedding_dimensions_too_small")
        self._dimensions = dimensions
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            normalized = " ".join(text.casefold().split())
            features = [
                normalized[index : index + 3]
                for index in range(max(1, len(normalized) - 2))
            ]
            vector = [0.0] * self.dimensions
            for feature in features:
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                slot = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[slot] += sign
            vectors.append(_normalize(vector))
        return vectors


class OpenAICompatibleEmbedder:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        dimensions: int,
        api_key: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("embedding_base_url_must_be_https")
        self.base_url = base_url.rstrip("/")
        self._model = model
        self._dimensions = dimensions
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = httpx.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json={"model": self.model, "input": list(texts)},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ValueError("invalid_embedding_response")
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        vectors = [item.get("embedding") for item in ordered]
        if len(vectors) != len(texts) or any(
            not isinstance(vector, list) or len(vector) != self.dimensions for vector in vectors
        ):
            raise ValueError("invalid_embedding_dimensions")
        return [[float(value) for value in vector] for vector in vectors]
