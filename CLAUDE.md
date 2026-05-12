# CLAUDE.md — Operating manual for `swift-pr-reviewer`

This file is the contract between any agent (human or model) and this codebase.
Read it before touching code. Update it when architecture changes.

**Also read [`NEXT.md`](./NEXT.md)** — captures current slice state, SDK
corrections discovered after this file was written, and the slice plan.

## Purpose & scope

A Strands Agents prototype that reviews Swift pull requests. Built as the
AWS – Strands Agents homework deliverable; intentionally scoped to one
narrow domain so every Strands concept lands in a defensible place rather
than a contrived one.

**Out of scope** for v1: real GitHub integration, swiftlint invocation,
async webhooks, Xcode project parsing, multi-language support. Anything
adjacent that doesn't earn its place against the rubric stays out.

## Architecture at a glance

```
   ┌──────────────┐
   │ DiffLoader   │  ← Strands Agent over a filesystem MCP server (npx
   │  (Strands    │     @modelcontextprotocol/server-filesystem). Reads
   │   Agent)     │     pr.diff. Called from main.py, NOT inside a Graph.
   └──────┬───────┘     Direct-read fallback if MCP fails.
          │ raw diff text
          ▼
   parse_unified_diff (pure Python, `unidiff`) → List[Hunk]
          │
          ▼
   ┌────────────────── Strands Graph #1 (reviewer fan-out) ──────────────────┐
   │  ┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐      │
   │  │ Correctness  ││    Style     ││  ApiDesign   ││ TestCoverage │      │
   │  │   Reviewer   ││   Reviewer   ││   Reviewer   ││   Reviewer   │      │
   │  └──────┬───────┘└──────┬───────┘└──────┬───────┘└──────┬───────┘      │
   │         └──────────────┬─┴────────────────┴───────────────┘ (no edges) │
   │       4 nodes, no edges → executed in parallel by the GraphBuilder     │
   └────────────────────────────────┬───────────────────────────────────────┘
                                    │ List[ReviewerOutput]
                                    ▼
                          aggregator.aggregate(...)
                          plain Python: dedup by (file, line, category),
                          keep higher severity, sort. No Agent.
                                    │ List[Finding]
                                    ▼
   ┌────────────────── Strands Graph #2 (report-writer + HITL) ─────────────┐
   │  BeforeNodeCallEvent on `report-writer` → event.interrupt(...)         │
   │  Graph returns Status.INTERRUPTED → main.py prompts user → resumes.    │
   │  ┌──────────────────────────────────────────────────────────────┐     │
   │  │ ReportWriter Agent — activates `swift-review-rubric` skill,  │     │
   │  │ uses `current_time` community tool, emits markdown report.   │     │
   │  └──────────────────────────────────────────────────────────────┘     │
   └────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          Rich-rendered markdown to stdout
                          JSONL trace at runs/<run_id>.jsonl
```

**Pattern: Strands `Graph`** (not Workflow). The reviewer stage is a DAG of
4 parallel nodes with no edges — `GraphBuilder` runs them concurrently.
The HITL gate is implemented as a `BeforeNodeCallEvent` on a second
single-node graph wrapping the report-writer. Two graphs in one run is
intentional: it isolates the HITL interrupt to the writer stage so a
reviewer failure can't trap a half-completed graph.

The diff-loader Agent sits *outside* the graph because it has no
downstream agent dependency — parsing is pure Python, and threading an
agent-level node through just to read a file added complexity for no
homework or production benefit.

## Tech stack

- Python 3.11+ (uses `match`, PEP 604 unions)
- `strands-agents` 1.39.x — `Agent`, `AgentSkills`, `Skill`, `tool`
- `strands-agents-tools` — `current_time` is the only community tool we wire
- `mcp` Python client + a local stdio filesystem MCP server (Node, via `npx`)
- `unidiff` for parsing — never hand-roll diff parsing
- `pydantic>=2.6` for every data contract that crosses an agent boundary
- `anthropic` for the local-dev provider; `boto3` for the Bedrock provider
  (slice 5). Selected at runtime by `STRANDS_PROVIDER`.
- AWS Distro for OpenTelemetry → CloudWatch Logs/Metrics (slice 5)
- `strands-evals` (slice 5; PyPI 0.0.1 today)

