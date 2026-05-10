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
                         │ DiffLoader   │  ← reads pr.diff via filesystem MCP,
                         │  (Strands    │     parses with `unidiff`, emits
                         │   Agent)     │     structured Hunks
                         └──────┬───────┘
                                │ List[Hunk]
                ┌───────────────┼───────────────┬──────────────┐
                ▼               ▼               ▼              ▼
        ┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
        │ Correctness  ││    Style     ││  ApiDesign   ││ TestCoverage │
        │   Reviewer   ││   Reviewer   ││   Reviewer   ││   Reviewer   │
        └──────┬───────┘└──────┬───────┘└──────┬───────┘└──────┬───────┘
               │ List[Finding] (each agent, Pydantic-validated)│
               └───────────────┬──────────────────────────────┘
                               ▼
                       ┌──────────────┐
                       │  Aggregator  │ ← activates `swift-review-rubric`
                       │   (Strands   │   skill, dedupes, sorts by severity
                       │    Agent)    │
                       └──────┬───────┘
                              │
                    BeforeNodeCallEvent on `report-writer`
                    raises interrupt → human accepts/rejects each finding
                              │
                       ┌──────▼───────┐
                       │ ReportWriter │ ← writes outputs/<run_id>/report.md
                       └──────────────┘
```

**Pattern: Strands `Graph`** (not Workflow). The topology is a literal DAG
with parallel fan-out at the reviewer stage. `GraphBuilder` from
`strands.multiagent` gives us native parallel node execution and clean
`BeforeNodeCallEvent` interrupt seams. Workflow tool is the right call for
agent-driven declarative task lists; we don't want that meta level here.

## Tech stack

- Python 3.11+ (uses `match`, PEP 604 unions)
- `strands-agents` (verify exact version on first install — pin from PyPI)
- `strands-agents-tools` for community tools
- `strands-evals` for the eval harness
- `mcp` Python client + a local stdio filesystem MCP server (Node, via `npx`)
- `unidiff` for parsing — never hand-roll diff parsing
- `pydantic>=2.6` for every data contract that crosses an agent boundary
- `boto3` (Bedrock provider) and `anthropic` (Anthropic provider) — selected at
  runtime by `STRANDS_PROVIDER`
- AWS Distro for OpenTelemetry → CloudWatch Logs/Metrics

## Directory map

```
swift-pr-reviewer/
├── CLAUDE.md                       ← you are here
├── README.md                       ← user-facing setup
├── ARCHITECTURE.md                 ← TODO: diagrams + design rationale
├── requirements.txt
├── .env.example
│
├── app/
│   ├── main.py                     ← CLI entry: `python -m app.main --pr <dir>`
│   ├── graph.py                    ← GraphBuilder topology + agent wiring
│   ├── models.py                   ← Pydantic: Hunk, Finding, ReviewReport, etc.
│   ├── provider.py                 ← Bedrock vs Anthropic selection
│   │
│   ├── agents/
│   │   ├── diff_loader.py          ← parses unified diff → List[Hunk]
│   │   ├── correctness_reviewer.py ← bugs, force-unwraps, retain cycles
│   │   ├── style_reviewer.py       ← naming, formatting (LLM-only, no swiftlint)
│   │   ├── api_design_reviewer.py  ← public API breakage, naming, generics
│   │   ├── test_coverage_reviewer.py ← missing tests for new branches
│   │   └── aggregator.py           ← merges, dedupes, activates skill, formats
│   │
│   ├── tools/
│   │   ├── parse_diff.py           ← @tool wrapping unidiff for the loader agent
│   │   └── format_comment.py       ← @tool: Finding → markdown comment string
│   │
│   ├── hooks/
│   │   ├── instrumentation.py      ← Before/After invocation: log + emit OTEL spans
│   │   └── approval.py             ← BeforeNodeCallEvent on report-writer → interrupt
│   │
│   └── observability/
│       ├── otel.py                 ← OTEL setup; ADOT exporter to CloudWatch
│       └── metrics.py              ← Custom metrics: findings_per_pr, json_retry_count
│
├── skills/
│   └── swift-review-rubric/
│       └── SKILL.md                ← rubric the aggregator activates for formatting
│
├── data/
│   └── prs/
│       └── 001_force_unwrap/
│           ├── pr.diff             ← input
│           ├── metadata.json       ← input
│           └── ground_truth.json   ← evals only — agents never see this
│
├── evals/
│   ├── run_evals.py                ← entrypoint
│   ├── evaluators.py               ← recall, precision, severity match
│   └── README.md
│
├── outputs/                        ← report.md per run, gitignored after demo
└── runs/                           ← hook-emitted JSONL per run, gitignored
```

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

Every agent boundary is a Pydantic model. If you can't write the schema,
you don't yet understand the boundary.

```python
# app/models.py — sketch, not full implementation

