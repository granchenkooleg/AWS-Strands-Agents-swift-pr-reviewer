# Evals

Run with:

```bash
python -m evals.run_evals
```

Loads every PR under `data/prs/`, runs the full review graph, and scores
findings against `ground_truth.json` for each case.

Metrics emitted:
- **Recall** — fraction of expected findings that were caught
- **Precision** — fraction of emitted findings that match expected (FP rate)
- **Severity match rate** — when a finding is caught, how often is severity correct
- **JSON validity rate** — how often each reviewer emits valid Pydantic-conforming output without retry

See `evaluators.py` for the evaluator implementations.
