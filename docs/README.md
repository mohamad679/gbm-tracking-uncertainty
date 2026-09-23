# Documentation index

This directory is intentionally split into **reader-facing documentation**, **current evidence**, and **historical archive material**. The goal is to keep the repository easy to review without deleting the preregistration, lock, provenance, and negative-result history that makes the scientific audit reproducible.

## Start here

1. [`final-project-report.md`](final-project-report.md) — consolidated scientific/technical interpretation.
2. [`dryad-confirmatory-final-report.md`](dryad-confirmatory-final-report.md) — final three-experiment external glioma technical-transfer result.
3. [`architecture.md`](architecture.md) — module and pipeline architecture.
4. [`reproduction.md`](reproduction.md) — reproduction instructions.
5. [`project-closure-report.md`](project-closure-report.md) — formal project/release closure and claim boundary.
6. [`roadmap.md`](roadmap.md) — chronological stage progression.
7. [`portfolio-summary.md`](portfolio-summary.md) — concise research-engineering summary.

## Documentation audit (2026-09-23)

The pre-cleanup `docs/` directory contained **100 files**. Every file was classified before reorganization:

| Classification | Count | Action |
| --- | ---: | --- |
| KEEP | 7 | Keep at the `docs/` top level because these are the primary reader-facing documents. |
| MOVE TO EVIDENCE | 46 | Preserve current protocols, locks, manifests, machine-readable results, final stage evidence, engineering evidence, and external-validation evidence under `docs/evidence/`. |
| ARCHIVE | 47 | Preserve superseded protocols, development/tuning artifacts, intermediate step reports, earlier stage generations, and the original stage0–stage9 chronology under `docs/archive/`. |
| DELETE | 0 | Nothing was deleted; the audit trail remains available in Git history and in the reorganized tree. |

`7 + 46 + 47 = 100`, so every pre-cleanup documentation file is accounted for. This index is the only new documentation file added by the cleanup.

### KEEP

- `architecture.md`
- `dryad-confirmatory-final-report.md`
- `final-project-report.md`
- `portfolio-summary.md`
- `project-closure-report.md`
- `reproduction.md`
- `roadmap.md`

### MOVE TO EVIDENCE

Current evidence is grouped by purpose rather than left flat:

- [`evidence/stage-a/`](evidence/stage-a/) — final Stage A protocol/report/locked result.
- [`evidence/stage-b/`](evidence/stage-b/) — final Stage B protocol/report/locked result.
- [`evidence/stage-c/`](evidence/stage-c/) — Stage C v2/T98G development lock and locked evaluation evidence.
- [`evidence/stage-d/`](evidence/stage-d/) — final Stage D v3 protocol, lock, evaluation and closure evidence.
- [`evidence/stage-e/`](evidence/stage-e/) — Stage E protocol, split lock, development fit, one-time locked result and final report.
- [`evidence/dryad/`](evidence/dryad/) — Dryad local-resumption protocol, committed schema lock, runbook and machine-readable final result.
- [`evidence/external/`](evidence/external/) — fallback external glioma source audit, manifest, protocol amendment and historical n=1 result.
- [`evidence/engineering/`](evidence/engineering/) — architecture/performance, hardening, packaging and frozen reproduced-result evidence.
- [`evidence/glio-trace/`](evidence/glio-trace/) — exploratory annotation-pilot record.
- [`evidence/release/`](evidence/release/) — v1.0.0 release/portfolio evidence.

### ARCHIVE

Historical but scientifically relevant material is retained under:

- [`archive/stage-a/`](archive/stage-a/) — superseded Stage A tuning/protocol iterations and step reports.
- [`archive/stage-b/`](archive/stage-b/) — Stage B development/intermediate artifacts.
- [`archive/stage-c/`](archive/stage-c/) — original Stage C and superseded v2 step reports.
- [`archive/stage-d/`](archive/stage-d/) — Stage D v1/v2 HOLD-era material and superseded development records.
- [`archive/legacy/`](archive/legacy/) — original stage0–stage9 reports and the 2026-09-19 project pivot record.

Archived files are **not obsolete evidence**; they are simply no longer the primary entry points. Historical `HOLD`, `REVISE`, negative, and superseded artifacts remain intentionally immutable.

## Evidence policy

A file belongs in `evidence/` when it is part of the current scientific audit trail: a frozen protocol, source manifest, lock, machine-readable result, final stage report, or engineering/reproducibility record. A file belongs in `archive/` when it is a superseded protocol/configuration, development-only tuning output, intermediate step report, or earlier stage-generation record.

Future work should avoid adding new flat files to the top-level `docs/` directory unless they are intended as primary reader-facing documents. New preregistration/result artifacts should be placed directly in the appropriate `docs/evidence/<study-or-stage>/` directory.