## Directory map

```
swift-pr-reviewer/
├── CLAUDE.md                       ← you are here
├── NEXT.md                         ← slice handoff state (read after this)
├── README.md                       ← user-facing setup
├── requirements.txt
├── .env.example
│
├── app/
│   ├── main.py                     ← CLI entry; orchestrates the two graphs
│   ├── graph.py                    ← run_reviewers() + build_report_writer_graph()
│   ├── models.py                   ← Pydantic: AddedLine, Hunk, Finding, etc.
│   ├── provider.py                 ← Anthropic provider; Bedrock stubbed for slice 5
│   │
│   ├── agents/
│   │   ├── diff_loader.py          ← MCP-filesystem reader Agent
│   │   ├── aggregator.py           ← plain Python dedup + sort (NOT an Agent)
│   │   ├── report_writer.py        ← Strands Agent: skill + current_time tool
│   │   └── _steering/              ← system prompts per agent (markdown)
│   │       ├── correctness.md
│   │       ├── style.md
│   │       ├── api_design.md
│   │       ├── test_coverage.md
│   │       └── report_writer.md
│   │
│   ├── tools/
│   │   └── parse_diff.py           ← parse_unified_diff() pure function (no @tool)
│   │
│   ├── hooks/
│   │   ├── instrumentation.py      ← RunLogger: BeforeInvocation/AfterInvocation
│   │   └── approval.py             ← ApprovalHook: BeforeNodeCallEvent + interrupt
│   │
│   └── observability/              ← slice 5: empty stub today
│
├── skills/
│   └── swift-review-rubric/
│       └── SKILL.md                ← rubric the report-writer activates
│
├── data/
│   └── prs/
│       └── 001_force_unwrap/
│           ├── pr.diff             ← input
│           ├── metadata.json       ← input
│           └── ground_truth.json   ← evals only — agents never see this
│
├── evals/                          ← slice 5: README only today
│   └── README.md
│
├── outputs/                        ← report.md per run (gitignored)
└── runs/                           ← JSONL trace per run (gitignored)
```

The reviewer Agent objects are constructed inline in `app/graph.py` from
`_REVIEWER_CONFIGS` + the steering files. There is no `correctness_reviewer.py`
file — the agent **is** the steering markdown plus the Graph node config.

## Run commands

```bash
# Dev — Anthropic provider, single PR
STRANDS_PROVIDER=anthropic python -m app.main --pr data/prs/001_force_unwrap

# Eval — runs every PR under data/prs/
python -m evals.run_evals

# AWS demo (for screenshots) — Bedrock, OTEL on
STRANDS_PROVIDER=bedrock OTEL_SERVICE_NAME=swift-pr-reviewer \
    python -m app.main --pr data/prs/001_force_unwrap

# Non-interactive (eval / CI) — bypass community-tool consent prompts
BYPASS_TOOL_CONSENT=true python -m evals.run_evals
```

## Data contracts

Every agent boundary is a Pydantic model — see `app/models.py` for the
authoritative definitions. Models live there, not duplicated here.

Roughly: `AddedLine` and `Hunk` describe the diff after parsing.
`Finding` is what a reviewer emits per issue. `ReviewerOutput` wraps a
reviewer's full per-PR output. `ReviewReport` is the final post-aggregation,
post-HITL package (not currently persisted; we render markdown directly).

**Hard rule:** reviewer agents emit `ReviewerOutput` only — Strands enforces
the schema via `Agent(structured_output_model=ReviewerOutput, ...)` and
re-prompts the model on validation failure. We do not fail the run on a
single broken reviewer; the others still produce signal (graph-level
fail-soft in `run_reviewers()`).

## Homework concept map — where each requirement lives

