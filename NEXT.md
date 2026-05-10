# NEXT.md — Handoff state

Slice 1 (single Correctness reviewer over PR 001) is complete and smoke-tested.
Read `CLAUDE.md` first; this file captures only what's *not yet in there*.

## SDK corrections discovered during slice 1

Apply these when you next touch CLAUDE.md (after slice 2 is green, per the
refactor-after-green rule):

- **Use `Agent(structured_output_model=ReviewerOutput, ...)`** — Strands enforces
  the schema and re-prompts on validation failure natively. The hand-rolled
  Pydantic retry loop sketched in CLAUDE.md row #8 is **not needed**; delete
  it from the concept map. Reviewer output is read via `result.structured_output`.
- **Hook events live at top-level `strands.hooks`** — `BeforeInvocationEvent`,
  `AfterInvocationEvent`, `BeforeToolCallEvent`, **`AfterToolCallEvent`**
  (not `AfterToolInvocationEvent` — docs page is stale).
- **No `Workflow` class** in `strands.multiagent`. Only `GraphBuilder` and `Swarm`.
  Confirms our Graph choice; nothing to change.
- **Strands ships model providers**: `from strands.models.anthropic import AnthropicModel`,
  `from strands.models.bedrock import BedrockModel`. Already wired in `app/provider.py`.
- **`strands-agents 1.39.0`** is the current PyPI version. Pin in `requirements.txt`
  before submission.

## Local dev setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add ANTHROPIC_API_KEY to .env
python -m app.main --pr data/prs/001_force_unwrap
```

Expected: 2 blocker findings (the two force-unwraps at L15 and L19).
The L13 API-break finding won't appear until slice 2 lands the api_design reviewer.

## Slice plan

- [x] **Slice 1** — One reviewer (Correctness), one PR, CLI entry. *Done.*
- [ ] **Slice 2** — Add Style, ApiDesign, TestCoverage reviewers. Sequential
      loop in `main.py` (no Graph yet). Each reviewer = its own steering file
      + its own `app/agents/<name>_reviewer.py`. Aggregator dedup is a plain
      Python function for now.
- [ ] **Slice 3** — Replace the sequential loop with `GraphBuilder`.
      Parallel fan-out at the reviewer stage. This is where the homework's
      multi-agent rubric item lands.
- [ ] **Slice 4** — HITL via `BeforeNodeCallEvent` interrupt on the
      report-writer node. Hooks (`BeforeInvocationEvent` / `AfterInvocationEvent`)
      writing JSONL to `runs/<run_id>.jsonl`. Skill activation: aggregator
      activates `swift-review-rubric`. MCP: filesystem MCP serving `data/prs/`.
- [ ] **Slice 5** — Evals (`evals/run_evals.py` over the corpus, recall +
      precision). Observability: OTEL → CloudWatch. Bedrock provider enabled
      for AWS console screenshots. Submission deliverables: ARCHITECTURE.md,
      reflection.md, screenshots.

## Things to grow before slice 5

The eval corpus is the real bottleneck. By the time slice 4 ships, you need
~10 PRs in `data/prs/` covering: force-unwrap, retain cycle, missing weak self
in Combine sink, public API breakage, missing test for new branch, naming
style violation, no-finding-clean-PR (precision), unused public symbol,
incorrect `@MainActor` annotation, integer overflow on user input.

Each PR = `pr.diff` + `metadata.json` + `ground_truth.json`. Plan ~30 min per
PR; that's the load-bearing 4 hours of the homework, not the Strands wiring.

## Open questions still unresolved

- AWS region + Bedrock model ID for your account — verify before slice 5.
- ADOT-to-CloudWatch wiring on macOS — local OTEL collector may be needed.
  Document the exact setup once verified.
- `strands-evals` package layout — install and inspect when slice 5 starts.

## Don't forget

- `BYPASS_TOOL_CONSENT=true` for non-interactive eval runs (community tool
  consent prompts otherwise block).
- Don't reach for `swiftlint`, `xcodebuild`, or shell tools — see CLAUDE.md
  "Things to NOT do".
- Steering changes go in `app/agents/_steering/*.md`, never inline as Python
  strings.
