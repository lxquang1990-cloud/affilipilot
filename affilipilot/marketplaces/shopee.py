from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urlparse, urlunparse

from affilipilot.marketplaces.base import DiscoveryAdvice, UrlClassification
from affilipilot.models import ProductCandidate

_PRODUCT_PATTERNS = (
    re.compile(r"-i\.(\d+)\.(\d+)", re.I),
    re.compile(r"/product/(\d+)/(\d+)", re.I),
)


class ShopeeAdapter:
    name = "SHOPEE"

    def classify_url(self, url: str) -> UrlClassification:
        parsed = urlparse(url.strip())
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        normalized = urlunparse(parsed._replace(fragment=""))
        if "shopee." not in host and "s.shopee." not in host:
            return UrlClassification(self.name, "external", normalized, ["host_not_shopee"])
        if "s.shopee." in host:
            return UrlClassification(self.name, "shortlink", normalized, ["shopee_shortlink_requires_resolution_before_validation"])
        if any(pattern.search(path) for pattern in _PRODUCT_PATTERNS):
            return UrlClassification(self.name, "product", normalized, [])
        if path.startswith("/shop/") or path.startswith("/mall/"):
            return UrlClassification(self.name, "shop", normalized, ["shopee_shop_page_requires_discovery"])
        if path.startswith("/search") or "keyword=" in parsed.query.lower():
            return UrlClassification(self.name, "search", normalized, ["shopee_search_page_requires_discovery"])
        if path.strip("/"):
            return UrlClassification(self.name, "listing", normalized, ["shopee_non_product_url_requires_discovery"])
        return UrlClassification(self.name, "channel", normalized, ["shopee_home_or_channel_requires_discovery"])

    def is_product_url(self, url: str) -> bool:
        return self.classify_url(url).is_product

    def is_channel_url(self, url: str) -> bool:
        return self.classify_url(url).is_channel

    def discovery_advice(self, url: str) -> DiscoveryAdvice:
        classification = self.classify_url(url)
        if classification.kind == "product":
            return DiscoveryAdvice(True, "convert_affiliate", "URL is a Shopee product detail page.")
        if classification.kind == "shortlink":
            return DiscoveryAdvice(False, "resolve_shortlink", "Resolve s.shopee shortlinks before product validation.")
        if classification.is_channel:
            return DiscoveryAdvice(False, "discover_product_details", "Shopee shop/search/channel URLs must be used only for discovery, never direct affiliate conversion.")
        return DiscoveryAdvice(False, "unsupported", "Not a Shopee URL.")

    def normalize_candidate(self, product: ProductCandidate) -> ProductCandidate:
        classification = self.classify_url(product.original_url or product.url)
        notes = product.notes
        if classification.reasons:
            notes = (notes + ";" if notes else "") + ";".join(classification.reasons)
        return replace(product, original_url=product.original_url or (product.url if classification.is_product else ""), notes=notes)
