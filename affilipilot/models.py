from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ComplianceStatus(str, Enum):
    PASS = "pass"
    NEEDS_REVIEW = "needs_review"
    BLOCK = "block"


@dataclass
class ProductCandidate:
    url: str
    title: str = ""
    category: str = "unknown"
    price_vnd: Optional[int] = None
    commission_rate: Optional[float] = None
    image_url: str = ""
    image_path: str = ""
    video_url: str = ""
    video_path: str = ""
    affiliate_url: str = ""
    tracking_url: str = ""
    notes: str = ""


@dataclass
class TrackingIdentity:
    channel: str
    property_name: str
    post_id: str
    product_id: str

    @property
    def sub1(self) -> str:
        return self.channel

    @property
    def sub2(self) -> str:
        return self.property_name

    @property
    def sub3(self) -> str:
        return self.post_id

    @property
    def sub4(self) -> str:
        return self.product_id


@dataclass
class ComplianceResult:
    status: ComplianceStatus
    risk_flags: List[str] = field(default_factory=list)
    required_edits: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == ComplianceStatus.PASS


@dataclass
class ContentDraft:
    product: ProductCandidate
    hook: str
    body: str
    cta: str
    disclosure: str
    compliance: ComplianceResult

    @property
    def full_text(self) -> str:
        return "\n\n".join(part for part in [self.hook, self.body, self.cta, self.disclosure] if part)
