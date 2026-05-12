# PR Corpus

Each PR lives in its own directory:

```
001_force_unwrap/
├── pr.diff           # unified diff (the primary input)
├── metadata.json     # title, description, target branch
└── ground_truth.json # expected findings — used by evals only, not by the reviewer
```

Naming: `NNN_short_label/` where NNN is a zero-padded ordinal.

Reviewer agents see ONLY `pr.diff` and `metadata.json`. They never see `ground_truth.json` —
that file exists exclusively for the eval harness.
