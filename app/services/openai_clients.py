"""OpenAI-backed service clients for embeddings, reasoning, and outreach generation."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_REASONING_MODEL = "gpt-4o-mini"
DEFAULT_OUTREACH_MODEL = "gpt-4o-mini"


def _coerce_str_list(value: Any, *, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if cleaned:
            return cleaned[:5]
    return fallback


class OpenAIEmbeddingClient:
    """Embedding client adapter used by MatcherService."""

    def __init__(self, *, api_key: str, model: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model, input=text)
        return response.data[0].embedding


class OpenAIReasoningClient:
    """Reasoning client adapter used by MatcherService."""

    def __init__(self, *, api_key: str, model: str = DEFAULT_REASONING_MODEL) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def summarize_fit(self, *, jd_text: str, resume_text: str, similarity_score: float) -> tuple[list[str], list[str]]:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a hiring analyst. Return strict JSON with keys "
                        "'strengths' and 'gaps', each as a list of short bullet strings."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Job description:\n{jd_text}\n\n"
                        f"Candidate resume:\n{resume_text}\n\n"
                        f"Similarity score: {similarity_score:.4f}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("reasoning_client_non_json_response content=%r", content[:300])
            payload = {}

        strengths = _coerce_str_list(
            payload.get("strengths"),
            fallback=["Experience appears relevant to key job requirements."],
        )
        gaps = _coerce_str_list(
            payload.get("gaps"),
            fallback=["Additional role-specific depth may be required."],
        )
        return strengths, gaps


class OpenAIOutreachClient:
    """Outreach generation client adapter used by OutreachService."""

    def __init__(self, *, api_key: str, model: str = DEFAULT_OUTREACH_MODEL) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.4,
            messages=[
                {"role": "system", "content": "Write concise, professional referral outreach messages."},
                {"role": "user", "content": prompt},
            ],
        )
        message = response.choices[0].message.content
        if not message:
            raise RuntimeError("OpenAI outreach response was empty")
        return message.strip()
