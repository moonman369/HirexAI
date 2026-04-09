"""Decision service for shortlist/reject classification."""

from __future__ import annotations

from dataclasses import dataclass

SHORTLISTED = "SHORTLISTED"
REJECTED = "REJECTED"


@dataclass(slots=True)
class DecisionResult:
    """Structured decision payload."""

    decision: str
    match_score: float
    threshold: float


class DecisionService:
    """Applies threshold rule to match score."""

    def __init__(self, *, threshold: float = 0.75) -> None:
        self.threshold = threshold

    def decide(self, *, match_score: float) -> DecisionResult:
        """Return `SHORTLISTED` when score meets threshold, else `REJECTED`."""
        decision = SHORTLISTED if match_score >= self.threshold else REJECTED
        return DecisionResult(decision=decision, match_score=match_score, threshold=self.threshold)
