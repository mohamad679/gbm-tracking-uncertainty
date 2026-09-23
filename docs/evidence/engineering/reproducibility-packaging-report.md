# Reproducibility and packaging hardening report

Date: 2026-09-19. Status: **COMPLETE for v0.1.0 packaging baseline.**

## Scope

This stage converts the technical benchmark from a loosely versioned research checkout into a reproducible Python package baseline without changing the scientific gate criteria or claiming biological validation.

## Package version and Python support

- Package version: `0.1.0`
- Supported CPython: `3.11`, `3.12`, `3.13`
- `pyproject.toml` now declares `>=3.11,<3.14`.
- Runtime dependency ranges are bounded rather than lower-bound-only.
- Repository source code is licensed under MIT in `LICENSE`.

## Exact reproducibility constraints

`constraints.txt` pins the validated environment:

- Python 3.11: `numpy==2.4.2`
- Python 3.12-3.13: `numpy==2.5.3`
- `Pillow==12.3.0`
- `certifi==2026.7.22`
- CI tooling: `coverage==7.16.1`

The NumPy split is deliberate: the 2.5.x line used by the newer interpreters does not provide the same CPython 3.11 wheel availability, so the supported matrix uses an explicit interpreter marker instead of silently resolving different versions.

## CI validation

GitHub Actions run `35440719250` validates the package after the packaging changes.

Results:

- Python 3.11: success
- Python 3.12: success
- Python 3.13: success
- Unit/integration tests: `42 / 42` passed
- Total package coverage: `68%`
- Enforced coverage floor: `65%`
- Wheel build: success
- Wheel reinstall/version smoke test: success (`0.1.0`)

The wheel build prevents the repository from passing only because editable-source imports happen to work.

## Runtime provenance

`gbm_audit.provenance.runtime_provenance()` records a compact environment block. The final audit now contains:

- package name/version;
- Python version and implementation;
- NumPy, Pillow and certifi versions;
- source Git SHA supplied by GitHub Actions.

The reproduction workflow sets `GBM_AUDIT_GIT_SHA=${{ github.sha }}` explicitly so the final audit is tied to the source revision that produced it.

## Full pinned U373 reproduction

GitHub Actions run `35440643025` completed successfully using the pinned environment and official U373 training archive.

- Source commit: `483209d634f68876732d8bd595994ebf6a826d14`
- Artifact: `u373-reproduced-results`
- Artifact SHA-256: `69fb61591fd6433cf0b78dc780659af91205f722c3f5f7316579ac55d3a727cf`
- Final audit SHA-256: `9de47c9ed1f54bb923414ff12e69e61959c349e55eff0b363cfe766f6b8d6957`

Recorded runtime provenance from that artifact:

- package: `gbm-tracking-uncertainty 0.1.0`
- Python: `CPython 3.11.16`
- NumPy: `2.4.2`
- Pillow: `12.3.0`
- certifi: `2026.7.22`

## Scientific-result comparison

The pinned rerun preserves the scientific decisions:

- `technical_benchmark_complete = true`
- `operator_learning_ready = false`
- `biological_validation_claim_supported = false`

Core reference/corruption/uncertainty/dynamics hashes remain unchanged. The soft-dynamics and gate-sensitivity JSON hashes changed relative to the earlier unpinned run because the pinned Python 3.11 environment uses NumPy 2.4.2 and a few floating-point values serialize at a different last decimal place. The reported metrics and gate outcomes are unchanged at meaningful precision.

Examples:

- clean candidate coverage remains `0.7912813738441216` / `0.8911764705882353` for sequences 01/02 at the 8 px gate;
- the 16 px gate still passes clean coverage but fails the held-out localization-noise robustness criterion;
- the final operator-learning decision therefore remains `false`.

The exact post-packaging hashes and metrics are preserved in `docs/reproduced-results-2026-09-19.json`.

## Reproduction commands

The canonical local installation is now:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints.txt -e .
```

See `docs/reproduction.md` for the full benchmark command chain and CI behavior.

## Gate for the next engineering stage

The packaging/reproducibility baseline is complete. The next engineering stage is architecture/performance cleanup: shared numerical utilities, removal of private cross-module imports/dead work, soft-dynamics transition indexing, archive resource limits, and centralized experiment configuration.
