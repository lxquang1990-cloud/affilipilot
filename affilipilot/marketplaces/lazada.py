from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlparse, urlunparse

from affilipilot.marketplaces.base import DiscoveryAdvice, UrlClassification
from affilipilot.models import ProductCandidate
from affilipilot.quality import is_product_detail_url


class LazadaAdapter:
    name = "LAZADA"

    def classify_url(self, url: str) -> UrlClassification:
        parsed = urlparse(url.strip())
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        normalized = urlunparse(parsed._replace(fragment=""))
        reasons: list[str] = []
        if "lazada." not in host:
            return UrlClassification(self.name, "external", normalized, ["host_not_lazada"])
        if is_product_detail_url(normalized):
            return UrlClassification(self.name, "product", normalized, [])
        if path.startswith("/tag/"):
            return UrlClassification(self.name, "tag", normalized, ["lazada_tag_page_requires_discovery"])
        if path.startswith("/shop/") or "/shop/" in path:
            return UrlClassification(self.name, "shop", normalized, ["lazada_shop_page_requires_discovery"])
        if path.startswith("/catalog/") or "q=" in parsed.query.lower() or "keyword=" in parsed.query.lower():
            return UrlClassification(self.name, "search", normalized, ["lazada_search_page_requires_discovery"])
        if "sellercenter.lazada" in host or "helpcenter.lazada" in host:
            return UrlClassification(self.name, "blocked", normalized, ["lazada_navigation_or_support_url"])
        reasons.append("lazada_non_product_url")
        return UrlClassification(self.name, "channel", normalized, reasons)

    def is_product_url(self, url: str) -> bool:
        return self.classify_url(url).is_product

    def is_channel_url(self, url: str) -> bool:
        return self.classify_url(url).is_channel

    def discovery_advice(self, url: str) -> DiscoveryAdvice:
        classification = self.classify_url(url)
        if classification.kind == "product":
            return DiscoveryAdvice(True, "convert_affiliate", "URL is a Lazada product detail page.")
        if classification.kind == "blocked":
            return DiscoveryAdvice(False, "reject", ",".join(classification.reasons))
        if classification.is_channel:
            return DiscoveryAdvice(
                False,
                "discover_product_details",
                "Lazada channel/tag/search URLs must be used only for discovery, never direct affiliate conversion.",
                "python -m affilipilot browser-discover --source LAZADA --category <category> --url '<url>' --out data/scans/lazada-browser.json",
            )
        return DiscoveryAdvice(False, "unsupported", "Not a Lazada URL.")

    def normalize_candidate(self, product: ProductCandidate) -> ProductCandidate:
        classification = self.classify_url(product.original_url or product.url)
        notes = product.notes
        if classification.reasons:
            notes = (notes + ";" if notes else "") + ";".join(classification.reasons)
        return replace(product, original_url=product.original_url or (product.url if classification.is_product else ""), notes=notes)
