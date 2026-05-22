from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from affilipilot.content.caption_quality_ai import judge_caption_quality
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
    ai_retry_attempts: int | None = None,
) -> RegeneratedDraft:
    """Generate a caption, test A/B/C gates, regenerate with gate feedback if needed.

    The loop is intentionally bounded. If it still fails, caller can keep the
    item in audit/report and must not queue it for operator approval.
    """
    feedback: list[str] | None = None
    attempts: list[RegenerationAttempt] = []
    ai_retry_attempts = max_regenerations if ai_retry_attempts is None else ai_retry_attempts
    draft = generator(product)
    gate = evaluate_content_gates(product.__dict__, draft.full_text)
    quality_judge = judge_caption_quality(product, draft.full_text)
    draft.metadata.setdefault("caption_quality_passed", quality_judge.passed)
    draft.metadata.setdefault("caption_quality_score", quality_judge.score)
    draft.metadata.setdefault("caption_quality_source", quality_judge.source)
    draft.metadata.setdefault("caption_quality_reasons", quality_judge.reasons)
    draft.metadata.setdefault("caption_quality_recommendations", quality_judge.recommendations)
    passed = gate.passed and quality_judge.passed
    reasons = gate.reasons + [f"caption_quality:{reason}" for reason in quality_judge.reasons]
    attempts.append(RegenerationAttempt(attempt=0, passed=passed, score=min(gate.score, quality_judge.score / 100), reasons=reasons))

    total_attempts = max_regenerations + 1
    for attempt in range(1, total_attempts + 1):
        if passed:
            break
        feedback = gate.reasons + gate.recommendations + quality_judge.reasons + quality_judge.recommendations
        # Caption policy: production captions should remain AI-generated.
        # If AI cannot pass gates after bounded retries, keep the last AI draft
        # and let downstream gates/filtering hold it; do not switch to a
        # deterministic repair fallback that can reintroduce long checklist copy.
        draft = generator(product, feedback=feedback)
        gate = evaluate_content_gates(product.__dict__, draft.full_text)
        quality_judge = judge_caption_quality(product, draft.full_text)
        draft.metadata.update({
            "caption_quality_passed": quality_judge.passed,
            "caption_quality_score": quality_judge.score,
            "caption_quality_source": quality_judge.source,
            "caption_quality_reasons": quality_judge.reasons,
            "caption_quality_recommendations": quality_judge.recommendations,
        })
        passed = gate.passed and quality_judge.passed
        reasons = gate.reasons + [f"caption_quality:{reason}" for reason in quality_judge.reasons]
        attempts.append(RegenerationAttempt(attempt=attempt, passed=passed, score=min(gate.score, quality_judge.score / 100), reasons=reasons))

    return RegeneratedDraft(
        draft=draft,
        gate=gate,
        attempts=attempts,
        regenerated_count=max(0, len(attempts) - 1),
    )
