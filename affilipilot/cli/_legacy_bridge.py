"""Bridge: import commands from the legacy ``_cli_legacy`` monolithic file into
the new registry-based parser.

Why this exists:
    Refactoring 70 command handlers into 8 domain modules in one PR is risky.
    Instead, we incrementally migrate. Already-migrated commands live in their
    own ``cli/<domain>.py`` module and register via ``@register``. Everything
    else is bridged from ``_cli_legacy`` here so the user-facing CLI stays
    backward-compatible during the migration.

How it works:
    1. Build the legacy argparse parser exactly as before.
    2. Iterate its subparsers, skipping any name already in the new registry
       (which would otherwise conflict).
    3. Re-register each surviving legacy command via ``register`` so it shows
       up in the unified ``build_parser`` output.

Migrating a command out of the bridge:
    - Move ``cmd_XYZ`` into the appropriate ``cli/<domain>.py`` module.
    - Decorate with ``@register("xyz", help=..., configure=...)``.
    - Delete the corresponding ``sub.add_parser("xyz", ...)`` block from
       ``_cli_legacy.build_parser`` (NOT the handler — keep the handler until
       all references are updated).
    - The bridge automatically stops bridging that command on next import.
"""
from __future__ import annotations

import argparse
from typing import Any

from affilipilot.cli._registry import _COMMANDS, register


def _registered_names() -> set[str]:
    return {cmd.name for cmd in _COMMANDS}


def _bridge_subparser(name: str, legacy_parser: argparse.ArgumentParser, handler: Any) -> None:
    """Register a single legacy subparser into the new registry.

    The legacy parser already knows its own arguments; we wrap it with a
    ``configure`` that recreates each argument on the new subparser preserving
    ``action``, ``dest``, ``nargs``, ``choices``, ``type``, ``default``,
    ``required``, and ``const``.
    """

    def _configure(new_parser: argparse.ArgumentParser) -> None:
        for action in legacy_parser._actions:  # noqa: SLF001
            if action.dest == "help":
                continue
            kwargs: dict[str, Any] = {"help": action.help, "default": action.default}

            # ``action`` keyword preserves _StoreTrueAction, _StoreFalseAction,
            # _AppendAction, _CountAction, ... by detecting subclass.
            if isinstance(action, argparse._StoreTrueAction):  # noqa: SLF001
                kwargs["action"] = "store_true"
            elif isinstance(action, argparse._StoreFalseAction):  # noqa: SLF001
                kwargs["action"] = "store_false"
            elif isinstance(action, argparse._AppendAction):  # noqa: SLF001
                kwargs["action"] = "append"
                if action.type is not None:
                    kwargs["type"] = action.type
            elif isinstance(action, argparse._CountAction):  # noqa: SLF001
                kwargs["action"] = "count"
            else:
                # Default _StoreAction. Preserve type/nargs/choices.
                if action.type is not None:
                    kwargs["type"] = action.type
                if action.nargs is not None:
                    kwargs["nargs"] = action.nargs
                if action.choices is not None:
                    kwargs["choices"] = action.choices
                if action.const is not None and not isinstance(action, argparse._StoreAction):  # noqa: SLF001
                    kwargs["const"] = action.const

            # ``required`` only valid for optional arguments.
            if action.option_strings and action.required:
                kwargs["required"] = True

            # ``dest`` is required when option_strings don't match dest naming.
            # argparse normally derives dest by replacing dashes with underscores,
            # but explicit ``dest=`` (as in --link dest="links") must be preserved.
            if action.option_strings:
                # Check whether dest matches the default derivation; if not,
                # we must pass dest= explicitly.
                derived = action.option_strings[0].lstrip("-").replace("-", "_")
                if action.dest != derived:
                    kwargs["dest"] = action.dest

            try:
                if action.option_strings:
                    new_parser.add_argument(*action.option_strings, **kwargs)
                else:
                    # Positional argument
                    new_parser.add_argument(action.dest, **kwargs)
            except (argparse.ArgumentError, TypeError):
                # Defensive: skip rather than break the entire CLI.
                continue

    register(name, help=legacy_parser.description or name, configure=_configure)(handler)


def bridge_legacy_commands() -> None:
    """Bring every legacy command into the new registry, except those already
    migrated to their own ``cli/<domain>.py`` module.
    """
    # Local import to avoid loading the legacy module unless bridging is needed.
    from affilipilot import _cli_legacy

    legacy_parser = _cli_legacy.build_parser()
    already_registered = _registered_names()

    # argparse stores the subparsers action as a single _SubParsersAction.
    subparsers_action = None
    for action in legacy_parser._actions:  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            subparsers_action = action
            break
    if subparsers_action is None:
        return

    for name, sub_parser in subparsers_action.choices.items():
        if name in already_registered:
            continue
        handler = sub_parser.get_default("func")
        if handler is None:
            continue
        # Use the subparser's description/prog as help text fallback.
        sub_parser.description = sub_parser.description or sub_parser.format_help().splitlines()[0]
        _bridge_subparser(name, sub_parser, handler)
