from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from affilipilot.models import ProductCandidate


@dataclass(frozen=True)
class UrlClassification:
    marketplace: str
    kind: str
    normalized_url: str
    reasons: list[str] = field(default_factory=list)

    @property
    def is_product(self) -> bool:
        return self.kind == "product"

    @property
    def is_channel(self) -> bool:
        return self.kind in {"channel", "search", "tag", "shop", "listing"}


@dataclass(frozen=True)
class DiscoveryAdvice:
    ok: bool
    action: str
    reason: str
    command_hint: str = ""


class MarketplaceAdapter(Protocol):
    name: str

    def classify_url(self, url: str) -> UrlClassification:
        ...

    def is_product_url(self, url: str) -> bool:
        ...

    def is_channel_url(self, url: str) -> bool:
        ...

    def discovery_advice(self, url: str) -> DiscoveryAdvice:
        ...

    def normalize_candidate(self, product: ProductCandidate) -> ProductCandidate:
        ...
