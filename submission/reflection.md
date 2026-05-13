# Submission Reflection

## What worked

The Strands Graph model maps cleanly to a parallel code-review pipeline. Four reviewer agents with no shared state run concurrently by default — no threading primitives, no async coordination, just nodes with no edges. The HITL interrupt via `BeforeNodeCallEvent` was the most interesting piece: suspending a graph, collecting a human decision, and resuming with modified state felt production-adjacent even in a CLI wrapper.

Steering files (`.md` per reviewer) turned out to be the right abstraction. Editing a reviewer's behaviour is a text edit — no Python reload, no redeploy. The severity ladder and output rules in each file are enforceable through `structured_output_model`; Strands re-prompts on schema failure automatically.

The eval harness closed the feedback loop. Running `evals/run_evals.py` after each change and seeing recall/precision numbers move made tuning the steering prompts tractable rather than impressionistic.

---

## Honest limitations

### (a) Tiny corpus — 3 PRs

The `data/prs/` corpus has three fixtures: `001_force_unwrap`, `002_clean_pr` (precision check — no issues expected), and `003_retain_cycle`. Three PRs is enough to smoke-test the harness and demonstrate the eval pipeline, but it isn't enough to report meaningful recall or precision numbers — a single missed finding moves recall by 16 points. A representative corpus for a Swift reviewer would need 20–30 PRs covering: `@MainActor` violations, integer overflow, IUO, various retain-cycle patterns, API breaking changes, naming conventions across different file types, and true negatives. That corpus work was descoped as slice-5 stretch in favour of getting the end-to-end pipeline solid first.

### (b) MCP diff-loader is decorative

`app/agents/diff_loader.py` constructs an `MCPClient` over a local filesystem stdio server (`npx @modelcontextprotocol/server-filesystem`). The CLI entry-point in `app/main.py:_load_pr` passes a directory path to the MCP server — the agent reads `pr.diff` through the MCP tool. A direct `Path(pr_dir / "pr.diff").read_text()` call would do the same thing with less machinery and a direct-read fallback already exists for when the MCP server fails to launch.

The MCP path is there because rubric requirement #3 asks for an MCP server integration. It demonstrates the wiring pattern correctly — `MCPClient`, `stdio_client`, `StdioServerParameters`, per-PR session scope — but it doesn't add production value beyond that. In a real deployment the diff would arrive over a webhook or from a GitHub API call; MCP would only be useful if the filesystem server were replaced by a server that proxied those APIs.

### (c) HITL is synchronous CLI, not a real iOS callback

The approval gate in `app/hooks/approval.py` registers a `BeforeNodeCallEvent` on the `report-writer` node and calls `event.interrupt(...)`. `app/main.py` detects `Status.INTERRUPTED`, iterates over the findings payload, prompts the user with `input()`, and calls `graph.resume(...)` with accepted/rejected decisions.

This shows the Strands HITL mechanic correctly — interrupt, surface the payload, resume with state. But `input()` blocks the process, which only works when a human is sitting at the terminal. A real iOS app would:

1. Persist the interrupt payload to a database with a session ID.
2. Push a notification to the mobile client.
3. Expose an HTTP endpoint that accepts the human decision and calls `graph.resume(session_id, ...)`.
4. Use `session_manager` for durable graph suspension across process restarts.

The CLI `input()` is a stand-in that demonstrates the pattern without implementing the async infrastructure.

### (d) Eval re-runs segfault intermittently on Bedrock

The first eval invocation in a fresh shell session is reliable. The second and third successive `python -m evals.run_evals` calls have repeatedly crashed with `segmentation fault` (SIGSEGV) right after the `run_id=… — scoring 3 PR(s)` print, before any PR pipeline runs. The crash is C-level (not a catchable Python exception), so the run produces no aggregate table and no snapshot.

Suspected cause: a stale `npx @modelcontextprotocol/server-filesystem` child process from the previous run holding a Unix socket/FD that the second process trips over, or a Python 3.13 + boto3 native-extension teardown race on macOS. The cited evaluation snapshot (`evals/results/latest.json`) is from a clean first-run; the segfault doesn't affect submitted metrics, only re-runs.

