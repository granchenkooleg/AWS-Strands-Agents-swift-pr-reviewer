# NEXT.md — Handoff state

Read `CLAUDE.md` first; this file captures only what's *not yet in there*
and what the next session should pick up.

## Status

- [x] **Slice 1** — single Correctness reviewer over PR 001.
- [x] **Slice 2** — Style, ApiDesign, TestCoverage reviewers added; sequential run.
- [x] **Slice 3** — Strands `Graph` replaces the sequential loop. Parallel fan-out.
- [x] **Slice 4** — MCP diff-loader, RunLogger hook, report-writer Agent with
      `swift-review-rubric` skill, HITL interrupt via `BeforeNodeCallEvent`.
- [ ] **Slice 5** — Evals, observability (OTEL → CloudWatch), Bedrock provider,
      submission artifacts (ARCHITECTURE.md, reflection.md, screenshots).

## Slice 4 audit notes (already applied)

The audit on 2026-05-10 fixed CLAUDE.md drift and deleted four dead reviewer
modules (`{correctness,style,api_design,test_coverage}_reviewer.py`) that the
Slice 3 Graph rewrite had orphaned. Also removed the `load_pr_diff` `@tool`
from `parse_diff.py` (no caller — MCP path superseded it).

If you find a stale reference to those modules, fix it; the architecture is
now: agents constructed inline in `app/graph.py` from `_REVIEWER_CONFIGS` +
steering markdown.

## Slice 5 work, in priority order

1. **Eval corpus** — the load-bearing 4 hours of slice 5. Add ~9 more PRs to
   `data/prs/`. Each needs `pr.diff` + `metadata.json` + `ground_truth.json`.
   Cover: retain cycle, missing `[weak self]` in Combine sink, public API
   breakage, missing test for new branch, naming style violation,
   no-finding-clean-PR (precision check), unused public symbol, incorrect
   `@MainActor` annotation, integer overflow on user input.

2. **Eval harness** — `evals/run_evals.py` over the corpus.
   Metrics: recall (expected findings caught), precision (FP rate),
   severity match rate. Use `strands-evals` if its 0.0.1 API is workable;
   otherwise write a thin custom harness — the corpus is the deliverable,
   not the harness.

3. **Observability** — `app/observability/otel.py`. Wire AWS Distro for
   OTel; export Strands spans + `RunLogger`-derived custom metrics
   (`findings_per_pr`, `agent_latency_ms`). Take CloudWatch dashboard
   screenshots, then disable to avoid metric cost.

4. **Bedrock provider** — flip the `NotImplementedError` branch in
   `app/provider.py` to a real `BedrockModel`. Verify model availability
   in your AWS region first.

5. **Submission deliverables**:
   - `ARCHITECTURE.md` — DAG diagram (Mermaid), design rationale.
   - `submission/reflection.md` — what worked, what was forced (the MCP
     diff-loader, the synchronous CLI HITL), what'd change in v2.
   - `submission/screenshots/` — CLI run, CloudWatch dashboard, eval report.

## Outstanding architectural notes

- **`Hunk.start_line` and `Hunk.line_count` are written but never read.**
  Trim from the model when convenient. Harmless padding today.
- **`RunLogger` only emits invocation-level events** — no tool-call or
  model-call events. Acceptable for the current rubric needs; extend if
  the observability dashboard demands more granularity.
- **Two Graphs per run** (reviewer fan-out + report-writer-with-HITL) is
  intentional. The diff-loader Agent runs outside any Graph. Documented in
  CLAUDE.md's architecture diagram.

## Open questions still unresolved

- AWS region + Bedrock model ID for your account — verify before slice 5.
- ADOT-to-CloudWatch wiring on macOS — local OTEL collector may be needed.
  Document the exact setup once verified.
- `strands-evals` 0.0.1 API surface — install and inspect when you start.

## Don't forget

- `BYPASS_TOOL_CONSENT=true` for non-interactive eval runs.
- No `swiftlint`, `xcodebuild`, or shell tools — see CLAUDE.md "Things to NOT do".
- Steering changes go in `app/agents/_steering/*.md`, never inline as Python strings.
- After any architectural change, re-run `python -m app.main --pr data/prs/001_force_unwrap`
  to make sure the green path still works before claiming a slice complete.
