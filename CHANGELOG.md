# Changelog

All notable project changes are documented here. The project follows semantic versioning from `0.1.0` onward.

## Post-release evidence extension - 2026-09-23

### Added
- Hash-verified local-resumption workflow for the originally selected Dryad `10.5061/dryad.s4d28` external glioma source after GitHub-hosted file-download authorization failures.
- Hardened Dryad archive inventory that ignores macOS AppleDouble metadata and permits legitimate high-compression non-table assets while retaining fail-closed table validation.
- Schema-only probe for legacy XLS, MATLAB `StoreData`, deposited MATLAB source contexts and README evidence.
- Committed pre-outcome `LOCKED` mapping for three independent rat PDGFB-glioma brain-slice tumour-track experiments.
- Deterministic normalization with exact source time retained and `global_time_rank` frame derivation.
- One-time frozen three-experiment confirmatory evaluator and replicate-aware descriptive/sensitivity statistics.
- Frozen machine-readable result `docs/dryad-confirmatory-result.json.gz` and final report `docs/dryad-confirmatory-final-report.md`.

### Result
- Association-error AUPRC uncertainty-minus-distance was positive in 3/3 experiments; mean effect `+0.596419`.
- Selective-risk benefit was positive in 3/3 experiments; mean effect `+0.079359`.
- Frozen uncertainty-compatible `p >= 0.5` link-F1 effect versus hard NN was negative in 3/3 experiments; mean effect `-0.012764`.
- Mean-speed, path-length and net-displacement fidelity also favoured hard NN; directionality was mixed.
- The result supports external technical transfer of calibrated confidence/error-ranking and selective-risk behavior, not superiority of the frozen hard tracker.
- Historical Stage E remains `REVISE`; no human GBM-wide or clinical validation claim is added.

### Documentation
- README, roadmap, project closure report, consolidated final report, local runbook and external biological-context final report now distinguish the original v1.0.0 technical closure from the completed post-release Dryad evidence extension.
- The earlier `n=1` TrackMate fallback remains preserved as historical external evidence.

## [1.0.0] - 2026-09-22

### Added
- Frozen Stage E-Final multi-domain technical-validation protocol with explicit supported and unsupported claims, registered endpoints, and GO/REVISE/STOP rules.
- Verified CTC GOWT1, HeLa, and SIM+ dataset manifest with archive SHA-256 identities, annotation metadata, and structural counts.
- Immutable sequence-level split assigning sequence `01` to development and sequence `02` to locked evaluation, with consumed U373, T98G, and Huh7 sources excluded from new confirmation.
- Artifact-contract tests that enforce the manifest hashes, split roles, untouched test state, and biological-claim boundary.
- Generic CTC archive reader with a sequence-`02` decode boundary, plus dependency-free association AUPRC, selective-risk and calibration metrics.
- Frozen three-domain sequence-`01` development fit and a dedicated GitHub Actions reproduction workflow; no sequence-`02` outcome was accessed.
- One-time locked Stage E-Final sequence-`02` evaluation artifact and final report. The valid decision is `REVISE`: selective-risk, calibration, provenance, leakage and reproducibility gates passed; the real-data AUPRC gate and the motion-win gate failed.
- Final project closure report and v1.0.0 release notes documenting the completed technical scope, Stage D `GO`, Stage E `REVISE`, and claim boundary.

### Changed
- Package version advanced to `1.0.0` for the final technical project closure.
- README, roadmap, reproduction guide, portfolio summary, and consolidated project report now describe the complete A-E project state.

### Validation status
- Final project state: closed as a reproducible technical/research-engineering portfolio artifact.
- Biological, GBM brain-slice, treatment-effect, and clinical claims remain unsupported.

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
- Project status, roadmap, portfolio summary, and README now consistently record the qualified Stage D v3 `GO`.
- Package version advanced to `0.2.0` for the completed Stage A-D technical research line.

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
