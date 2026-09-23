# Release notes — v1.0.0

Release date: 2026-09-22.

`v1.0.0` is the final technical project closure release for the GBM tracking uncertainty audit.

## Highlights

- Closes the full A-E technical research line.
- Keeps the qualified Stage D v3 `GO`: calibrated Huh7 sequence-`01` blend generalizes to locked Huh7 sequence `02`.
- Publishes the Stage E-Final one-time locked `REVISE`: the run was valid, but calibrated error AUPRC did not beat the distance baseline on both real tests and uncertainty won only four of eight registered motion comparisons.
- Adds final closure documentation, release notes and project-level claim boundaries.
- Advances the Python package version to `1.0.0`.

## Evidence included in the release

- `docs/project-closure-report.md`
- `docs/final-project-report.md`
- `docs/stage-d-closure-report.md`
- `docs/stage-e-final-report.md`
- `docs/stage-e-sequence02-evaluation.json`
- `docs/stage-e-sequence02-evaluation-lock.json`
- `docs/reproduction.md`

## Supported claim

This release supports a reproducible technical audit claim: the repository implements leakage-controlled cell-tracking uncertainty evaluation and documents where uncertainty-aware methods pass, hold, or require revision under locked technical benchmarks.

## Unsupported claims

This release does not support human GBM biological validation, a migration phenotype, perturbation effects, animal-level population inference, patient-level inference or clinical utility.

## Validation

The release workflow validates the tagged commit by installing the pinned environment, checking that `v1.0.0` matches `gbm_audit.__version__`, running the unit/integration suite with the coverage gate, building a wheel, reinstalling that wheel in a clean virtual environment, and creating a GitHub Release.

## Post-release evidence extension — 2026-09-23

This section records evidence added **after** the `v1.0.0` release. It is not backdated into the original tagged release and does not change the package version or the historical Stage E decision.

The originally selected Dryad external glioma arm (`doi:10.5061/dryad.s4d28`) was completed locally under the already frozen no-retuning configuration after GitHub-hosted source-download authorization failures. Source hashes were verified, the three-experiment tumour-track schema was committed as `LOCKED` before outcomes, normalization passed structural QC, and the confirmatory evaluator was executed once.

Biological `n=3` consisted of three independent rat PDGFB-glioma brain-slice experiments with 100, 190 and 50 tumour tracks.

The result is mixed:

- calibrated uncertainty improved association-error AUPRC over distance confidence in all three experiments; mean uncertainty-minus-distance effect `+0.596419`;
- selective-risk benefit was positive in all three experiments; mean `+0.079359`;
- frozen uncertainty-compatible `p >= 0.5` link F1 was below hard nearest-neighbour F1 in all three experiments; mean uncertainty-minus-hard effect `-0.012764`;
- mean-speed, path-length and net-displacement fidelity also favoured hard NN; directionality was mixed.

This extension supports external **technical transfer** of uncertainty ranking/calibration/selective-risk behavior in rat glioma brain-slice data. It does not support human GBM-wide validation, clinical utility or a claim that the frozen uncertainty-compatible hard tracker is superior.

Post-release evidence:

- `docs/dryad-confirmatory-schema-lock.json`
- `docs/dryad-confirmatory-final-report.md`
- `docs/dryad-confirmatory-result.json.gz`
- `docs/external-biological-context-final-report.md`

Stage E remains `REVISE`.
