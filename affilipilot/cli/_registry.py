"""Command registry for the AffiliPilot CLI.

This module owns the global ``_COMMANDS`` registry and the canonical
``build_parser`` / ``main`` entry points. Domain modules register themselves
via ``@register`` decorators; importing the ``cli`` package triggers those
imports so the registry is populated before ``build_parser`` is called.
"""
from __future__ import annotations

import argparse
import importlib
from typing import Callable, NamedTuple


class _Command(NamedTuple):
    name: str
    help: str
    configure: Callable[[argparse.ArgumentParser], None] | None
    handler: Callable[[argparse.Namespace], int]


_COMMANDS: list[_Command] = []

# Domain modules whose import side-effect is to register commands. Order is
# not semantically important; alphabetical for readability.
_DOMAIN_MODULES = (
    "affilipilot.cli.accesstrade",
    "affilipilot.cli.admin",
    "affilipilot.cli.facebook",
    "affilipilot.cli.observability",
    "affilipilot.cli.publish",
    "affilipilot.cli.scan",
    "affilipilot.cli.telegram",
    "affilipilot.cli.workflow",
)

_modules_loaded = False


def register(
    name: str,
    *,
    help: str,
    configure: Callable[[argparse.ArgumentParser], None] | None = None,
) -> Callable[[Callable[[argparse.Namespace], int]], Callable[[argparse.Namespace], int]]:
    """Decorator that registers a CLI subcommand.

    Args:
        name: subcommand name as the user types it (e.g. ``"profit-e2e"``).
        help: short help string shown by ``--help``.
        configure: optional function that receives the subparser and adds
            its ``--`` arguments. Omit for commands that take no arguments.
    """

    def _decorator(fn: Callable[[argparse.Namespace], int]) -> Callable[[argparse.Namespace], int]:
        _COMMANDS.append(_Command(name=name, help=help, configure=configure, handler=fn))
        return fn

    return _decorator


def _load_domain_modules() -> None:
    """Import every domain module so their @register decorators fire.

    Called lazily on first build_parser() invocation; safe to call multiple
    times (Python caches imports).

    After domain modules are loaded, the legacy bridge imports any commands
    still living in ``_cli_legacy`` that haven't been migrated yet.
    """
    global _modules_loaded
    if _modules_loaded:
        return
    for mod in _DOMAIN_MODULES:
        try:
            importlib.import_module(mod)
        except ModuleNotFoundError:
            # Domain module not yet created; that's fine during the migration.
            continue
    # Pull in everything else from the legacy parser.
    from affilipilot.cli._legacy_bridge import bridge_legacy_commands

    bridge_legacy_commands()
    _modules_loaded = True


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse parser with every registered command."""
    _load_domain_modules()
    parser = argparse.ArgumentParser(description="AffiliPilot Lite CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    # Sort for stable --help output. Registration order would also be stable
    # but alphabetical is friendlier for operators scanning the help text.
    for cmd in sorted(_COMMANDS, key=lambda c: c.name):
        p = sub.add_parser(cmd.name, help=cmd.help)
        if cmd.configure is not None:
            cmd.configure(p)
        p.set_defaults(func=cmd.handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Process argv and dispatch to the matching command handler."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


__all__ = ["register", "build_parser", "main"]
