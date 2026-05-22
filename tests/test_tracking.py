from datetime import date

from affilipilot.links.subid import build_utm, make_tracking_identity


def test_tracking_identity_mapping():
    identity = make_tracking_identity("Kệ nhà bếp", 1, day=date(2026, 5, 16))
    assert identity.sub1 == "facebook"
    assert identity.sub2 == "smartshopping"
    assert identity.sub3 == "post_20260516_001"
    assert identity.sub4


def test_utm_mapping():
    identity = make_tracking_identity("Kệ nhà bếp", 1, day=date(2026, 5, 16))
    utm = build_utm(identity)
    assert utm["utm_source"] == "facebook"
    assert utm["utm_campaign"] == "affilipilot_smart_shopping_202605"
    assert utm["sub3"] == "post_20260516_001"
