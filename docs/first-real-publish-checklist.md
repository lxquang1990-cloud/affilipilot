# First Real Publish Checklist

Use this checklist before the first real Facebook publish from AffiliPilot.

## Hard stop conditions

Do **not** publish if any item below is false:

- [ ] Snail explicitly approved this real publish attempt.
- [ ] The post is safe to publish on the target page.
- [ ] `scripts/verify_all.sh` passes.
- [ ] `python3 -m affilipilot readiness` shows Facebook token check config ready.
- [ ] `python3 -m affilipilot facebook-token-check` passes.
- [ ] The target post status is `approved` in SQLite.
- [ ] The post has compliance status `pass`.
- [ ] The post has affiliate disclosure text.
- [ ] The product link is an affiliate/tracking link, not a raw/untracked product URL.
- [ ] The post has media or a validated media fallback.
- [ ] `approve-ready` generated `facebook-plan.json`.
- [ ] The exact post in `facebook-plan.json` has status `publishable_dry_run`.
- [ ] The plan endpoint/payload look correct.
- [ ] Output result path is unique and under `data/publish/`.

## Commands

### 1. Verify project

```bash
cd /home/snail/.openclaw/workspace/affilipilot
scripts/verify_all.sh
```

### 2. Check readiness

```bash
python3 -m affilipilot readiness
python3 -m affilipilot facebook-token-check
```

### 3. Inspect batch

```bash
python3 -m affilipilot batch-status \
  --db data/affilipilot.db \
  --batch-key <batch-key> \
  --facebook-plan <path-to-facebook-plan.json>
```

### 4. Real publish exactly one post

```bash
python3 -m affilipilot facebook-publish-one \
  --plan <path-to-facebook-plan.json> \
  --post-id <post-id> \
  --out data/publish/<batch-key>-<post-id>-result.json
```

## Post-publish checks

- [ ] Result JSON has `ok: true`.
- [ ] Facebook response includes a post/photo ID.
- [ ] The published post appears correctly on the page.
- [ ] Caption, disclosure, image/media, and link are correct.
- [ ] Save the result JSON under `data/publish/`.
- [ ] Run `python3 scripts/secret_scan.py` after publish result is saved.

## Rollback / remediation

If the post is wrong:

1. Delete or hide the Facebook post manually or via a guarded delete command if available.
2. Save the delete/hide result JSON under `data/publish/`.
3. Mark the local post decision as `needs_edit` or `rejected`.
4. Record the incident in project notes.

Never mass-publish after the first success. Publish one post, inspect, then decide next increment.
