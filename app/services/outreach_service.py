"""Outreach service for generating referral-ready message drafts."""

from __future__ import annotations

from typing import Protocol


class OutreachGeneratorClient(Protocol):
    """Optional generator client contract (e.g., OpenClaw or LLM wrapper)."""

    def generate(self, prompt: str) -> str:
        """Return a generated message string."""


def build_referral_prompt(*, jd_text: str, resume_highlights: list[str]) -> str:
    """Create a compact prompt from JD text and resume highlights."""
    highlights = "\n".join(f"- {item}" for item in resume_highlights)
    return (
        "Write a concise referral message (120-180 words). "
        "Use a professional tone, reference role fit, and include a polite CTA.\n\n"
        f"Job description:\n{jd_text}\n\n"
        f"Resume highlights:\n{highlights}"
    )


class OutreachService:
    """Generates referral messages with injectable prompt + generation dependencies."""

    def __init__(
        self,
        *,
        generator_client: OutreachGeneratorClient | None = None,
        prompt_builder=build_referral_prompt,
    ) -> None:
        self.generator_client = generator_client
        self.prompt_builder = prompt_builder

    def generate_referral_message(self, *, jd_text: str, resume_highlights: list[str]) -> str:
        """Generate a referral-ready outreach draft from JD + resume highlights."""
        prompt = self.prompt_builder(jd_text=jd_text, resume_highlights=resume_highlights)

        if self.generator_client is not None:
            return self.generator_client.generate(prompt)

        return self._fallback_message(jd_text=jd_text, resume_highlights=resume_highlights)

    def _fallback_message(self, *, jd_text: str, resume_highlights: list[str]) -> str:
        role_hint = jd_text.split(".")[0][:120].strip() or "this role"
        bullets = "\n".join(f"- {item}" for item in resume_highlights[:3])
        return (
            f"Hi there — I'm reaching out regarding {role_hint}.\n\n"
            "I believe my background maps well to the team's needs, including:\n"
            f"{bullets}\n\n"
            "If helpful, I'd appreciate a referral or quick guidance on next steps. "
            "Thank you for your time."
        )
