"""Provider failure classification helpers.

Project-local integration of SnailBot Level 4 provider-block playbook.
The goal is to classify external API/provider failures as provider state, not
local parser bugs, and avoid unsafe retry/bypass behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ProviderFailureState(str, Enum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    AUTH_REQUIRED = "auth_required"
    PROVIDER_BLOCKED = "provider_blocked"
    NOT_FOUND = "not_found"
    SERVER_ERROR = "server_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass(frozen=True)
class ProviderFailure:
    provider: str
    state: ProviderFailureState
    status_code: int | None = None
    message: str = ""
    retry_allowed: bool = False
    bypass_allowed: bool = False
    next_action: str = ""
    legacy_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


def classify_provider_failure(
    provider: str,
    *,
    status_code: int | None = None,
    body: str = "",
    error: str = "",
) -> ProviderFailure:
    text = f"{body or ''}\n{error or ''}".lower()

    if status_code is not None and 200 <= status_code < 300:
        return ProviderFailure(provider, ProviderFailureState.OK, status_code, "ok", False, False, "continue_normal_pipeline")

    if status_code == 429 or "rate limit" in text or "too many requests" in text:
        return ProviderFailure(
            provider,
            ProviderFailureState.RATE_LIMITED,
            status_code,
            "provider_rate_limited",
            True,
            False,
            "stop_retries_and_wait_for_retry_after_or_next_slot",
        )

    if status_code in {401, 403} and any(token in text for token in ("unauthorized", "invalid token", "permission", "scope", "auth")):
        return ProviderFailure(
            provider,
            ProviderFailureState.AUTH_REQUIRED,
            status_code,
            "provider_auth_required",
            False,
            False,
            "refresh_or_request_official_credentials",
        )

    if status_code == 403 or any(token in text for token in ("anti-bot", "waf", "captcha", "blocked", "error:90309999", "90309999")):
        legacy = f"blocked_by_{provider}_403" if status_code == 403 else f"blocked_by_{provider}"
        return ProviderFailure(
            provider,
            ProviderFailureState.PROVIDER_BLOCKED,
            status_code,
            "provider_blocked",
            False,
            False,
            "use_official_api_feed_manual_import_or_owner_approved_browser_flow",
            legacy,
        )

    if status_code == 404:
        return ProviderFailure(
            provider,
            ProviderFailureState.NOT_FOUND,
            status_code,
            "provider_not_found",
            False,
            False,
            "mark_source_unavailable_and_try_alternate_official_source",
        )

    if status_code is not None and status_code >= 500:
        return ProviderFailure(
            provider,
            ProviderFailureState.SERVER_ERROR,
            status_code,
            "provider_server_error",
            True,
            False,
            "record_incident_and_retry_later_with_backoff",
        )

    return ProviderFailure(
        provider,
        ProviderFailureState.UNKNOWN_ERROR,
        status_code,
        "provider_unknown_error",
        False,
        False,
        "capture_fixture_and_triage_before_code_changes",
    )


class ProviderBlockedError(RuntimeError):
    """Raised when a provider blocks access and bypass is not allowed."""

    def __init__(self, failure: ProviderFailure):
        self.failure = failure
        message = failure.legacy_error or failure.message or failure.state.value
        super().__init__(message)
