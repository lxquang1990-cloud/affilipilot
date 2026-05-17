from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from affilipilot.publishing.requirements import check_affiliate_link, check_media
from affilipilot.workflows.daily_batch import load_products


@dataclass
class ProductValidationItem:
    index: int
    title: str
    url: str
    passed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class AffiliateReadyValidation:
    input_path: str
    total: int
    passed_count: int
    failed_count: int
    items: list[ProductValidationItem]

    @property
    def passed(self) -> bool:
        return self.failed_count == 0 and self.total > 0


def validate_affiliate_ready_input(input_path: str | Path) -> AffiliateReadyValidation:
    products = load_products(input_path)
    items: list[ProductValidationItem] = []
    for index, product in enumerate(products, 1):
        post = {"product": product.__dict__, "files": {}}
        affiliate = check_affiliate_link(post)
        media = check_media(post)
        reasons = affiliate.reasons + media.reasons
        items.append(ProductValidationItem(
            index=index,
            title=product.title,
            url=product.url,
            passed=not reasons,
            reasons=reasons,
        ))
    passed_count = sum(1 for item in items if item.passed)
    return AffiliateReadyValidation(
        input_path=str(input_path),
        total=len(items),
        passed_count=passed_count,
        failed_count=len(items) - passed_count,
        items=items,
    )


def render_affiliate_ready_validation(validation: AffiliateReadyValidation) -> str:
    lines = [
        f"🐌 Affiliate-ready input validation — {validation.input_path}",
        f"Total: {validation.total}",
        f"Passed: {validation.passed_count}",
        f"Failed: {validation.failed_count}",
        "",
    ]
    for item in validation.items:
        icon = "✅" if item.passed else "○"
        title = item.title or item.url
        lines.append(f"{icon} #{item.index} {title}")
        if item.reasons:
            lines.append("   reasons: " + ", ".join(item.reasons))
    return "\n".join(lines)
