# Architecture and performance refactor — 2026-09-19

## Scope

This stage reorganizes shared numerical/configuration code, removes private cross-module coupling, reduces the main soft-dynamics transition hotspot, and adds defensive archive limits. It is intentionally a behavior-preserving engineering refactor: the scientific benchmark definitions and decision gates are unchanged.

## Architecture changes

- Added `gbm_audit.config` as the single source for benchmark defaults and ZIP safety limits.
- Added public `gbm_audit.calibration.temperature_transform` and removed cross-module imports of the private uncertainty helper.
- Added `gbm_audit.numerics` for Gaussian emissions, transition-row normalization, and stationary-distribution computation shared by hard and soft dynamics.
- Updated corruption generation, baseline tracking, uncertainty evaluation, and HMM defaults to use centralized constants.
- Corrected baseline metadata so the declared tracker inputs match the implementation: the frozen nearest-neighbour tracker uses frame/x/y and ignores area, supplied observed IDs, and evaluation truth.

## Performance change

The soft-dynamics transition accumulation previously scanned every edge against every later edge, giving an O(E^2) candidate scan. It now builds an adjacency index keyed by each edge's left observation and visits only edges that can follow the current edge. The work is O(E + C), where C is the number of compatible consecutive-edge pairs. The mathematical contribution for every compatible pair is unchanged.

A regression test computes the old quadratic reference accumulation on a controlled graph and verifies equality with the indexed implementation. No wall-clock speedup is claimed here because this stage validates algorithmic complexity and numerical equivalence rather than publishing a hardware-specific benchmark.

## Archive safety

External ZIP input is now validated before benchmark/image decoding. Limits cover:

- member count,
- maximum declared uncompressed member size,
- total declared uncompressed size,
- compression ratio,
- bounded member reads with post-decompression size consistency checks.

The same bounded member reader is used for benchmark lineage/tiff reads and appearance-frame loading. The official U373 archive passes these limits in the full reproduction workflow.

## Validation

Latest validation source commit before documentation: `bc9cda1628423f45e9926d0b0a02b1b0160b0f3c`.

GitHub Actions test run: `35441341915`.

- Python 3.11: success
- Python 3.12: success
- Python 3.13: success
- wheel build/install smoke test: success
- tests: 50 / 50 passed
- total coverage: 69%
- enforced coverage floor: 65%

Full pinned U373 reproduction run: `35441341918`.

- package environment installation: success
- tests inside reproduction workflow: success
- official U373 download: success
- complete numerical pipeline: success
- result artifact upload: success
- artifact: `u373-reproduced-results`
- artifact SHA-256: `c60428859456eeef6eb27228c6b18720e79d9ed2368c7d874b14eda24bc0c4c0`

Runtime provenance from `final-audit.json`:

- package: `gbm-tracking-uncertainty 0.1.0`
- Python: CPython 3.11.16
- NumPy: 2.4.2
- Pillow: 12.3.0
- certifi: 2026.7.22
- source Git SHA: `bc9cda1628423f45e9926d0b0a02b1b0160b0f3c`

## Numerical equivalence

The post-refactor run preserves all declared project decisions:

- `technical_benchmark_complete = true`
- `operator_learning_ready = false`
- `biological_validation_claim_supported = false`

Reference-manifest, corruption, uncertainty, hard-dynamics, soft-dynamics, gate-sensitivity, and motion-appearance uncertainty hashes are recorded in `docs/reproduced-results-2026-09-19.json`. Compared with the immediately preceding pinned snapshot, a few soft floating-point values move only in the final serialized decimal; no gate threshold, scenario interpretation, or project conclusion changes.

## Deliberately deferred

The all-pairs frame-local candidate search remains O(n_prev * n_current). For the current U373 benchmark this is not the dominant blocker, and replacing it with a spatial index would add implementation complexity and a new equivalence surface. That optimization should be justified by profiling on larger workloads rather than added speculatively.

The soft-state procedure also retains its existing method name and scientific interpretation. This refactor does not redefine it as a full temporal soft HMM; doing so would be a model change rather than an architecture cleanup.
