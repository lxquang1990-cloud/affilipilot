from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from affilipilot.content.content_gate import ContentGateResult, evaluate_content_gates
from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ContentDraft, ProductCandidate

DraftGenerator = Callable[..., ContentDraft]


@dataclass
class RegenerationAttempt:
    attempt: int
    passed: bool
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class RegeneratedDraft:
    draft: ContentDraft
    gate: ContentGateResult
    attempts: list[RegenerationAttempt]
    regenerated_count: int


def generate_until_content_gate_passes(
    product: ProductCandidate,
    *,
    max_regenerations: int = 2,
    generator: DraftGenerator = generate_safe_facebook_draft,
) -> RegeneratedDraft:
    """Generate a caption, test A/B/C gates, regenerate with gate feedback if needed.

    The loop is intentionally bounded. If it still fails, caller can keep the
    item in audit/report and must not queue it for operator approval.
    """
    feedback: list[str] | None = None
    attempts: list[RegenerationAttempt] = []
    draft = generator(product)
    gate = evaluate_content_gates(product.__dict__, draft.full_text)
    attempts.append(RegenerationAttempt(attempt=0, passed=gate.passed, score=gate.score, reasons=gate.reasons))

    for attempt in range(1, max_regenerations + 1):
        if gate.passed:
            break
        feedback = gate.reasons + gate.recommendations
        draft = generator(product, feedback=feedback)
        gate = evaluate_content_gates(product.__dict__, draft.full_text)
        attempts.append(RegenerationAttempt(attempt=attempt, passed=gate.passed, score=gate.score, reasons=gate.reasons))

    return RegeneratedDraft(
        draft=draft,
        gate=gate,
        attempts=attempts,
        regenerated_count=max(0, len(attempts) - 1),
    )
