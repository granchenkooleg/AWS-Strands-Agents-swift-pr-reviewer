# Agent guidance

Read [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md), [evaluation methodology](evals/README.md), and [limitations](submission/reflection.md) before proposing changes. Existing educational Swift scope and saved evaluation history remain unchanged.

## Portfolio task routing (2026-10-20)

For portfolio-directed tasks, explicitly read:
- [Approved limited Garden release target / delivery workflow](https://github.com/granchenkooleg/GBP-AI-projects/blob/35a5c5f4346efa0683f611e741466e95b8776b64/decisions/P-001-garden-release-target.md).
- [Release specification and approval limits](https://github.com/granchenkooleg/GBP-AI-projects/blob/35a5c5f4346efa0683f611e741466e95b8776b64/MVP_RELEASE_SPEC.md).
- [Historical reconciliation / RFC-001 research status](https://github.com/granchenkooleg/GBP-AI-projects/blob/35a5c5f4346efa0683f611e741466e95b8776b64/reviews/2026-10-20-product-intent-and-mvp.md).

These are pinned coordination records in a private repository (GBP-AI-projects Draft PR #1), not replacements for this repository's governing specifications. The high-level Garden operator-assisted CLI scenario is accepted; detailed G-AC/B-AC/R-AC criteria remain proposed. This instruction update does not adopt new runtime behavior, alter contracts, or authorize implementation/merge/model runs. Surface conflicts; preserve existing local rules and frozen studies.

Check access explicitly. A cross-repository link is not automatically loaded by Claude/Codex. If access fails, report the missing source and use an owner-supplied exact approved revision; do not guess policy or request broad credentials. The task must identify its milestone, accepted scope and exact implementation SHA for review.

Working sequence: owner defines value → scope/architecture agreed → assigned implementer builds/tests → independent reviewer checks code, requirements and failure cases → owner assesses evidence and progress. Reviewing one's own changes is not independent review. A model's agreement and green test count do not establish product usefulness.

For each new task/PR, name the requirement or concrete failure prevented, its effect on the selected MVP, focused verification and remaining blockers. Extra infrastructure needs a demonstrated blocker and the smallest effective repair. Retain useful implementation; no restart or new agent framework by default. Existing authorization boundaries apply; authorized routine work does not require repeated confirmation.

Reviewer-specific: this guidance does not implement a Python profile, GitHub publishing, or a runtime failure/approval policy. Treat those as separate scoped changes. Verify reports against pinned code and saved JSON; three synthetic PRs are development evidence, not generalized reliability. Use fake agents for deterministic failure-path work where possible; do not make unapproved live provider calls.
