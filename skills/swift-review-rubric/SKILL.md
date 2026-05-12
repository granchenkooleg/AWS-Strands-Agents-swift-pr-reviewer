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

## Output rules — read carefully

- **Start the output with the `# Code Review` heading. No preamble, no
  "Now I'll format…", no "Here is the report:", no thinking out loud.**
  The very first character of your output must be `#`.
- Substitute every placeholder. Do NOT emit empty brackets or literal placeholder names.

## Comment format

For each finding, render exactly this structure. Substitute `{severity}`,
`{path}`, `{line}`, `{title}`, `{body}`, `{action}` with the finding's actual
values. Do NOT leave placeholder names or empty brackets in the output.

```
**{severity}** `{path}:{line}` — {title}

{body}

Suggested action: {action}
```

Worked example. If the finding is severity=blocker, path=Sources/UserService.swift,
line=15, title=Force-unwrap on async response, body="`return response!` will
crash if nil.", action="Use guard let.", then the output is:

```
**blocker** `Sources/UserService.swift:15` — Force-unwrap on async response

`return response!` will crash if nil.

Suggested action: Use guard let.
```

Note: the bold marker contains the literal severity word (`blocker`,
`major`, `minor`, `nit`) — never empty `****`, never the word "severity",
never the placeholder syntax.

## Report structure

The full report is exactly:

```
# Code Review

**Review date:** {ISO-8601 timestamp from current_time tool}
**Summary:** {N} blocker, {N} major, {N} minor, {N} nit.

---

## Blocker

{one finding block per blocker, separated by `---`}

## Major

{one finding block per major, separated by `---`}

## Minor

{...}

## Nit

{...}
```

Skip empty severity sections entirely (no empty `## Minor` heading).

## Hard constraints

- Never invent code that isn't in the diff hunks.
- Never combine multiple findings into one comment.
- Never recommend a follow-up PR; this review is the gate for *this* PR.
- Reviewers assess; they do not congratulate. No "great job!", "looks good overall!", etc.
- If the input findings list is empty, emit exactly: `No issues found.`
- Never include the literal strings `[severity]`, `{severity}`, `path:line`,
  or any placeholder syntax in the output. Substitute or omit.
