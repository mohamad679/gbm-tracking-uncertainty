# Glioblastoma tracking uncertainty: feasibility pilot

Goal: measure how known segmentation/tracking errors change migration and image-derived latent-state estimates, and whether calibrated uncertainty makes those conclusions more reliable. Existing expert annotations provide the quantitative reference; GlioTrace brain-slice images are an exploratory application. The repository contains no validated biological phenotype claim.

## Current gate

**Technical benchmark package complete; HOLD before SLDS/Koopman.** The reference benchmark, controlled corruptions, uncertainty, downstream HMM sensitivity, proposal sweeps, and raw-image negative control are reproducible. See the [final project report](docs/final-project-report.md), [final reproduction guide](docs/reproduction.md), and [final audit JSON](results/final-audit.json after reproduction). No validated biological claim is made.

## Release and reproducibility contract

The current package version is **0.1.0**. Supported Python versions are **3.11, 3.12, and 3.13**. Runtime dependency ranges are declared in `pyproject.toml`; the exact dependency set used by the validated GitHub Actions reproduction is pinned in `constraints.txt`.

For a byte-for-byte controlled software environment, install with:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints.txt -e .
```

The final audit records package version, Python version, dependency versions, and the Git commit SHA supplied by the reproduction workflow. Source code is licensed under the MIT License; dataset licenses and redistribution terms remain separate and must be respected independently.

## Sources

- Primary images: [GlioTrace example data, Zenodo 21981544](https://zenodo.org/records/21981544), two mice, `Example_data.zip` (5.6 GB) and `metadata.csv`. Its published axis description conflicts with one real array header; verify with `--expected-frames`.
- Reference implementation: [Gliomethods/GlioTrace](https://github.com/Gliomethods/GlioTrace), Python, Apache-2.0; do not confuse with the older MATLAB repository under `shipsauce`.
- Technical benchmark: [Cell Tracking Challenge U373](https://celltrackingchallenge.net/2d-datasets/), phase-contrast cells on a substrate, not brain slices.
- Secondary technical benchmark: [T98G electrotaxis](https://zenodo.org/records/19026908), manually curated masks and lineages, not brain-slice invasion.

Raw data do not belong in this Git repository. The GlioTrace dataset page does not display a clear reusable license; confirm rights before redistribution.

## Source code map

The complete executable implementation is versioned in this repository:

- `src/gbm_audit/`: Python package for the benchmark, corruption scenarios, tracking baselines, uncertainty propagation, dynamics, proposal sensitivity, and final audit.
- `scripts/`: data-preparation and pilot-download utilities.
- `tests/`: unit and integration tests covering the Python package and reproducibility gates.
- `docs/`: English technical reports and reproduction notes.
- `constraints.txt`: exact dependency versions used by the validated reproducibility environment.
- `LICENSE`: MIT license for this repository's source code.

Generated outputs under `results/` and downloaded raw data under `data/raw/` are intentionally ignored by Git; they can be regenerated with the commands below and are not source code.

## To reproduce the small pilot without downloading 5.6 GB

Install Python 3.11–3.13, then from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints.txt -e .
python scripts/fetch_pilot_rois.py
python -m gbm_audit.roi data/raw/glio_trace/Set_67/exp_333_roi_84_stack.npz --output results/set67-roi.json
python -m gbm_audit.roi data/raw/glio_trace/Set_68/exp_337_roi_63_stack.npz --expected-frames 68 --output results/set68-roi.json
```

The two pinned byte ranges retrieve about 28 MB in total and validate hashes and CRCs before use. They are from the 5.6 GB archive in Zenodo record 21981544, v1. The exp 333 file contains 65 image frames although `metadata.csv` lists 64, so its command deliberately does not assert the CSV frame count. On a computer where the Zenodo URL is unavailable, the script stops without silently downloading the full archive.

The independently downloaded U373 technical benchmark can be audited after placing its training ZIP in `data/raw/`:

```bash
python -m gbm_audit.cli data/raw/PhC-C2DH-U373.zip --output results/ctc-audit.json
python -m gbm_audit.ctc data/raw/PhC-C2DH-U373.zip --output results/ctc-reference-profile.json
```

The archive audit reads directory metadata without unzipping entire archives. `gbm_audit.cli` reads NumPy array *headers*, not full image arrays. Visual inspection remains useful for the exploratory GlioTrace case study but is not a prerequisite for the reference benchmark.

## Archived GlioTrace feasibility pilot

With the two ROI files present locally, `python -m gbm_audit.pilot --output-dir results/stage1-viewer` prepares four fixed ten-frame windows. This viewer is retained for qualitative inspection only. It is not required for the quantitative benchmark, and its machine candidates are not reference tracks.

Machine candidates can be produced with `python -m gbm_audit.proposals` and visualized with `python -m gbm_audit.overlay`. Candidate CSVs and contact sheets stay in ignored `results/`. They are exploratory outputs, never human ground truth.

## Next reproducible stage

Stage 1 now freezes U373 sequence-level splits, verifies reference identities, centroids and lineages, and emits a machine-readable benchmark manifest. See the [Stage 1 reference report](docs/stage1-reference-report.md). Stage 2 injects seeded, fully known tracking errors into those reference tracks. T98G is an independent confirmation dataset after its archive schema passes a separate audit.

The controlled-error benchmark is implemented in `gbm_audit.corruptions`; see the [Stage 2 report](docs/stage2-corruption-report.md). It produces 17 deterministic scenarios with evaluation truth isolated from tracker input.

The frozen nearest-neighbour comparator is implemented in `gbm_audit.baseline`; see the [Stage 3 report](docs/stage3-baseline-report.md). It uses an 8-pixel gate and no gap bridging.

The sampled multi-hypothesis uncertainty evaluator is implemented in `gbm_audit.uncertainty`; see the [Stage 4 report](docs/stage4-uncertainty-report.md). Calibration is fit on development sequence 01 and evaluated unchanged on sequence 02.

Stage 5 migration and HMM sensitivity is implemented in `gbm_audit.dynamics`; see the [Stage 5 report](docs/stage5-dynamics-report.md). The follow-up soft-weighted evaluator is implemented in `gbm_audit.soft_dynamics`; see the [soft dynamics report](docs/stage5-soft-dynamics-report.md). It propagates calibrated link probabilities without p50/p90 thresholding. The current gate-recall limitation means SLDS or Koopman extension is on hold until candidate proposals are improved.

Stage 6 candidate-gate sensitivity is implemented in `gbm_audit.gate_sensitivity`; see the [Stage 6 report](docs/stage6-gate-sensitivity-report.md). It sweeps proposal radii before any learned operator is allowed to consume the tracks.

Stage 7 adds a truth-blind constant-velocity proposal model through `gbm_audit.uncertainty --proposal-model motion`; see the [Stage 7 report](docs/stage7-motion-proposal-report.md). It is retained as a sensitivity comparator, not promoted to the operator-learning input.

Stage 8 tests a motion-plus-area proposal through `--proposal-model motion_area`; see the [Stage 8 report](docs/stage8-multifeature-proposal-report.md). The morphology proxy does not improve aggregate robustness, so raw-image appearance features remain an optional future extension rather than a hidden assumption.

Stage 9 audits a raw-image patch descriptor with `--proposal-model motion_appearance` and `--archive`; see the [Stage 9 report](docs/stage9-raw-appearance-report.md). The handcrafted descriptor improves some speed summaries but fails posterior calibration and is rejected for operator learning.

On Windows PowerShell, use `.venv\Scripts\Activate.ps1` instead of `source .venv/bin/activate`.
