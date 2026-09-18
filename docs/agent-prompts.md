# Copy-ready supervisor prompt for the next gate

Paste the following message in the **main Codex conversation inside the opened project folder** after following `START_HERE_FA.md`. The supervisor remains responsible for checking all agent outputs and deciding the gate.

```text
You are the supervisor for Stage 1 only. First read AGENTS.md,
docs/roadmap.md, docs/stage0-report.md, and docs/annotation-pilot.md.
The user has authorized the project work. Use at most three subagents
for independent read-only tasks: (1) inspect image quality and shared
field of view on both mouse ROIs; (2) check metadata, pixel/time units,
and identify a control ROI per mouse; (3) review annotation protocol,
uncertainty labels, and leakage risks. Give each agent its own input,
output, deadline, and no overlapping write ownership. Integrate their
findings yourself. Prepare a small manual annotation workflow and
inspection windows; do not call an automatic track a human-reviewed
reference. Ask a human reviewer only for the actual identity judgments
that a model cannot independently verify. Run executable checks, record
commands and failures, and write a dated Stage 1 gate report with a
GO / REVISE / STOP decision. Do not start Stage 2 until the independent
annotations and the Stage 1 gate have passed. Do not run HMM, SLDS, or
Koopman modeling in Stage 1. Keep all source data and exported images
outside Git until distribution rights are established.
```

The first person inspecting and assigning cell identities should not see a model's proposed identities. A second reviewer should resolve ambiguous links and document disagreements. Source labels from U373 cannot stand in for brain-slice ground truth.
