"""Accesstrade catalog/conversion/report CLI commands.

Commands:
    accesstrade-campaigns     Fetch approved campaign registry
    accesstrade-datafeed      Fetch datafeed products + optional input TXT
    accesstrade-top-products  Fetch top products
    accesstrade-deals         Fetch offer merchants/keywords/coupons
    accesstrade-orders        Sync orders into local DB
    accesstrade-report        Summarize synced orders
    accesstrade-convert       Convert URLs to tracking links (dry-run default)

All commands are read-only with respect to Facebook publishing and never call
``publish_post``/``publish_photo_post``/etc. ``accesstrade-convert`` defaults
to dry-run; pass ``--real`` to call the Accesstrade API.
"""
from __future__ import annotations

import argparse

from affilipilot.accesstrade.campaigns import write_campaign_registry
from affilipilot.accesstrade.catalog import fetch_datafeeds, fetch_top_products, write_products_input
from affilipilot.accesstrade.deals import (
    fetch_coupons,
    fetch_offer_keywords,
    fetch_offer_merchants,
    write_deals,
)
from affilipilot.accesstrade.reports import (
    fetch_order_list,
    render_order_summary,
    save_orders,
    summarize_orders,
    write_json as write_report_json,
)
from affilipilot.cli._registry import register
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input

DEFAULT_DB = "data/affilipilot.db"


# ---------- accesstrade-campaigns ----------


