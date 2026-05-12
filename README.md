# Swift PR Reviewer

A Strands Agents prototype that reviews Swift pull requests. Four specialized
reviewer agents run in parallel over a unified diff, an aggregator merges their
findings, a human approves which findings to ship, and the report-writer formats
the result using an activated skill.

This is the AWS – Strands Agents homework deliverable.

---

## Quick-start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env   # fill in ANTHROPIC_API_KEY (and optionally AWS keys)

# 4. Run a review (Anthropic provider)
STRANDS_PROVIDER=anthropic python -m app.main --pr data/prs/001_force_unwrap

# 5. Run evaluations
BYPASS_TOOL_CONSENT=true python -m evals.run_evals
```

For Bedrock (Push 2 — requires AWS credentials):
```bash
STRANDS_PROVIDER=bedrock OTEL_SERVICE_NAME=swift-pr-reviewer \
    python -m app.main --pr data/prs/001_force_unwrap
```

---

## Rubric concept map

Every rubric requirement maps to a concrete file or module:

| # | Requirement | Where it lives | Status |
|---|---|---|---|
| 1 | Agent anatomy (model, prompt, memory, tools) | 6 agents total: 4 reviewers built inline in `app/graph.py` from `_REVIEWER_CONFIGS` + `_steering/*.md`, plus `app/agents/diff_loader.py` and `app/agents/report_writer.py`. | ✅ |
| 2 | Community tool from `strands-agents-tools` | `from strands_tools import current_time` in `app/agents/report_writer.py` — stamps the report header. | ✅ |
| 3 | MCP server | Local filesystem MCP via stdio in `app/agents/diff_loader.py` — `MCPClient` over `npx @modelcontextprotocol/server-filesystem`. Direct-read fallback in `app/main.py`. | ✅ |
| 4 | Skill | `skills/swift-review-rubric/SKILL.md` — wired via `AgentSkills` plugin on the report-writer agent. | ✅ |
| 5 | Steering | `app/agents/_steering/{correctness,style,api_design,test_coverage,report_writer}.md` — hard rules per reviewer loaded at agent construction. | ✅ |
| 6 | Hook | `app/hooks/instrumentation.py` — `RunLogger` writes one JSONL line per agent invocation to `runs/<run_id>.jsonl`. | ✅ |
| 7 | Interrupt (HITL) | `app/hooks/approval.py` — `ApprovalHook` raises `event.interrupt(...)` before the report-writer node. Main loop prompts per finding and resumes with accepted/rejected decisions. | ✅ |
| 8 | Retries | Strands `structured_output_model=ReviewerOutput` re-prompts on schema failure. Graph-level fail-soft: a broken reviewer is skipped; others still produce signal. | ✅ |
| 9 | Multi-agent pattern | Strands **Graph** in `app/graph.py`: two graphs — (a) 4 parallel reviewer nodes, no edges; (b) single report-writer node with HITL hook. | ✅ |
| 10 | Evaluations | `evals/run_evals.py` — loads `data/prs/*/ground_truth.json`, runs pipeline, computes recall / precision / severity-match. Latest result: 3 PRs, 6/6 findings matched. | ✅ |
| 11 | Observability | `app/observability/` stub — ADOT/CloudWatch wiring planned for Push 2 (Bedrock provider flip). | ⏳ |

---

## Known limitations

These are honest trade-offs, not bugs — see [`submission/reflection.md`](./submission/reflection.md) for full context:

- **3-PR corpus**: sufficient to demonstrate the eval harness, not enough for meaningful recall/precision numbers at scale.
- **MCP diff-loader is decorative**: the CLI reads the diff file directly; the MCP path shows the integration pattern but isn't exercised end-to-end from an external client.
- **HITL is synchronous CLI**: the `input()` interrupt in Graph 2 demonstrates the Strands mechanic; a production iOS reviewer would use an async webhook/push-notification callback.
- **Bedrock provider is stubbed**: `app/provider.py` raises `NotImplementedError` for the Bedrock path; wiring is planned for Push 2.

---

## Documentation

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — Mermaid DAG and design rationale
- [`CLAUDE.md`](./CLAUDE.md) — full architecture reference, conventions, homework concept map
- [`submission/reflection.md`](./submission/reflection.md) — honest assessment of limitations and v2 roadmap
- [`evals/README.md`](./evals/README.md) — eval methodology and results
