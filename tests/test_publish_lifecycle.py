from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.lifecycle import latest_publish_events, record_publish_event, render_publish_status


def test_publish_lifecycle_records_latest_event(tmp_path):
    db = tmp_path / "aff.db"
    AffiliPilotDB(db).init()
    record_publish_event(db, batch_key="b1", post_id="p1", state="published", facebook_post_id="fb1")
    record_publish_event(db, batch_key="b1", post_id="p1", state="deleted", facebook_post_id="fb1", reason="bad_media")
    latest = latest_publish_events(db, batch_key="b1")
    assert latest["p1"]["state"] == "deleted"
    assert latest["p1"]["reason"] == "bad_media"
    rendered = render_publish_status(db, batch_key="b1")
    assert "p1: deleted" in rendered
    assert "bad_media" in rendered
