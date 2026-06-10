from __future__ import annotations

import csv
import io
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from affilipilot.models import ProductCandidate

SHOPEE_SMARTLINK_CAMPAIGN_ID = "4751584435713464237"
SHOPEE_SMARTLINK_JOB_ID = "128"
SHOPEE_SHORTLINK_DOMAIN = "https://shorten.asia"

BEST_SELLERS_SHEET_ID = "1TK_0HL8sJJFH0kiVrvhmQtpu6LcizXzb"
BEST_SELLERS_GID = "3026657"
MAJOR_PROGRAMS_SHEET_ID = "17CT-UJDjBW1NLt2cB4Hp0cqlGOB5uOAYe_g_qC2m95U"
MAJOR_PROGRAMS_GID = "691809098"
BRAND_BONUS_GID = "1591401277"

DEFAULT_SHOPEE_SHEETS = {
    "shopee_best_sellers": (BEST_SELLERS_SHEET_ID, BEST_SELLERS_GID),
    "shopee_major_programs": (MAJOR_PROGRAMS_SHEET_ID, MAJOR_PROGRAMS_GID),
    "shopee_brand_bonus": (MAJOR_PROGRAMS_SHEET_ID, BRAND_BONUS_GID),
}

_URL_RE = re.compile(r"https?://[^\s\]\)\}\>\"']+", re.I)
_PRICE_RE = re.compile(r"(?:₫|đ|vnd)?\s*([0-9][0-9\.,]{3,})", re.I)
_PERCENT_RE = re.compile(r"([0-9]+(?:[\.,][0-9]+)?)\s*%")

@dataclass
class ShopeeSheetProduct:
    url: str
    title: str = ""
    category: str = "shopee"
    price_vnd: int | None = None
    commission_rate: float | None = None
    image_url: str = ""
    merchant: str = ""
    source: str = "accesstrade_shopee_sheet"
    raw: dict[str, Any] | None = None

    def to_candidate(self) -> ProductCandidate:
        notes = [
            "source=accesstrade_shopee_sheet",
            f"merchant={self.merchant}" if self.merchant else "",
            f"campaign_id={SHOPEE_SMARTLINK_CAMPAIGN_ID}",
            f"job_id={SHOPEE_SMARTLINK_JOB_ID}",
            f"shortlink_domain={SHOPEE_SHORTLINK_DOMAIN}",
        ]
        return ProductCandidate(
            url=self.url,
            title=self.title,
            category=self.category or "shopee",
            price_vnd=self.price_vnd,
            commission_rate=self.commission_rate,
            image_url=self.image_url,
            notes=";".join(x for x in notes if x),
            media_source="accesstrade_shopee_sheet",
            media_confidence="partner_sheet" if self.image_url else "missing",
            original_url=self.url,
            campaign_id=SHOPEE_SMARTLINK_CAMPAIGN_ID,
            campaign_key="SHOPEE",
        )

def google_sheet_csv_url(sheet_id: str, gid: str = "0") -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={urllib.parse.quote(str(gid))}"


def google_sheet_gviz_csv_url(sheet_id: str, gid: str = "0") -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={urllib.parse.quote(str(gid))}"

def _fetch_text(url: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AffiliPilot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8-sig", errors="replace")

def _norm_key(value: str) -> str:
    text = (value or "").strip().lower()
    text = text.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")

def _first(row: dict[str, str], keys: tuple[str, ...]) -> str:
    norm = {_norm_key(k): v for k, v in row.items()}
    for key in keys:
        if key in norm and str(norm[key]).strip():
            return str(norm[key]).strip()
    return ""

def _find_url(row: dict[str, str]) -> str:
    direct = _first(row, ("url", "link", "link_item", "item_link", "product_link", "product_url", "shopee_link", "campaign_url", "tracking_link"))
    if direct.startswith("http"):
        return direct
    if direct.startswith("shopee."):
        return "https://" + direct
    joined = " ".join(str(v or "") for v in row.values())
    for match in _URL_RE.findall(joined):
        if "shopee.vn" in match.lower() or "shopee.com" in match.lower():
            return match.rstrip(".,;")
    naked = re.search(r"(?:^|\s)(shopee\.(?:vn|com)/[^\s,]+)", joined, re.I)
    if naked:
        return "https://" + naked.group(1).rstrip(".,;")
    return ""

def _parse_price(value: str) -> int | None:
    if not value:
        return None
    match = _PRICE_RE.search(str(value))
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None

def _parse_rate(value: str) -> float | None:
    if not value:
        return None
    match = _PERCENT_RE.search(str(value))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ".")) / 100.0
    except ValueError:
        return None

