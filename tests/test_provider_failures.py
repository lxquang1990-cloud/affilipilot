import urllib.error

import pytest

from affilipilot.marketplaces import shopee_public_api
from affilipilot.provider_failures import (
    ProviderBlockedError,
    ProviderFailureState,
    classify_provider_failure,
)


def test_classify_shopee_90309999_as_provider_blocked():
    failure = classify_provider_failure("shopee", status_code=403, body='{"error":90309999,"message":"blocked"}')
    assert failure.state == ProviderFailureState.PROVIDER_BLOCKED
    assert failure.retry_allowed is False
    assert failure.bypass_allowed is False
    assert failure.legacy_error == "blocked_by_shopee_403"
    assert "official" in failure.next_action


def test_classify_auth_required_before_generic_blocked():
    failure = classify_provider_failure("facebook", status_code=403, body="missing permission scope")
    assert failure.state == ProviderFailureState.AUTH_REQUIRED
    assert failure.retry_allowed is False
    assert failure.bypass_allowed is False
    assert failure.next_action == "refresh_or_request_official_credentials"


def test_classify_rate_limit_allows_later_retry():
    failure = classify_provider_failure("provider", status_code=429, body="too many requests")
    assert failure.state == ProviderFailureState.RATE_LIMITED
    assert failure.retry_allowed is True
    assert failure.bypass_allowed is False


def test_shopee_request_json_raises_structured_provider_block(monkeypatch):
    class FakeHTTPError(urllib.error.HTTPError):
        def read(self, amt=None):
            return b'{"error":90309999,"message":"blocked"}'

    def fake_urlopen(req, timeout=30):
        raise FakeHTTPError(req.full_url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr(shopee_public_api.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ProviderBlockedError) as excinfo:
        shopee_public_api._request_json("https://shopee.vn/api/v4/search/search_items")
    with pytest.raises(RuntimeError, match="blocked_by_shopee_403"):
        shopee_public_api._request_json("https://shopee.vn/api/v4/search/search_items")

    assert str(excinfo.value) == "blocked_by_shopee_403"
    failure = excinfo.value.failure
    assert failure.provider == "shopee"
    assert failure.state == ProviderFailureState.PROVIDER_BLOCKED
    assert failure.bypass_allowed is False
