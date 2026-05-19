"""AffiliPilot CLI package.

Public entry points:
    main(argv)        — process argv and dispatch to a command handler
    build_parser()    — return the argparse.ArgumentParser with all subcommands

Implementation is split across domain modules to keep each file under ~250
lines and let each domain own its own handlers + parser configuration:

    accesstrade.py    Accesstrade catalog/conversion/report commands
    facebook.py       Facebook token/publish/plan commands
    scan.py           Scan, discover, enrich, browser-plan commands
    workflow.py       E2E workflows: profit, run-day, multi-source, ...
    telegram.py       Telegram outbox/delivery commands
    observability.py  event-log, circuit-status, kill-switch, score-tier
    publish.py        ready-package, publish-safe, ready-to-publish, ...
    admin.py          doctor, readiness, init-secrets, sprint0, health

Adding a new command:
    1. Decorate a function in the appropriate domain module:

        from affilipilot.cli._registry import register

        @register("my-command", help="Short description")
        def cmd_my_command(args):
            ...
            return 0  # exit code

    2. Optionally pass ``configure=`` to add args to the subparser:

        def _configure(p):
            p.add_argument("--input", required=True)

        @register("my-command", help="...", configure=_configure)
        def cmd_my_command(args):
            ...
"""
from __future__ import annotations

from affilipilot.cli._registry import build_parser, main

# Backward-compat re-exports. Existing tests monkeypatch ``affilipilot.cli.publish_post``
# and similar symbols. Until those tests are migrated to patch the underlying
# module (``affilipilot.publishing.facebook.publish_post``), keep the symbols
# accessible at the package root. Removing these is a separate, breaking change.
from affilipilot._cli_legacy import (  # noqa: F401, E402
    publish_post,
    publish_photo_post,
    publish_multi_photo_post,
    publish_video_post,
    publish_gallery_comment,
)

__all__ = [
    "build_parser",
    "main",
    "publish_post",
    "publish_photo_post",
    "publish_multi_photo_post",
    "publish_video_post",
    "publish_gallery_comment",
]