def product_from_row(row: dict[str, str]) -> ShopeeSheetProduct | None:
    url = _find_url(row)
    if not url:
        return None
    title = _first(row, ("title", "ten_san_pham", "product_name", "name", "san_pham", "item_name"))
    if not title:
        title = next((str(v).strip() for v in row.values() if str(v).strip() and "http" not in str(v).lower()), "Shopee product")
    price_text = _first(row, ("current_selling_price", "seller_price", "price", "gia", "sale_price", "gia_ban", "gia_km", "price_before_discount")) or " ".join(str(v) for v in row.values())
    rate_text = _first(row, ("avg_cms_rate", "commission", "commission_rate", "hoa_hong", "brand_bonus", "bonus")) or " ".join(str(v) for v in row.values())
    image = _first(row, ("image", "image_url", "thumbnail", "img", "anh"))
    merchant = _first(row, ("seller_name", "shop", "merchant", "seller", "brand", "nhan_hang", "shop_name"))
    category = _first(row, ("category", "cate", "nganh_hang", "danh_muc")) or "shopee"
    return ShopeeSheetProduct(
        url=url,
        title=title,
        category=category,
        price_vnd=_parse_price(price_text),
        commission_rate=_parse_rate(rate_text),
        image_url=image if image.startswith("http") else "",
        merchant=merchant,
        raw=row,
    )

def parse_sheet_csv(text: str, *, limit: int = 100, offset: int = 0) -> list[ShopeeSheetProduct]:
    reader = csv.DictReader(io.StringIO(text))
    products: list[ShopeeSheetProduct] = []
    seen: set[str] = set()
    for row in reader:
        product = product_from_row({str(k or ""): str(v or "") for k, v in row.items()})
        if not product:
            continue
        key = product.url.split("?", 1)[0].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        products.append(product)
    start = max(0, int(offset or 0))
    end = start + max(0, int(limit or 0)) if limit else None
    return products[start:end]

def count_sheet_products(text: str) -> int:
    return len(parse_sheet_csv(text, limit=0, offset=0))

def fetch_shopee_sheet_products(*, sheet_id: str = BEST_SELLERS_SHEET_ID, gid: str = BEST_SELLERS_GID, limit: int = 100, offset: int = 0, timeout: int = 30, source_name: str = "shopee_sheet") -> dict[str, Any]:
    urls = [google_sheet_csv_url(sheet_id, gid), google_sheet_gviz_csv_url(sheet_id, gid)]
    url = urls[0]
    fetch_error = ""
    try:
        text = ""
        for candidate_url in urls:
            url = candidate_url
            try:
                text = _fetch_text(candidate_url, timeout=timeout)
                fetch_error = ""
                break
            except Exception as exc:  # noqa: BLE001
                fetch_error = f"{type(exc).__name__}"
                text = ""
        if not text:
            raise RuntimeError(f"all_sheet_csv_endpoints_failed:{fetch_error or 'unknown'}")
        total_available = count_sheet_products(text)
        products = parse_sheet_csv(text, limit=limit, offset=offset)
        # Return the same product dict shape consumed by catalog.write_products_input.
        # Keep Shopee-specific campaign/shortlink metadata in notes via merchant/product_id.
        catalog_products = []
        for p in products:
            catalog_products.append({
                "url": p.url,
                "title": p.title,
                "category": p.category,
                "price_vnd": p.price_vnd,
                "discount_vnd": p.price_vnd,
                "discount_rate": None,
                "image_url": p.image_url,
                "affiliate_url": "",
                "product_id": f"campaign_id={SHOPEE_SMARTLINK_CAMPAIGN_ID};job_id={SHOPEE_SMARTLINK_JOB_ID};shortlink_domain={SHOPEE_SHORTLINK_DOMAIN}",
                "merchant": p.merchant or "shopee.vn",
                "source": "accesstrade_shopee_sheet",
                "raw": p.raw,
            })
        return {
            "ok": True,
            "source": "shopee_sheet",
            "source_name": source_name,
            "source_url": url,
            "export_url": urls[0],
            "fallback_url": urls[1],
            "sheet_id": sheet_id,
            "gid": gid,
            "total": len(catalog_products),
            "total_available": total_available,
            "offset": max(0, int(offset or 0)),
            "limit": limit,
            "products": catalog_products,
        }
    except Exception as exc:
        return {
            "ok": False,
            "source": "shopee_sheet",
            "source_name": source_name,
            "source_url": url,
            "export_url": urls[0],
            "fallback_url": urls[1],
            "sheet_id": sheet_id,
            "gid": gid,
            "error": f"sheet_fetch_error:{type(exc).__name__}",
            "offset": max(0, int(offset or 0)),
            "limit": limit,
            "products": [],
        }

def write_products_input(products: list[dict[str, Any]], out_path: str) -> None:
    from pathlib import Path
    lines: list[str] = []
    for p in products:
        cand = ShopeeSheetProduct(**{k: p.get(k) for k in ShopeeSheetProduct.__dataclass_fields__}).to_candidate()
        parts = [cand.url]
        for key, value in {
            "title": cand.title,
            "category": cand.category,
            "price": cand.price_vnd,
            "commission_rate": cand.commission_rate,
            "image_url": cand.image_url,
            "notes": cand.notes,
            "media_source": cand.media_source,
            "media_confidence": cand.media_confidence,
            "original_url": cand.original_url,
            "campaign_id": cand.campaign_id,
            "campaign_key": cand.campaign_key,
        }.items():
            if value not in (None, ""):
                parts.append(f"{key}={value}")
        lines.append(" | ".join(str(x) for x in parts))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
