# Changelog

All notable project changes are documented here. The project follows semantic versioning from `0.1.0` onward.

## [Unreleased]

## [0.2.0] - 2026-09-21

### Added
- Frozen Stage A adaptive-candidate protocol with leakage controls and quantitative pass/revise thresholds.
- Candidate-burden instrumentation and a provenance-checked comparison CLI for fixed 8/12/16-pixel baselines and `adaptive_v1`.
- Deterministic, truth-blind adaptive candidate generator v1 with motion-uncertainty and local-density gates.
- Explicit candidate-graph sampling for `adaptive_v1`, downstream posterior diagnostics, and graph-consistency enforcement for legacy motion scorers.
- Outcome-blind CTC Huh7 audit and sequence locks for independent Stage D evaluation.
- Frozen zero-shot Huh7 evaluator and a bounded Koopman/empirical blend calibrated on sequence `01`.
- One-time locked Huh7 sequence-`02` evaluation with exact CI reproduction.
- Formal Stage D closure report and consolidated project-level conclusion.

### Changed
- Project status, roadmap, portfolio summary, and README now consistently record
  the qualified Stage D v3 `GO`.
- Package version advanced to `0.2.0` for the completed Stage A-D technical
  research line.

### Validation status

- Stage D v2 zero-shot evaluation: `HOLD` because mean-speed non-inferiority failed despite improved RMSE.
- Stage D v3 calibrated sequence generalization: `GO`; all seven locked gates passed on 1481 Huh7 sequence-`02` transitions.
- Claim scope remains technical and excludes zero-shot, biological and clinical validation.

## [0.1.0] - 2026-09-19

### Added
- Deterministic U373 reference manifest and 17 known-truth corruption scenarios.
- Greedy nearest-neighbour baseline and sampled one-to-one uncertainty evaluation.
- Hard and soft two-state dynamics sensitivity analyses.
- Gate-sensitivity evaluation and final evidence-derived audit gates.
- Motion, area, and raw-image appearance proposal variants.
- Cross-stage schema/provenance validation and scenario-ID alignment.
- Runtime provenance with package, Python, dependency, and Git revision metadata.
- Exact reproducibility constraints for Python 3.11-3.13.
- ZIP archive safety limits and bounded member reads.
- Centralized benchmark configuration, calibration utilities, and numerical utilities.
- GitHub Actions matrix tests, coverage gate, wheel build/install smoke test, and full U373 reproduction workflow.

### Fixed
- `wrong_link` corruption is now local to one frame rather than behaving like a persistent ID switch.
- Empty/out-of-bounds appearance descriptors now retain the fixed 28-value contract.
- Cross-stage artifacts are joined by scenario ID rather than positional order.
- HMM transition rows remain finite and stochastic when transition evidence is absent.
- Baseline metadata now reports only the features actually used for matching.

### Performance
- Soft-dynamics transition accumulation now uses indexed adjacency instead of an all-pairs O(E^2) scan while retaining equivalent benchmark outputs.

### Validation status
- 50/50 tests pass on Python 3.11, 3.12, and 3.13.
- Package coverage: 69% with a 65% enforced CI gate.
- Full pinned U373 reproduction succeeds after the architecture/performance refactor.
- Technical benchmark gate: complete.
- Operator-learning gate: HOLD.
- No biological validation claim is made.
