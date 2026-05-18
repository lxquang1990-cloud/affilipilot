from __future__ import annotations

from urllib.parse import urlparse

from affilipilot.marketplaces.base import DiscoveryAdvice, MarketplaceAdapter, UrlClassification
from affilipilot.marketplaces.lazada import LazadaAdapter
from affilipilot.marketplaces.shopee import ShopeeAdapter

ADAPTERS = {
    "LAZADA": LazadaAdapter(),
    "SHOPEE": ShopeeAdapter(),
}


def adapter_for_url(url: str) -> MarketplaceAdapter | None:
    host = urlparse(url).netloc.lower()
    if "lazada." in host:
        return ADAPTERS["LAZADA"]
    if "shopee." in host:
        return ADAPTERS["SHOPEE"]
    return None


def classify_url(url: str) -> UrlClassification:
    adapter = adapter_for_url(url)
    if not adapter:
        return UrlClassification("UNKNOWN", "external", url, ["unsupported_marketplace"])
    return adapter.classify_url(url)


def discovery_advice(url: str) -> DiscoveryAdvice:
    adapter = adapter_for_url(url)
    if not adapter:
        return DiscoveryAdvice(False, "unsupported", "Unsupported marketplace URL.")
    return adapter.discovery_advice(url)

__all__ = ["ADAPTERS", "DiscoveryAdvice", "LazadaAdapter", "MarketplaceAdapter", "ShopeeAdapter", "UrlClassification", "adapter_for_url", "classify_url", "discovery_advice"]
