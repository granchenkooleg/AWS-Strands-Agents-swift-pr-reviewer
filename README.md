# Swift PR Reviewer

A Strands Agents prototype that reviews Swift pull requests. Four specialized
reviewer agents run in parallel over a unified diff, an aggregator merges their
findings, a human approves which findings ship, and the result is written to a
markdown report.

This is the AWS – Strands Agents homework deliverable.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in credentials
python -m app.main --pr data/prs/001_force_unwrap
```

## Documentation

- [`CLAUDE.md`](./CLAUDE.md) — architecture, conventions, and homework concept map (read this first if you're working on the code)
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — diagrams and design rationale (TODO)
- [`evals/README.md`](./evals/README.md) — eval methodology and results (TODO)

## Status

Scaffold only. No implementation yet — see CLAUDE.md for the build plan.
