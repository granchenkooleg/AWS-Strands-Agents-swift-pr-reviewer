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

### (d) What would change in v2

- **Bedrock provider**: flip the `NotImplementedError` stub in `app/provider.py` to `boto3`-backed Bedrock. The provider interface already abstracts this; the change is ~20 lines plus verified model IDs per region.
- **ADOT/CloudWatch**: wire `app/observability/` with AWS Distro for OpenTelemetry. Export traces to CloudWatch X-Ray; build a dashboard over the `RunLogger` JSONL metrics. The hook data is already structured for this.
- **Expand corpus**: 20–30 PR fixtures across the Swift issue categories listed above. With a real corpus, the eval numbers become meaningful submission evidence rather than illustrative.
- **Async HITL**: replace `input()` with a thin FastAPI server + `session_manager` so the interrupt can be resolved from a mobile client or Slack bot without blocking the process.
- **GitHub integration**: replace the static `data/prs/` directory with a real GitHub webhook → diff fetch flow. The rest of the pipeline wouldn't change.
