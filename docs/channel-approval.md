# Channel Approval — simplified operator flow

`channel-approval` is the short path from a marketplace channel/listing URL to a local approval batch.

It performs:

```text
channel/listing URL
→ Playwright browser discovery
→ product-detail URLs only
→ Accesstrade conversion
→ draft generation
→ local media preparation
→ quality/ready preview
→ local Telegram outbox queue
```

It does **not** send Telegram messages and does **not** publish Facebook posts.

## Example

```bash
. .venv/bin/activate
PYTHONPATH=. python -m affilipilot channel-approval \
  --url 'https://www.lazada.vn/tag/khan-sua-em-be/' \
  --batch-key lazada-khan-sua-$(date +%Y%m%dT%H%M%S) \
  --work-dir data/runs/lazada-khan-sua-channel-approval \
  --source LAZADA \
  --category baby_care \
  --campaign-key LAZADA \
  --limit 3
```

Default conversion is dry-run. Add `--real` only when ready to call Accesstrade.

## Next steps after command

```bash
python -m affilipilot outbox --outbox data/outbox/telegram.json
python -m affilipilot openclaw-telegram-send --outbox data/outbox/telegram.json --reply-to 640968010 --account default --limit 2
python -m affilipilot campaign-status --batch-key <batch_key>
python -m affilipilot publish-safe --batch-key <batch_key> --post-id <post_id> --check-only
```

Real publish still requires explicit final confirmation.
