from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

from affilipilot.content.regenerator import generate_until_content_gate_passes
from affilipilot.links.subid import build_utm, make_tracking_identity
from affilipilot.media import prepare_product_media, prepare_product_media_gallery
from affilipilot.scoring.product_score import score_product
from affilipilot.sources.manual_input import parse_link_lines, parse_products_csv
from affilipilot.telegram.cards import render_approval_card


def load_products(path: str | Path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return parse_products_csv(path)
    return parse_link_lines(path.read_text(encoding="utf-8"))


def build_batch(input_path: str | Path, out_dir: str | Path, *, limit: int = 5, day: date | None = None) -> dict:
    # Keep IDs deterministic for tests/demo until real scheduling injects the day.
    day = day or date(2026, 5, 16)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    products = load_products(input_path)
    scored = []
    for product in products:
        score_info = score_product(product)
        scored.append((int(score_info["score"]), score_info["reasons"], product))
    scored.sort(key=lambda item: item[0], reverse=True)

    selected = scored[:limit]
    posts = []
    cards = []
    for index, (score, reasons, product) in enumerate(selected, 1):
        identity = make_tracking_identity(product.title or product.url, index, day=day)
        regenerated = generate_until_content_gate_passes(product)
        draft = regenerated.draft
        card = render_approval_card(draft, post_id=identity.post_id)
        card_path = out_dir / f"{identity.post_id}.telegram.txt"
        post_path = out_dir / f"{identity.post_id}.post.txt"
        media_dir = out_dir / "media" / identity.post_id
        product_dict = asdict(product)
        gallery_results = prepare_product_media_gallery(product_dict, media_dir)
        media_result = gallery_results[0] if gallery_results else prepare_product_media(product_dict, media_dir)
        card_path.write_text(card, encoding="utf-8")
        post_path.write_text(draft.full_text + "\n", encoding="utf-8")
        post = {
            "post_id": identity.post_id,
            "product": asdict(product),
            "score": score,
            "score_reasons": reasons,
            "tracking": asdict(identity),
            "utm": build_utm(identity),
            "compliance": {
                "status": draft.compliance.status.value,
                "risk_flags": draft.compliance.risk_flags,
                "required_edits": draft.compliance.required_edits,
            },
            "content_gate": {
                "passed": regenerated.gate.passed,
                "score": regenerated.gate.score,
                "regenerated_count": regenerated.regenerated_count,
                "attempts": [attempt.__dict__ for attempt in regenerated.attempts],
                "reasons": regenerated.gate.reasons,
            },
            "media": {
                "ok": media_result.ok,
                "local_path": media_result.local_path,
                "media_type": media_result.media_type,
                "reasons": media_result.reasons,
                "source": product.media_source,
                "confidence": product.media_confidence,
                "gallery": [asdict(item) for item in gallery_results],
                "gallery_count": len(gallery_results),
                "video_urls": product.video_urls or ([product.video_url] if product.video_url else []),
            },
            "files": {
                "telegram_card": str(card_path),
                "post_text": str(post_path),
                "image": media_result.local_path if media_result.ok else "",
                "images": [item.local_path for item in gallery_results if item.ok],
            },
        }
        posts.append(post)
        cards.append(card)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "out_dir": str(out_dir),
        "total_products": len(products),
        "selected": len(posts),
        "posts": posts,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "approval_batch_preview.txt").write_text("\n\n---\n\n".join(cards) + "\n", encoding="utf-8")
    return manifest
