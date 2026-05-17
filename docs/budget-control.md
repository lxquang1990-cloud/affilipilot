# Budget Control

Default daily LLM/API budget for Sprint 1: 30,000 VND.

## Modes

- `normal`: spent < 80% cap.
- `cheap_model_only`: spent >= 80% cap.
- `hard_stop`: spent >= 100% cap.

## CLI

```bash
PYTHONPATH=. python3 -m affilipilot record-spend \
  --path data/budget/today.json \
  --phase draft \
  --amount 5000 \
  --cap 30000
```

The workflow should stop or ask for user decision when mode becomes `hard_stop`.