class Hunk(BaseModel):
    file_path: str
    start_line: int           # line in the new (post-change) file
    line_count: int
    added_lines: list[str]    # only the '+' lines, sans prefix
    context: str              # the diff hunk header for the LLM

Severity = Literal["blocker", "major", "minor", "nit"]
Category = Literal["correctness", "style", "api_design", "test_coverage"]

class Finding(BaseModel):
    file_path: str
    line: int                 # post-change line number, must match a hunk
    severity: Severity
    category: Category
    title: str = Field(max_length=120)
    body: str = Field(max_length=600)
    suggested_action: str

class ReviewerOutput(BaseModel):
    """What every reviewer agent must return."""
    findings: list[Finding]
    confidence_note: str = ""  # free-form one-liner, optional

class ReviewReport(BaseModel):
    pr_id: str
    findings: list[Finding]    # post-aggregation, post-HITL filter
    rejected_findings: list[Finding] = []  # what the human dropped
    rendered_markdown: str
```

**Hard rule:** reviewer agents emit `ReviewerOutput` JSON only — no prose, no
markdown wrappers. If JSON parsing fails, the retry loop (see below) re-prompts
with the validation error appended. After 2 retries → return empty `findings`
list and emit a `json_retry_exhausted` metric. We do not fail the run on a
single broken reviewer; the others still produce signal.

## Homework concept map — where each requirement lives

| # | Requirement | File / module |
|---|---|---|
| 1 | Agent anatomy (model, prompt, memory, tools) | every file under `app/agents/` — each is a `strands.Agent` with `system_prompt`, model from `app/provider.py`, tool list, and per-agent `agent.state` |
| 2 | Community tool from `strands-agents-tools` | `from strands_tools import file_read, current_time` in `app/agents/diff_loader.py` (file_read) and `app/agents/aggregator.py` (current_time for the run timestamp). Also `handoff_to_user` is available but we use `BeforeNodeCallEvent` instead — see #7 |
| 3 | MCP server | Local filesystem MCP via stdio. `app/main.py` constructs `MCPClient(lambda: stdio_client(StdioServerParameters(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "data/prs"])))` and passes it to the diff loader agent |
| 4 | Skill | `skills/swift-review-rubric/SKILL.md` — wired via `AgentSkills(skills="./skills/swift-review-rubric")` plugin on the Aggregator agent only. The aggregator activates it before formatting the final markdown |
| 5 | Steering | Per-agent `system_prompt` strings + `app/agents/_steering/` markdown files loaded at agent construction. Hard rules every reviewer enforces: "only comment on changed lines", "cite line numbers from diff", "severity must be one of {blocker, major, minor, nit}", "never invent code not in the hunk" |
| 6 | Hook | `app/hooks/instrumentation.py` — `HookProvider` registering `BeforeInvocationEvent` and `AfterInvocationEvent` callbacks. Logs `(agent_name, input_size, latency_ms, token_count, retry_count)` to `runs/<run_id>.jsonl` and emits OTEL spans |
| 7 | Interrupt (HITL) | `app/hooks/approval.py` — `BeforeNodeCallEvent` on the `report-writer` node raises `event.interrupt("review-approval", reason={"findings": [...]})`. CLI prompts user to accept/reject each finding; rejected ones land in `ReviewReport.rejected_findings` |
| 8 | Retries | Two layers: (a) Strands' built-in retry strategy for transient model errors, configured in `app/provider.py`; (b) custom Pydantic retry in `app/agents/_retry.py` — on `ValidationError`, re-prompt the agent with the error message appended, max 2 attempts |
| 9 | Multi-agent pattern | **Graph** in `app/graph.py` using `strands.multiagent.GraphBuilder`. Nodes: `diff-loader`, `correctness`, `style`, `api-design`, `test-coverage`, `aggregator`, `report-writer`. Edges fan out from `diff-loader` to the four reviewers, all four edge into `aggregator`, which edges into `report-writer` |
| 10 | Evaluations | `evals/run_evals.py` — loads every `data/prs/*/ground_truth.json`, runs the full graph, computes recall/precision/severity-match. `evaluators.py` implements custom evaluators on top of `strands_evals.evaluators`. Test PRs cover: force-unwrap, retain cycle, missing weak self in Combine sink, public API breakage, missing test for new branch, naming style violation, no-finding-clean-PR (precision check) |
| 11 | Observability | `app/observability/otel.py` configures the AWS Distro for OTel (ADOT) to export traces and metrics to CloudWatch. Strands emits spans automatically; our hooks add custom metrics: `findings_per_pr`, `agent_latency_ms`, `json_retry_count`, `precision_rolling`. Dashboard URL goes in `submission/screenshots/` |

## Conventions

- **Pydantic everywhere across agent boundaries.** No `dict[str, Any]` payloads.
- **Reviewer agents output JSON only.** Steering enforces this. Retry loop catches violations.
- **One `tool_use_id` per agent invocation** for traceability. Threaded through hooks.
- **No global state.** Run state lives in `RunContext` constructed per `python -m app.main` invocation.
- **No swiftlint, no shell out to git, no network calls at runtime** (other than the model API and the MCP server). The PR is a static directory under `data/prs/`.
- **Steering rules live in markdown** under `app/agents/_steering/`. Loaded at agent construction time. Edit those, not the Python strings, to tune behavior.
- **All hook output is JSONL**, one line per event, fields stable. The eval harness greps over it.

## Adding a new reviewer agent

1. Create `app/agents/<name>_reviewer.py` returning a Strands `Agent`.
2. Add a steering file at `app/agents/_steering/<name>.md`.
3. Add the node + edge in `app/graph.py` (parallel sibling of existing reviewers).
4. Add `Category` literal value in `app/models.py`.
5. Add at least 2 ground-truth findings of the new category in `data/prs/`.
6. Re-run evals; commit the precision/recall delta.

If you skip step 5–6 you have no signal that the new reviewer works.

## Failure modes & limits we accept

- **Bedrock model gating.** The exact `BEDROCK_MODEL_ID` may not be enabled in
  your AWS region. `app/provider.py` raises a clear error on first call. Fix:
  request access in the Bedrock console (can take hours) or change region.
- **JSON validation failure rate.** Empirically 1–5% of reviewer calls return
  malformed JSON; the retry layer absorbs almost all. Track
  `json_retry_count`; if rolling average climbs above 0.1 per agent invocation,
  the steering needs tightening.
- **Diff parser edge cases.** `unidiff` handles renames, binary files, and
  `\\ No newline at EOF` correctly; do not "improve" with regex.
- **CloudWatch cost.** Custom metrics are ~$0.30/metric/month plus dimensions.
  Enable for the demo, take screenshots, then disable. Don't leave it running.
- **Aggregator dedup is heuristic.** Same line + same category from two
  reviewers gets merged taking the higher severity. Cross-category overlaps
  (e.g. a force-unwrap that's also bad style) deliberately stay separate.
- **The HITL gate is synchronous CLI.** In a real iOS frontend it'd be an
  async webhook with the agent suspended via `session_manager`. Note this in
  the submission reflection — it's a limitation, not a bug.

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

- Exact `strands-evals` package layout vs current docs — verify on first install.
- `BeforeInvocationEvent` exact import path: docs reference both
  `strands.hooks` and `strands.hooks.events`. Confirm and pin.
- ADOT-to-CloudWatch wiring on macOS dev machines; may need a local OTEL
  collector. Document the exact setup once verified.
- Bedrock model ID for the homework demo — region-specific, must be verified
  against your account before the run.