| # | Requirement | File / module | Status |
|---|---|---|---|
| 1 | Agent anatomy (model, prompt, memory, tools) | 6 agents total: 4 reviewers built inline in `app/graph.py` from `_REVIEWER_CONFIGS` + `_steering/*.md`, plus `app/agents/diff_loader.py` and `app/agents/report_writer.py`. Each is a `strands.Agent` with `system_prompt`, model from `app/provider.py`, optional tools, hooks. | ✅ |
| 2 | Community tool from `strands-agents-tools` | `from strands_tools import current_time` in `app/agents/report_writer.py` — wired into the report-writer Agent so it can stamp the report header. No other community tools are wired (we kept the surface minimal). | ✅ |
| 3 | MCP server | Local filesystem MCP via stdio. `app/agents/diff_loader.py` constructs `MCPClient(lambda: stdio_client(StdioServerParameters(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", str(pr_dir)])))` scoped per-PR. Direct-read fallback in `app/main.py:_load_pr` if MCP launch fails. | ✅ |
| 4 | Skill | `skills/swift-review-rubric/SKILL.md` — wired via `AgentSkills(skills=[str(_SKILLS_DIR)])` plugin on the **Report Writer** agent in `app/agents/report_writer.py`. Steering tells the writer to activate the skill *before* formatting. | ✅ |
| 5 | Steering | `app/agents/_steering/{correctness,style,api_design,test_coverage,report_writer}.md`. Hard rules every reviewer enforces: "only comment on changed lines", "cite post-change line numbers exactly", "severity ∈ {blocker, major, minor, nit}", "never invent code not in the hunk". | ✅ |
| 6 | Hook | `app/hooks/instrumentation.py` — `RunLogger` HookProvider registering `BeforeInvocationEvent`/`AfterInvocationEvent`. Writes one JSONL line per agent invocation to `runs/<run_id>.jsonl` with `(agent, latency_ms, input_tokens, output_tokens)`. | ✅ |
| 7 | Interrupt (HITL) | `app/hooks/approval.py` — `ApprovalHook` registers `BeforeNodeCallEvent` on the report-writer node. Raises `event.interrupt("review-approval", reason={"findings": [...]})`. Main loop in `app/main.py` prompts per finding, resumes the graph with accepted/rejected decisions. Also registers `BeforeInvocationEvent` to replace the agent's task with only the accepted findings on resume. | ✅ |
| 8 | Retries | Strands' built-in `structured_output_model=ReviewerOutput` enforces the Pydantic schema and re-prompts on validation failure — no hand-rolled retry loop. Graph-level fail-soft: a reviewer that throws is logged and skipped; other reviewers' findings still flow. | ✅ |
| 9 | Multi-agent pattern | Strands **Graph** in `app/graph.py`. Two single-stage graphs in one run: (a) `run_reviewers()` — 4 parallel reviewer nodes, no edges, all execute concurrently; (b) `build_report_writer_graph()` — single `report-writer` node with graph-level hooks for the HITL interrupt. The diff-loader Agent and aggregator function run outside any Graph. | ✅ |
| 10 | Evaluations | Slice 5 — not yet implemented. Plan: `evals/run_evals.py` loads every `data/prs/*/ground_truth.json`, runs the pipeline, computes recall/precision/severity-match. Need ~10 PR fixtures before this is meaningful. | ⏳ slice 5 |
| 11 | Observability | Slice 5 — `app/observability/` is an empty stub today. Plan: AWS Distro for OTel → CloudWatch, custom metrics on top of `RunLogger` data. | ⏳ slice 5 |

## Conventions

- **Pydantic everywhere across agent boundaries.** No `dict[str, Any]` payloads.
- **Reviewer agents emit `ReviewerOutput` only** via `structured_output_model`.
  Strands re-prompts on schema failure; no hand-rolled retry.
- **No global state.** Run state is threaded as locals through `main.py` and
  via Strands `invocation_state` for graph-scoped data (e.g. the findings
  payload the ApprovalHook reads in `BeforeNodeCallEvent`).
- **No swiftlint, no shell out to git, no network calls at runtime** other than
  the model API and the MCP server. The PR is a static directory under `data/prs/`.
- **Steering rules live in markdown** under `app/agents/_steering/`. Loaded at
  agent construction time. Edit those, not Python strings, to tune behavior.
- **All hook output is JSONL**, one line per event, fields stable. Tooling
  greps over it; do not break the schema without bumping a version field.

## Adding a new reviewer agent

