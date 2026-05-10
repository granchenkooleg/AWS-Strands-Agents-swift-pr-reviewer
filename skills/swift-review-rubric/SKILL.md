---
name: swift-review-rubric
description: Format raw reviewer findings into a polished PR-comment report following our Swift review style guide.
---

# Swift Review Rubric

Activate this skill when you have a list of validated `Finding` objects from
the four reviewer agents and need to produce the final markdown report shown
to the human approver and posted to the PR.

## Severity ladder

- **blocker** — bug, crash, security issue, or contract break. Must fix before merge.
- **major** — design or correctness concern that should be addressed but not strictly blocking.
- **minor** — code quality, naming, or local style.
- **nit** — cosmetic.

If unsure, prefer the lower severity. Never invent severity above what the reviewer agent emitted.

## Comment format

For each finding, render exactly:

```
**[severity]** `path:line` — title

Body. Two sentences max. Refer to the changed line content directly when
useful, but never quote unchanged context.

Suggested action: <single concrete step>
```

## Report structure

1. **Summary line.** Total findings by severity, e.g. "2 blocker, 1 major, 3 minor, 0 nit."
2. **Sections grouped by severity** (blocker → nit). Skip empty sections.
3. **No "great job!" preamble.** Reviewers don't praise; they assess.
4. **No mention of unchanged code.** Every finding must cite a line in the diff.

## Hard constraints

- Never invent code that isn't in the diff hunks.
- Never combine multiple findings into one comment.
- Never recommend a follow-up PR; this review is the gate for *this* PR.
- If the input findings list is empty, emit a one-line "No issues found." report.
