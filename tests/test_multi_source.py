from pathlib import Path

from affilipilot.workflows.multi_source import render_multi_source_summary, run_multi_source_discovery


def test_multi_source_discovery_merges_and_dedupes(monkeypatch, tmp_path):
    import affilipilot.workflows.multi_source as workflow

    def fake_run_discover_convert(**kwargs):
        work = Path(kwargs["work_dir"])
        work.mkdir(parents=True, exist_ok=True)
        converted = work / "converted.txt"
        title = "Khăn sữa mềm" if "one" in str(work) else "Khăn sữa mềm duplicate"
        converted.write_text(
            f"https://go.isclix.com/deep_link/v5/same | title={title} | category=baby_care | image_url=https://cdn.example/a.jpg | affiliate_url=https://go.isclix.com/deep_link/v5/same\n",
            encoding="utf-8",
        )
        return {"converted_input": str(converted), "discovery": {"ok": True, "total": 1}, "conversion": {"ok_count": 1, "failed_count": 0, "total": 1}}

    monkeypatch.setattr(workflow, "run_discover_convert", fake_run_discover_convert)
    summary = run_multi_source_discovery(
        sources=[
            {"name": "one", "url": "https://example.com/one", "source": "LAZADA", "category": "baby_care", "campaign_key": "LAZADA"},
            {"name": "two", "url": "https://example.com/two", "source": "LAZADA", "category": "baby_care", "campaign_key": "LAZADA"},
        ],
        work_dir=tmp_path / "multi",
        per_source_limit=1,
        final_limit=5,
    )
    assert summary["source_count"] == 2
    assert summary["candidate_count"] == 1
    assert summary["selected_count"] == 1
    assert Path(summary["merged_input"]).exists()
    rendered = render_multi_source_summary(summary)
    assert "multi-source scanner" in rendered
