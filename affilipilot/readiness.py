from __future__ import annotations

from dataclasses import dataclass, field

from affilipilot.config import load_config
from affilipilot.security import check_secret_file_permissions

@dataclass
class ReadinessCheck:
    name: str
    status: str
    detail: str = ""
    required_for: tuple[str, ...] = ()

@dataclass
class ReadinessReport:
    checks: list[ReadinessCheck] = field(default_factory=list)

    @property
    def ready_for_local_manual(self) -> bool:
        required = {"product_input", "compliance_policy", "approval_state", "local_smoke"}
        return self._all_pass(required)

    @property
    def ready_for_sprint1_manual(self) -> bool:
        return self.ready_for_local_manual

    @property
    def ready_for_accesstrade_api(self) -> bool:
        return self._all_pass({"secret_file", "accesstrade_token", "accesstrade_campaign"})

    @property
    def ready_for_facebook_token_check(self) -> bool:
        return self._all_pass({"secret_file", "facebook_page_id", "facebook_page_token"})

    @property
    def ready_for_facebook_publish(self) -> bool:
        # Config-present only. Operators still must run facebook-token-check and approve-ready.
        return self.ready_for_facebook_token_check

    @property
    def ready_for_direct_telegram(self) -> bool:
        return self._all_pass({"secret_file", "telegram_config"})

    def _status(self, name: str) -> str:
        for check in self.checks:
            if check.name == name:
                return check.status
        return "missing"

    def _all_pass(self, names: set[str]) -> bool:
        return all(self._status(name) == "pass" for name in names)

def build_readiness_report() -> ReadinessReport:
    cfg = load_config()
    secret = check_secret_file_permissions(cfg.secret_path)
    secret_status = "pass" if secret["exists"] and secret["secure"] else "warn"
    checks = [
        ReadinessCheck("secret_file", secret_status, f"{secret}", ("accesstrade", "facebook", "telegram")),
        ReadinessCheck("product_input", "pass", "manual link/CSV input supported", ("local",)),
        ReadinessCheck("compliance_policy", "pass", "mother/baby policy implemented", ("local", "publish")),
        ReadinessCheck("approval_state", "pass", "SQLite approval decisions supported", ("local", "publish")),
        ReadinessCheck("local_smoke", "pass", "demo-happy-path command available; verify_all runs smoke", ("local",)),
        ReadinessCheck("accesstrade_token", "pass" if cfg.accesstrade_token_present else "missing", "required for tracking-link API", ("accesstrade",)),
        ReadinessCheck("accesstrade_campaign", "pass" if cfg.accesstrade_campaign_present else "missing", f"required for tracking-link API; configured campaigns: {cfg.accesstrade_campaign_count}", ("accesstrade",)),
        ReadinessCheck("facebook_page_id", "pass" if cfg.facebook_page_id_present else "missing", "required for Graph API token check/publish", ("facebook",)),
        ReadinessCheck("facebook_page_token", "pass" if cfg.facebook_page_token_present else "missing", "required for Graph API token check/publish", ("facebook",)),
        ReadinessCheck("9router_key", "pass" if cfg.router_key_present else "optional", "only needed for future real LLM generation; deterministic fallback works", ("future_llm",)),
        ReadinessCheck("9router_endpoint", "pass" if cfg.router_endpoint_present else "optional", "only needed for future real LLM generation", ("future_llm",)),
        ReadinessCheck("telegram_config", "pass" if cfg.telegram_config_present else "optional", "direct Telegram bot delivery optional; OpenClaw route preferred", ("telegram",)),
    ]
    return ReadinessReport(checks=checks)

def render_readiness_report(report: ReadinessReport) -> str:
    lines = ["🐌 AffiliPilot readiness report", ""]
    for check in report.checks:
        icon = "✅" if check.status == "pass" else "⚠️" if check.status == "warn" else "○" if check.status == "optional" else "✖"
        scope = f" [{', '.join(check.required_for)}]" if check.required_for else ""
        lines.append(f"{icon} {check.name}: {check.status}{scope} — {check.detail}")
    lines.extend([
        "",
        "Readiness gates:",
        f"- Local manual workflow: {'yes' if report.ready_for_local_manual else 'no'}",
        f"- Accesstrade API: {'yes' if report.ready_for_accesstrade_api else 'no'}",
        f"- Facebook token check: {'yes' if report.ready_for_facebook_token_check else 'no'}",
        f"- Facebook publish config-present: {'yes' if report.ready_for_facebook_publish else 'no'}",
        f"- Direct Telegram bot config: {'yes' if report.ready_for_direct_telegram else 'no'}",
        "",
        "Publish still requires: approved post + compliance pass + affiliate link + media + facebook-token-check pass + publishable dry-run plan.",
    ])
    return "\n".join(lines)
