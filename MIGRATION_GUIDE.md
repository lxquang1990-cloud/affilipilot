# AffiliPilot CLI Migration Guide

This document tracks the progress of migrating the monolithic `cli.py`
(1367 lines, 70 handlers, 76KB) into modular domain packages under
`affilipilot/cli/`.

## Status snapshot

| Domain module | Commands migrated | LOC | Status |
|---|---|---|---|
| `cli/observability.py` | 6 | 132 | ✅ Done |
| `cli/facebook.py` | 4 | 184 | ✅ Done |
| `cli/accesstrade.py` | 7 | 257 | ✅ Done |
| `cli/scan.py` | 0 | — | ⏳ TODO |
| `cli/workflow.py` | 0 | — | ⏳ TODO |
| `cli/telegram.py` | 0 | — | ⏳ TODO |
| `cli/publish.py` | 0 | — | ⏳ TODO |
| `cli/admin.py` | 0 | — | ⏳ TODO |
| **Total migrated** | **17 / 69** | — | **25%** |

The remaining 52 commands still live in `affilipilot/_cli_legacy.py` and are
brought into the unified registry via `affilipilot/cli/_legacy_bridge.py`.
The bridge will continue to work indefinitely — there is no deadline.

## Migration recipe (per command)

Pick a command from the legacy file. Follow these steps in order:

### 1. Identify the right domain module

| Command prefix / theme | Target module |
|---|---|
| `accesstrade-*` | `cli/accesstrade.py` ✅ |
| `facebook-*`, `publish-safe` | `cli/facebook.py` ✅ |
| `event-log`, `circuit-*`, `kill-switch`, `score-tier`, `conversion-*` | `cli/observability.py` ✅ |
| `scan-*`, `discover-*`, `enrich-*`, `browser-*`, `quality-gate`, `marketplace-classify` | `cli/scan.py` |
| `profit-e2e`, `multi-source-*`, `channel-approval`, `discover-convert`, `run-day`, `draft-links`, `sprint0` | `cli/workflow.py` |
| `*telegram*`, `outbox`, `queue-telegram`, `mark-*`, `handle-text` | `cli/telegram.py` |
| `ready-*`, `approve-ready`, `publish-status`, `record-publish-event`, `validate-input` | `cli/publish.py` |
| `health`, `doctor`, `readiness`, `init-secrets`, `record-spend`, `digest`, `next-action`, `campaign-status`, `strategy`, `demo-happy-path`, `batch-*`, `create-batch`, `decide`, `status`, `market-fit`, `content-variants`, `offer-validate`, `performance-*` | `cli/admin.py` |

### 2. Move the handler

Cut `cmd_<name>(args)` from `_cli_legacy.py` into the target module.
**Do not delete** from `_cli_legacy.py` until step 4 confirms the migration.

### 3. Write a `_configure` function

Cut the corresponding `sub.add_parser("<name>", ...)` block from
`_cli_legacy.build_parser()` and turn it into a configure function:

```python
def _configure_my_command(p: argparse.ArgumentParser) -> None:
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="data/...")
    # ... preserve every option exactly as it was

@register("my-command", help="...the original help text...", configure=_configure_my_command)
def cmd_my_command(args: argparse.Namespace) -> int:
    # body unchanged from legacy
    return 0
```

### 4. Verify

```bash
PYTHONPATH=. python3 -m pytest -q   # must stay green
PYTHONPATH=. python3 -m affilipilot my-command --help   # must show expected args
```

If both pass, **then** delete the original `cmd_<name>` and `sub.add_parser`
block from `_cli_legacy.py`. The bridge automatically detects that the
command is in the new registry and skips re-registering it.

### 5. Update import side

If the handler called other handlers (e.g. `cmd_publish_safe` reuses
`cmd_facebook_publish_one`), update the import accordingly:

```python
from affilipilot.cli.facebook import cmd_facebook_publish_one
```

## Common patterns

### Commands that reuse other handlers

`publish-safe` calls `cmd_facebook_publish_one` directly. Two clean options:
- **Composition**: import the new handler from `cli.facebook`.
- **Extraction**: extract shared logic into a helper, call from both handlers.

### Commands with `dest=` argparse tricks

E.g. `accesstrade-convert` uses `--real dest="dry_run" action="store_false"`
with `set_defaults(dry_run=True)`. Preserve this exactly:

```python
def _configure_convert(p):
    p.add_argument("--real", dest="dry_run", action="store_false",
                   help="Call real Accesstrade API")
    p.set_defaults(dry_run=True)
```

See `cli/accesstrade.py:cmd_accesstrade_convert` for the working pattern.

### Commands with `action="append"` repeatable flags

E.g. `draft-links` uses `--link dest="links" action="append"`. Preserve `dest`:

```python
p.add_argument("--link", dest="links", action="append", default=[],
               help="Inline product line. Repeat for multiple products.")
```

## Removing the bridge (final step)

Once **every** command has its own `@register` decorator and
`_cli_legacy.py` no longer contains any `sub.add_parser` calls:

1. Delete the import of `_legacy_bridge` from `cli/_registry.py:_load_domain_modules`.
2. Delete `affilipilot/_cli_legacy.py`.
3. Delete `affilipilot/cli/_legacy_bridge.py`.
4. Update `affilipilot/cli/__init__.py` to drop the backward-compat re-exports
   (`publish_post`, `publish_photo_post`, etc.) if no test still patches them.
5. Run the test suite one last time.

Expected result: `affilipilot/cli/__init__.py` ~30 lines, `_registry.py` ~80 lines,
and 8 domain modules each ~150-250 lines. Compared to the original `cli.py`
(1367 lines), the largest file in the CLI layer drops by ~80%.