Workaround when re-running:

```bash
pkill -f "modelcontextprotocol/server-filesystem" 2>/dev/null
sleep 1
STRANDS_PROVIDER=bedrock BYPASS_TOOL_CONSENT=true python -m evals.run_evals
```

A proper fix would (a) reuse a single long-lived MCP client across runs rather than spawning per-PR, or (b) shell out to a helper script that wraps each eval in a clean child process — both are deployment-grade concerns rather than correctness bugs in the reviewer logic.

### (e) Severity is non-deterministic on Bedrock

Two consecutive Bedrock eval runs on the same `data/prs/003_retain_cycle` produced *different* severities for the retain-cycle finding — `major` on one run (matching ground truth), `blocker` on another. Same prompt, same temperature defaults, different answer. This is LLM non-determinism, not a steering bug; the steering's `blocker` definition ("crash, corrupt, invariant") doesn't fit a memory leak by any honest reading. Rather than chase the model with tighter steering or game ground truth to match whatever a given run produces, I'd rather report the severity-match metric (`Sev`) honestly and let the grader see the variance. The cited run scored `Sev=0.833` (5/6 correct severities); a different run hit `Sev=1.0`. Both are real.

### (f) What would change in v2

- **Bedrock provider**: ✅ landed in Push 2. `app/provider.py` now selects `BedrockModel` when `STRANDS_PROVIDER=bedrock`, memoized on `(region, model_id, max_tokens)`. End-to-end run on `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (cross-region inference profile) produced 5 findings on `001_force_unwrap`; the eval harness re-ran the full corpus and scored 6/6 matched (R=1.00, P=1.00, Sev=1.00). The first model ID I tried (`anthropic.claude-3-5-sonnet-20241022-v2:0` from the original `.env.example`) had reached EOL — switching to the `us.` inference profile was the only material wrinkle.
- **ADOT/CloudWatch**: partially landed. `app/observability/tracing.py` initializes an OTLP HTTP exporter when `OTEL_EXPORTER_OTLP_ENDPOINT` is set and `main.py` calls it at startup. I did **not** stand up an ADOT collector locally for the demo run, so spans never left the process. Per-agent telemetry evidence ships as JSONL via the `RunLogger` hook (`submission/traces/bedrock_run_70abcf53a8fd.jsonl` — 6 lines, one per agent invocation, with latency and token counts). Wiring the collector + exporting to CloudWatch X-Ray is a deployment task, not a code task; the SDK side is done.
- **Expand corpus**: still 3 PRs — descoped from Push 2 as well. Real eval signal needs 20–30 PRs across the Swift issue categories.
- **Async HITL**: still synchronous CLI `input()`. The replacement would be a thin FastAPI server + `session_manager` so the interrupt can be resolved from a mobile client or Slack bot without blocking the process.
- **GitHub integration**: replace the static `data/prs/` directory with a real GitHub webhook → diff fetch flow. The rest of the pipeline wouldn't change.

---

## Push 2 — what actually landed

Push 1 (`v1.0-submission`) shipped the docs and the steering-prompt refactor. Push 2 (`v1.1-aws`) adds the AWS deliverable:

- `app/provider.py`: `BedrockProvider` path live, sandbox-tested against `us.anthropic.claude-sonnet-4-5-20250929-v1:0`.
- `app/observability/tracing.py`: OTel SDK initialization, gated on `OTEL_EXPORTER_OTLP_ENDPOINT` so the Anthropic dev path stays noise-free.
- `app/main.py`: calls `setup_tracing()` at startup; prints a one-line confirmation when the collector endpoint is configured.
- `.env.example`: created (was missing from Push 1 despite being referenced in the README quick-start). Documents the Bedrock path and explicitly omits secrets.
- `submission/traces/bedrock_run_*.jsonl` + `submission/traces/bedrock_eval_*.json`: real evidence of an end-to-end Bedrock run and an eval over Bedrock.
- `evals/results/latest.json`: refreshed to point at the Bedrock-scored run.
