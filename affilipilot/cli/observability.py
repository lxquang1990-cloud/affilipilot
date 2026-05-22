"""Observability / control-plane CLI commands.

Commands:
    event-log            Render structured JSONL events
    circuit-status       Show auto-publish circuit breaker state
    kill-switch          Toggle /tmp/affilipilot.KILL
    score-tier           Score products and classify into tier
    conversion-record    Insert/upsert one conversion row
    conversion-summary   Render local conversion/ROI summary
    performance-feedback Build published-post → order feedback report
"""
from __future__ import annotations

import argparse
from pathlib import Path

from affilipilot.analytics.conversions import (
    render_conversion_summary,
    summarize_conversions,
    upsert_conversion,
)
from affilipilot.analytics.feedback import build_feedback_report, render_feedback_report, write_feedback_json
from affilipilot.cli._registry import register
from affilipilot.observability.circuit_breaker import (
    check_circuit,
    render_circuit_status,
    set_kill_switch,
)
from affilipilot.observability.event_log import EventLog, read_events, render_events
from affilipilot.scoring.confidence import compute_confidence
from affilipilot.scoring.tier import classify_tier, load_tier_config, render_tier_result
from affilipilot.sources.manual_input import parse_link_lines

DEFAULT_EVENT_LOG = "data/logs/affilipilot-events.jsonl"
DEFAULT_STATE = "data/auto_publish_state.json"
DEFAULT_KILL_PATH = "/tmp/affilipilot.KILL"
DEFAULT_DB = "data/affilipilot.db"


def _configure_event_log(p: argparse.ArgumentParser) -> None:
    p.add_argument("--path", default=DEFAULT_EVENT_LOG)
    p.add_argument("--limit", type=int, default=30)


@register("event-log", help="Render structured AffiliPilot JSONL events", configure=_configure_event_log)
def cmd_event_log(args: argparse.Namespace) -> int:
    print(render_events(read_events(args.path, limit=args.limit)))
    return 0


def _configure_circuit_status(p: argparse.ArgumentParser) -> None:
    p.add_argument("--state", default=DEFAULT_STATE)
    p.add_argument("--kill-path", default=DEFAULT_KILL_PATH)
    p.add_argument("--event-log", default=DEFAULT_EVENT_LOG)


@register("circuit-status", help="Show auto-publish circuit breaker status", configure=_configure_circuit_status)
def cmd_circuit_status(args: argparse.Namespace) -> int:
    status = check_circuit(state_path=args.state, kill_path=args.kill_path, event_log_path=args.event_log)
    print(render_circuit_status(status))
    return 0 if status.allowed else 2


def _configure_kill_switch(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", choices=["on", "off"])
    p.add_argument("--reason", default="operator")
    p.add_argument("--kill-path", default=DEFAULT_KILL_PATH)
    p.add_argument("--event-log", default=DEFAULT_EVENT_LOG)


@register("kill-switch", help="Toggle auto-publish kill switch", configure=_configure_kill_switch)
def cmd_kill_switch(args: argparse.Namespace) -> int:
    enabled = args.action == "on"
    status = set_kill_switch(enabled, kill_path=args.kill_path, event_log_path=args.event_log, reason=args.reason)
    print(render_circuit_status(status))
    return 0


def _configure_score_tier(p: argparse.ArgumentParser) -> None:
    p.add_argument("--input", required=True)
    p.add_argument("--config", default="config/tier-config.json")
    p.add_argument("--event-log", default=DEFAULT_EVENT_LOG)
    p.add_argument("--limit", type=int, default=20)


@register(
    "score-tier",
    help="Score input products and classify auto/soft/manual/blocked tiers; no publish",
    configure=_configure_score_tier,
)
def cmd_score_tier(args: argparse.Namespace) -> int:
    products = parse_link_lines(Path(args.input).read_text(encoding="utf-8"))
    cfg = load_tier_config(args.config)
    log = EventLog(args.event_log)
    print(f"AffiliPilot tier scoring: {len(products)} products")
    for product in products[: args.limit]:
        score, signals = compute_confidence(product)
        tier = classify_tier(score, signals, cfg)
        log.event(
            "draft_classified",
            title=product.title,
            url=product.url,
            score=score,
            tier=tier.value,
            signals=signals,
        )
        print(f"- {product.title or product.url}: {render_tier_result(score, tier, signals)}")
    return 0


def _configure_conversion_record(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--sub-id", required=True)
    p.add_argument("--order-id", required=True)
    p.add_argument("--status", default="pending")
    p.add_argument("--commission-vnd", type=int, default=0)
    p.add_argument("--order-value-vnd", type=int, default=0)
    p.add_argument("--draft-id", default="")
    p.add_argument("--post-id", default="")
    p.add_argument("--campaign-id", default="")


@register(
    "conversion-record",
    help="Record one conversion/order row for ROI tracking",
    configure=_configure_conversion_record,
)
def cmd_conversion_record(args: argparse.Namespace) -> int:
    order = {
        "sub_id": args.sub_id,
        "order_id": args.order_id,
        "order_status": args.status,
        "commission_vnd": args.commission_vnd,
        "order_value_vnd": args.order_value_vnd,
        "draft_id": args.draft_id,
        "post_id": args.post_id,
        "campaign_id": args.campaign_id,
    }
    upsert_conversion(args.db, order)
    print(render_conversion_summary(summarize_conversions(args.db)))
    return 0


def _configure_conversion_summary(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=DEFAULT_DB)


@register("conversion-summary", help="Summarize local conversion/ROI table", configure=_configure_conversion_summary)
def cmd_conversion_summary(args: argparse.Namespace) -> int:
    print(render_conversion_summary(summarize_conversions(args.db)))
    return 0

def _configure_performance_feedback(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--batch-key", default="")
    p.add_argument("--out", default="")

@register("performance-feedback", help="Build published-post to Accesstrade order feedback report", configure=_configure_performance_feedback)
def cmd_performance_feedback(args: argparse.Namespace) -> int:
    report = build_feedback_report(args.db, batch_key=args.batch_key)
    print(render_feedback_report(report))
    if args.out:
        write_feedback_json(args.out, report)
        print(f"Output JSON: {args.out}")
    return 0