1. Add a steering file at `app/agents/_steering/<name>.md`.
2. Add a tuple to `_REVIEWER_CONFIGS` in `app/graph.py`:
   `("<node_id>", "<name>.md", "<name>-reviewer")` — order is preserved in
   result extraction so insertion order matters for stable diffs.
3. Bump `set_max_node_executions` in `run_reviewers()` to the new count.
4. Add the new value to the `Category` literal in `app/models.py`.
5. Add at least 2 ground-truth findings of the new category to `data/prs/*/ground_truth.json`.
6. Re-run evals (slice 5); commit the precision/recall delta.

If you skip step 5–6 you have no signal that the new reviewer works.
There is **no** `app/agents/<name>_reviewer.py` file — the agent is the
steering markdown plus the `_REVIEWER_CONFIGS` entry. Slice 1–2 had per-reviewer
Python modules; slice 3 collapsed them into the Graph and the leftovers were
deleted during the slice-4 audit.

## Failure modes & limits we accept

- **Bedrock model gating** (slice 5). The exact `BEDROCK_MODEL_ID` may not be
  enabled in your AWS region. `app/provider.py` raises `NotImplementedError`
  today; when slice 5 enables the branch it will fail clearly on first call.
- **Diff parser edge cases.** `unidiff` handles renames, binary files, and
  `\\ No newline at EOF` correctly; do not "improve" with regex.
- **Aggregator dedup is heuristic.** Same `(file, line, category)` from two
  reviewers gets merged taking the higher severity. Cross-category overlaps
  (e.g. a force-unwrap that's also bad style) deliberately stay separate.
- **The HITL gate is synchronous CLI.** In a real iOS frontend it'd be an
  async webhook with the agent suspended via `session_manager`. Worth naming
  in the submission reflection — it's a limitation, not a bug.
- **The MCP diff-loader is largely decorative.** An LLM-driven file read
  with a direct-read fallback is doing nothing `pr_dir / "pr.diff" .read_text()`
  couldn't. It exists for rubric #3 and is an honest forced use — call it out
  in the reflection rather than pretending it adds value.
- **CloudWatch cost** (slice 5). Custom metrics are ~$0.30/metric/month plus
  dimensions. Enable for the demo, take screenshots, then disable.

## Things to NOT do

- Don't invoke `swiftlint`, `xcodebuild`, or any external Swift tool. We are
  pure-LLM with steering. Adding swiftlint fights the rubric (zero credit) and
  adds an OS dependency reviewers won't have.
- Don't use `strands_tools.shell` or `python_repl`. They have no place here
  and pull in safety prompts we don't want.
- Don't fetch PRs from GitHub at runtime. The corpus is static.
- Don't mutate `Finding` post-aggregation. The HITL gate filters; it does not edit.
- Don't introduce a second MCP server to "pad" requirement #3. One natural one
  is enough; padding is visible.
- Don't write test fixtures into `data/prs/`. That folder is the demo corpus
  only. Eval-internal fixtures go in `evals/fixtures/`.
- Don't ask the model to emit markdown directly. Always Pydantic JSON →
  formatter. The skill formats; the model never does.

## Verification checklist before submission

- [ ] All 11 rubric items have a checkable artifact (file, screenshot, or eval result)
- [ ] `evals/run_evals.py` passes with recall ≥ 0.8 and precision ≥ 0.8 on the corpus
- [ ] `runs/` contains a JSONL from a Bedrock run with non-empty traces
- [ ] CloudWatch dashboard screenshot in `submission/screenshots/`
- [ ] `ARCHITECTURE.md` has the DAG diagram (Mermaid is fine)
- [ ] README setup steps work on a clean clone in under 10 minutes
- [ ] No `BYPASS_TOOL_CONSENT=true` in committed shell history or notebooks
- [ ] `.env` is gitignored; only `.env.example` is committed
- [ ] Reflection in `submission/reflection.md` notes: what worked, what was
      forced (the second-MCP temptation, the fake-async HITL), what'd change in v2

## Open questions / uncertainty

- `strands-evals` is at PyPI 0.0.1 — install and inspect when slice 5 starts.
- ADOT-to-CloudWatch wiring on macOS dev machines; may need a local OTEL
  collector. Document the exact setup once verified.
- Bedrock model ID for the homework demo — region-specific, must be verified
  against your account before the run.
