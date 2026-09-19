# Glioblastoma tracking uncertainty: feasibility pilot

Goal: measure how known segmentation/tracking errors change migration and image-derived latent-state estimates, and whether calibrated uncertainty makes those conclusions more reliable. Existing expert annotations provide the quantitative reference; GlioTrace brain-slice images are an exploratory application. The repository contains no validated biological phenotype claim.

## Current gate

**GO to Stage 1: freeze and verify the U373 reference benchmark.** The earlier human-annotation gate was not executed because independent reviewers became unavailable. Existing work is retained, while quantitative validation moves to public expert annotations and seeded controlled corruptions. See the [pivot decision](docs/pivot-2026-09-19.md), [evidence report](docs/stage0-report.md), and [revised gates](docs/roadmap.md).

## Sources

- Primary images: [GlioTrace example data, Zenodo 21981544](https://zenodo.org/records/21981544), two mice, `Example_data.zip` (5.6 GB) and `metadata.csv`. Its published axis description conflicts with one real array header; verify with `--expected-frames`.
- Reference implementation: [Gliomethods/GlioTrace](https://github.com/Gliomethods/GlioTrace), Python, Apache-2.0; do not confuse with the older MATLAB repository under `shipsauce`.
- Technical benchmark: [Cell Tracking Challenge U373](https://celltrackingchallenge.net/2d-datasets/), phase-contrast cells on a substrate, not brain slices.
- Secondary technical benchmark: [T98G electrotaxis](https://zenodo.org/records/19026908), manually curated masks and lineages, not brain-slice invasion.

Raw data do not belong in this Git repository. The GlioTrace dataset page does not display a clear reusable license; confirm rights before redistribution.

## To reproduce the small pilot without downloading 5.6 GB

Install Python 3.11–3.13 and NumPy, then from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
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

Stage 1 now freezes U373 sequence-level splits, verifies reference identities, centroids and lineages, and emits a machine-readable benchmark manifest. Stage 2 will inject seeded, fully known tracking errors into those reference tracks. T98G is an independent confirmation dataset after its archive schema passes a separate audit.

On Windows PowerShell, use `.venv\Scripts\Activate.ps1` instead of `source .venv/bin/activate`.
