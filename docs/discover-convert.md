# Discover Convert Workflow

`discover-convert` connects Phase C discovery with Phase B conversion preflight.

It performs:

```text
browser-discover channel/listing page
→ write discovered product-detail input
→ accesstrade-convert only product-detail URLs
→ write converted input
```

It does **not** draft, send approvals, or publish.

## Lazada example

```bash
. .venv/bin/activate
PYTHONPATH=. python -m affilipilot discover-convert \
  --url 'https://www.lazada.vn/tag/khan-sua-em-be/' \
  --source LAZADA \
  --category baby_care \
  --campaign-key LAZADA \
  --work-dir data/runs/lazada-khan-sua-discover-convert \
  --limit 5
```

Default is dry-run conversion. Add `--real` only when ready to call Accesstrade.

## Outputs

```text
discovered-products.json
discovered-products.input.txt
discovered-products.converted.json
discovered-products.converted.txt
discover-convert-summary.json
```

## Safety

- Channel/search/tag URLs are never converted directly.
- Only discovered product-detail URLs enter conversion.
- Failed conversion rows are not written to `discovered-products.converted.txt`.
- No Facebook publish side effects.