def _configure_campaigns(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", default="data/accesstrade/campaigns.json")
    p.add_argument("--approval", default="successful")


@register("accesstrade-campaigns", help="Fetch approved Accesstrade campaign registry; no publish", configure=_configure_campaigns)
def cmd_accesstrade_campaigns(args: argparse.Namespace) -> int:
    registry = write_campaign_registry(args.out, approval=args.approval)
    print(f"Accesstrade campaigns: ok={registry.get('ok')} count={len(registry.get('campaigns', []))}")
    if registry.get("error"):
        print(f"Error: {registry['error']}")
    print(f"Output JSON: {args.out}")
    return 0 if registry.get("ok") else 2


# ---------- accesstrade-datafeed ----------


def _configure_datafeed(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", default="data/accesstrade/datafeed.json")
    p.add_argument("--write-input", default="")
    p.add_argument("--campaign", default="")
    p.add_argument("--domain", default="")
    p.add_argument(
        "--cat",
        default="",
        help="Accesstrade category code, e.g. thiet-bi-gia-dung, cong-nghe, nha-cua-doi-song",
    )
    p.add_argument("--status-discount", default="")
    p.add_argument("--discount-rate-from", default="")
    p.add_argument("--price-from", default="")
    p.add_argument("--price-to", default="")
    p.add_argument("--category", default="")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=50)


@register(
    "accesstrade-datafeed",
    help="Fetch Accesstrade datafeed products and optionally write AffiliPilot input TXT",
    configure=_configure_datafeed,
)
def cmd_accesstrade_datafeed(args: argparse.Namespace) -> int:
    data = fetch_datafeeds(
        campaign=args.campaign,
        domain=args.domain,
        cat=args.cat,
        status_discount=args.status_discount,
        discount_rate_from=args.discount_rate_from,
        price_from=args.price_from,
        price_to=args.price_to,
        page=args.page,
        limit=args.limit,
    )
    write_report_json(args.out, data)
    print(f"Accesstrade datafeed: ok={data.get('ok')} products={len(data.get('products', []))}")
    print(f"Output JSON: {args.out}")
    if args.write_input:
        path = write_products_input(data.get("products", []), args.write_input, category_override=args.category)
        print(f"Input TXT: {path}")
    return 0 if data.get("ok") else 2


# ---------- accesstrade-top-products ----------


def _configure_top_products(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", default="data/accesstrade/top-products.json")
    p.add_argument("--write-input", default="")
    p.add_argument("--merchant", default="")
    p.add_argument("--date-from", default="")
    p.add_argument("--date-to", default="")
    p.add_argument("--category", default="")


@register(
    "accesstrade-top-products",
    help="Fetch Accesstrade top products and optionally write AffiliPilot input TXT",
    configure=_configure_top_products,
)
def cmd_accesstrade_top_products(args: argparse.Namespace) -> int:
    data = fetch_top_products(merchant=args.merchant, date_from=args.date_from, date_to=args.date_to)
    write_report_json(args.out, data)
    print(f"Accesstrade top-products: ok={data.get('ok')} products={len(data.get('products', []))}")
    print(f"Output JSON: {args.out}")
    if args.write_input:
        path = write_products_input(data.get("products", []), args.write_input, category_override=args.category)
        print(f"Input TXT: {path}")
    return 0 if data.get("ok") else 2


# ---------- accesstrade-deals ----------


def _configure_deals(p: argparse.ArgumentParser) -> None:
    p.add_argument("--kind", choices=["merchants", "keywords", "coupons"], default="coupons")
    p.add_argument("--out", default="data/accesstrade/deals.json")
    p.add_argument("--merchant", default="")
    p.add_argument("--keyword", default="")
    p.add_argument("--next-day", action="store_true")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=50)


@register(
    "accesstrade-deals",
    help="Fetch Accesstrade offer merchants/keywords/coupons; no publish",
    configure=_configure_deals,
)
def cmd_accesstrade_deals(args: argparse.Namespace) -> int:
    if args.kind == "merchants":
        data = fetch_offer_merchants()
    elif args.kind == "keywords":
        data = fetch_offer_keywords()
    else:
        data = fetch_coupons(
            merchant=args.merchant,
            keyword=args.keyword,
            is_next_day_coupon=args.next_day,
            limit=args.limit,
            page=args.page,
        )
    write_deals(args.out, data)
    count_key = "deals" if args.kind == "coupons" else args.kind
    print(f"Accesstrade deals {args.kind}: ok={data.get('ok')} count={len(data.get(count_key, []))}")
    print(f"Output JSON: {args.out}")
    return 0 if data.get("ok") else 2


# ---------- accesstrade-orders ----------


def _configure_orders(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--out", default="data/accesstrade/orders.json")
    p.add_argument("--since", required=True)
    p.add_argument("--until", required=True)
    p.add_argument("--merchant", default="")
    p.add_argument("--status", default="")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=300)


@register(
    "accesstrade-orders",
    help="Fetch Accesstrade orders into local DB and print performance summary",
    configure=_configure_orders,
)
def cmd_accesstrade_orders(args: argparse.Namespace) -> int:
    data = fetch_order_list(
        since=args.since,
        until=args.until,
        merchant=args.merchant,
        status=args.status,
        page=args.page,
        limit=args.limit,
    )
    write_report_json(args.out, data)
    saved = save_orders(args.db, data.get("orders", [])) if data.get("ok") else 0
    summary = summarize_orders(args.db)
    print(f"Accesstrade orders: ok={data.get('ok')} fetched={len(data.get('orders', []))} saved={saved}")
    print(f"Output JSON: {args.out}")
    print(render_order_summary(summary))
    return 0 if data.get("ok") else 2


# ---------- accesstrade-report ----------


def _configure_report(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--out", default="")


@register("accesstrade-report", help="Summarize synced Accesstrade orders from local DB", configure=_configure_report)
def cmd_accesstrade_report(args: argparse.Namespace) -> int:
    summary = summarize_orders(args.db)
    print(render_order_summary(summary))
    if args.out:
        write_report_json(args.out, summary)
        print(f"Output JSON: {args.out}")
    return 0


# ---------- accesstrade-convert ----------


def _configure_convert(p: argparse.ArgumentParser) -> None:
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="data/accesstrade/converted.json")
    p.add_argument("--write-input", default="", help="Optional converted .txt input path")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--campaign-key",
        default="",
        help="Optional campaign key, e.g. SHOPEE, LAZADA, TIKI. Auto-detected by domain when configured.",
    )
    # --real flips dry_run off. Default dry_run=True is set via set_defaults
    # after we register the argument because argparse needs the action defined
    # before set_defaults can address its dest.
    p.add_argument("--real", dest="dry_run", action="store_false", help="Call real Accesstrade API")
    p.add_argument(
        "--allow-channel-urls",
        action="store_true",
        help="Development escape hatch: allow channel/search URLs past marketplace preflight",
    )
    p.set_defaults(dry_run=True)


@register(
    "accesstrade-convert",
    help="Convert product URLs to Accesstrade tracking links; dry-run by default",
    configure=_configure_convert,
)
def cmd_accesstrade_convert(args: argparse.Namespace) -> int:
    summary = convert_input_links(
        args.input,
        args.out,
        dry_run=args.dry_run,
        limit=args.limit,
        campaign_key=args.campaign_key,
        allow_channel_urls=args.allow_channel_urls,
    )
    print(
        f"Accesstrade convert: ok={summary['ok_count']} failed={summary['failed_count']} dry_run={summary['dry_run']}"
    )
    if summary.get("failed_count"):
        for row in summary.get("items", []):
            if row.get("result", {}).get("ok"):
                continue
            preflight = row.get("preflight", {})
            classification = preflight.get("classification", {})
            advice = preflight.get("advice", {})
            print(
                f"- blocked index={row.get('index')} "
                f"marketplace={classification.get('marketplace')} "
                f"kind={classification.get('kind')} "
                f"error={row.get('result', {}).get('error')}"
            )
            if advice.get("command_hint"):
                print(f"  hint: {advice.get('command_hint')}")
    print(f"Output JSON: {args.out}")
    if args.write_input:
        path = write_converted_input(args.out, args.write_input)
        print(f"Converted input: {path}")
    return 0 if summary["failed_count"] == 0 else 2
