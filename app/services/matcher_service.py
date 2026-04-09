"""Matcher service for embedding similarity + reasoning outputs."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class EmbeddingClient(Protocol):
    """Embeddings provider contract."""

    def embed(self, text: str) -> list[float]:
        """Return a dense vector for the provided text."""
        ...


@dataclass(slots=True)
class MatchResult:
    """Structured match output for decision and UX surfaces."""

    match_score: float
    strengths: list[str]
    gaps: list[str]


class ReasoningClient(Protocol):
    """Reasoning provider contract (LLM or heuristic engine)."""

    def summarize_fit(self, *, jd_text: str, resume_text: str, similarity_score: float) -> tuple[list[str], list[str]]:
        """Return strengths and gaps lists."""
        ...


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not left or not right:
        return 0.0

    length = min(len(left), len(right))
    left_vec = left[:length]
    right_vec = right[:length]

    dot = sum(a * b for a, b in zip(left_vec, right_vec, strict=True))
    left_norm = math.sqrt(sum(v * v for v in left_vec))
    right_norm = math.sqrt(sum(v * v for v in right_vec))

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    return dot / (left_norm * right_norm)


class MatcherService:
    """Runs embedding similarity and adds reasoning-based strengths/gaps."""

    def __init__(
        self,
        *,
        embedding_client: EmbeddingClient,
        reasoning_client: ReasoningClient,
    ) -> None:
        self.embedding_client = embedding_client
        self.reasoning_client = reasoning_client

    def match(
        self,
        *,
        jd_text: str,
        resume_text: str,
        job_id: str | None = None,
        user_id: str | None = None,
        url: str | None = None,
    ) -> MatchResult:
        """Return match score plus strengths and gap insights."""
        jd_embedding = self.embedding_client.embed(jd_text)
        resume_embedding = self.embedding_client.embed(resume_text)
        similarity = max(0.0, min(1.0, cosine_similarity(jd_embedding, resume_embedding)))

        strengths, gaps = self.reasoning_client.summarize_fit(
            jd_text=jd_text,
            resume_text=resume_text,
            similarity_score=similarity,
        )

        return MatchResult(
            match_score=similarity,
            strengths=strengths,
            gaps=gaps,
        )
