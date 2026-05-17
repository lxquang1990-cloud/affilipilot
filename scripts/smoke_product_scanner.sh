#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

TMP="$(mktemp -d)"
cat > "$TMP/sample.html" <<'HTML'
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Bình giữ nhiệt cho mẹ","image":"/img/a.jpg","url":"/binh-giu-nhiet","offers":{"@type":"Offer","price":"129000"}}
</script>
</head><body>
<a class="product" href="/khuyen-mai/yem-an-dam"><img src="/img/b.jpg" alt="Yếm ăn dặm silicone"/><span>79.000đ</span></a>
</body></html>
HTML

PYTHONPATH=. python3 - <<PY
from pathlib import Path
from affilipilot.scanner.core import scan_url, write_scan_result
html = Path('$TMP/sample.html').read_text()
result = scan_url('https://cellphones.com.vn/danh-sach-khuyen-mai', source='CELLPHONES', category='deal', limit=2, html_text=html)
write_scan_result(result, '$TMP/scan.json')
print(f'scanned={len(result.items)}')
PY

PYTHONPATH=. python3 -m affilipilot scan-draft \
  --scan "$TMP/scan.json" \
  --work-dir "$TMP/work" \
  --db "$TMP/affilipilot.db" \
  --batch-key scanner-smoke \
  --outbox "$TMP/outbox.json" \
  --limit 2 | tee "$TMP/scan-draft.out"

grep -q "Products: 2 considered, 2 selected" "$TMP/scan-draft.out"
test -s "$TMP/outbox.json"
echo "AffiliPilot product scanner smoke: PASS"
