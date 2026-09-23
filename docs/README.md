# Documentation index

This directory is intentionally split into three layers so the project is easy to review without losing the scientific audit trail.

## Start here

1. [`final-project-report.md`](final-project-report.md) — consolidated technical conclusions and claim boundary.
2. [`architecture.md`](architecture.md) — module architecture, invariants, and reproducibility boundaries.
3. [`reproduction.md`](reproduction.md) — local and GitHub Actions reproduction instructions.
4. [`dryad-confirmatory-final-report.md`](dryad-confirmatory-final-report.md) — final three-experiment rat-glioma external technical-transfer result.
5. [`project-closure-report.md`](project-closure-report.md) — formal project closure scope.
6. [`roadmap.md`](roadmap.md) — research-stage chronology and final state.
7. [`portfolio-summary.md`](portfolio-summary.md) — compact research-engineering summary.
8. [`release-notes-v1.0.0.md`](release-notes-v1.0.0.md) — tagged v1.0.0 release history plus the later Dryad evidence-extension note.

## Evidence layout

Scientific evidence that must remain available for auditability is grouped by purpose instead of being left as ~100 files at the top level.

- [`evidence/stage-a/`](evidence/stage-a/) — adaptive-candidate protocols, development artifacts, locked result, and final report.
- [`evidence/stage-b/`](evidence/stage-b/) — graph-context posterior protocol, development evidence, locked result, and final report.
- [`evidence/stage-c/`](evidence/stage-c/) — original Stage C plus the revised T98G-locked Stage C v2 evidence.
- [`evidence/stage-d/`](evidence/stage-d/) — historical HOLD artifacts, Huh7 audits/evaluations, v3 calibration, lock, and closure evidence.
- [`evidence/stage-e/`](evidence/stage-e/) — final multi-domain protocol, dataset/split locks, development fit, one-time sequence-02 result, and final REVISE report.
- [`evidence/dryad/`](evidence/dryad/) — local-resumption protocol, committed schema lock, runbook, and frozen one-time Dryad machine result.
- [`evidence/external-context/`](evidence/external-context/) — source audit, fallback protocol/result, and combined external-context chronology.
- [`evidence/engineering/`](evidence/engineering/) — architecture/performance hardening, packaging/reproducibility evidence, and frozen reproduced-results snapshot.

## Archive layout

Historical material that is useful for provenance but is not part of the current reader path is retained under [`archive/`](archive/).

- [`archive/legacy-pipeline/`](archive/legacy-pipeline/) — early stage0-stage9 technical reports that predate the A-E gated research line.
- [`archive/project-history/`](archive/project-history/) — annotation-pilot, pivot, and superseded portfolio-development notes.

Nothing was deleted during this cleanup. Historical scientific evidence is retained rather than relying on Git history alone.

## Audit record

The complete file-by-file classification of the original 100 `docs/` files is recorded in [`documentation-audit.json`](documentation-audit.json):

| Action | Count | Meaning |
| --- | ---: | --- |
| `KEEP` | 8 | Current reader-facing documents remain at `docs/` top level. |
| `MOVE_TO_EVIDENCE` | 77 | Protocols, locks, results, stage reports, and engineering evidence moved under `docs/evidence/`. |
| `ARCHIVE` | 15 | Historical/superseded project-development material moved under `docs/archive/`. |
| `DELETE` | 0 | No scientific/history artifact deleted. |

## Claim boundary

The reorganization changes paths only. It does not alter any frozen protocol, locked outcome, historical decision, numerical result, or scientific claim. In particular, Stage E remains `REVISE`, the Dryad `n=3` result remains external technical-transfer evidence, and the repository does not claim human-GBM-wide or clinical validation.
