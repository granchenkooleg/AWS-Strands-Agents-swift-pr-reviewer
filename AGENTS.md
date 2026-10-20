# Agent guidance — Swift PR Reviewer

## Project context

Read [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md), [evaluation methodology](evals/README.md), and [limitations](submission/reflection.md) before proposing changes. These are the local project sources; verify implementation and saved results at the task's exact commit.

This file guides coding agents working on this repository. It is not a review rubric or runtime reviewer prompt; those live in app/agents/_steering/ and skills/swift-review-rubric/. Changing developer guidance does not implement runtime behavior.

## Scope and delivery

- Preserve the existing Swift educational deliverable and saved evaluation history. Product hardening and any language-profile expansion need explicit task scope; do not infer them from another project's milestone.
- For each task/PR, identify the Reviewer requirement or concrete failure prevented, proposed behavior, verification and remaining limitations.
- Prefer the smallest effective change. Retain useful code; add frameworks or agents only for a demonstrated need.
- Separate complete review, partial/failed execution, findings and human disposition in analysis. Do not claim the current implementation already enforces a proposed failure policy.
- Findings about reviewed code need location, causal failure path and impact; state when diff-only context is insufficient.
- Verify reported metrics against pinned JSON and scorer semantics. Three synthetic PRs are development evidence, not generalized reliability.
- Use fake agents for deterministic failure-path tests where practical. Run checks relevant to the change; do not make live/paid provider calls without task authorization.
- Respect existing user authorization. Documentation, implementation, merge and release scopes are distinct; do not infer one from a milestone or request repeated confirmation for already-authorized routine work.

## Review and accountability

Owner defines the goal; scope/architecture are agreed; the assigned implementer builds/tests; an independent reviewer checks the pinned change; owner judges evidence and release readiness.

Self-review is not independent review. Distinguish source-verified facts, author reports and hypotheses. Model agreement or green test counts alone do not establish review usefulness.

## Optional portfolio context

For an explicitly portfolio-directed development task, the task may reference the [proposed Reviewer release section](https://github.com/granchenkooleg/GBP-AI-projects/blob/35a5c5f4346efa0683f611e741466e95b8776b64/MVP_RELEASE_SPEC.md#r-mvp--honest-advisory-review-on-actual-swift-diffs). It remains proposed and does not override local specifications.

Ordinary work on this repository does not require access to that private coordination repository. Product decisions from other repositories do not govern this Reviewer. If a portfolio task depends on an inaccessible source, report exactly what is missing and obtain its approved content; do not guess policy or request broad credentials.

For a task that reviews another project's PR, use that target project's applicable requirements supplied in the review context. Keep them separate from requirements for developing the Reviewer itself.
