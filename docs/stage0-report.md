# Stage 0 evidence and original decision

> Historical record: the manual-pilot recommendation below was superseded by the 2026-09-19 [human-independent pivot](pivot-2026-09-19.md). The evidence remains valid; the next gate is now the U373 reference benchmark.

Date: 2026-09-18. Status: **GO for a small, manually annotated tracking pilot; no GO for downstream biological inference yet.** Two genuine ROIs, one from each mouse, were inspected. A full-project GO decision remains premature.

## Verified from primary source records

- [GlioTrace example data](https://zenodo.org/records/21981544): 5.6 GB archive; two mouse subfolders; separate GFP and Lectin-594 channels. The [archive preview](https://zenodo.org/records/21981544/preview/Example_data.zip?include_deleted=0) lists **231 genuine ROI `.npz` files across 11 experiments** (329–339) in sets 67 and 68, alongside macOS metadata sidecars that are not image stacks. Record does not advertise gold tracking or segmentation annotations. Two complete ROI files and their archive CRCs were verified. Their arrays are **time × 501 × 501**, contradicting the Zenodo description (height × width × time). Both files also have an all-zero `Bstack` and scalar `delta`.
- The actual [metadata.csv](https://zenodo.org/records/21981544/files/metadata.csv?download=1) lists 11 experiments from cell line U3028MG, with `delta_t` **1.45** for set 67 and **1.35** for set 68, and 64–100 reported frames per experiment. The CSV has no explicit time unit for `delta_t`; the source description says acquisition intervals up to two hours. Controls and dasatinib/thapsigargin treatments occur in both sets. Do not hard-code two hours per frame.
- [Current Python implementation](https://github.com/Gliomethods/GlioTrace): Apache-2.0, Python 3.11–3.13, documents about 3.5 hours for its larger demo on a 16 GB M2 Mac. This estimate is not a benchmark of our pipeline or machine.
- Code-level inspection of its [stack loader](https://github.com/Gliomethods/GlioTrace/blob/main/src/gliotrace/gliotrace_class.py) and [preprocessor](https://github.com/Gliomethods/GlioTrace/blob/main/src/gliotrace/visualize/preprocess_stack.py) confirms it reads the real `.npz` keys directly and rearranges the time axis; on the inspected arrays an equivalent transformation gives `(496, 496, 65)` and `(496, 496, 68)` internally. Its metadata path assumes comma-separated CSV while the published `metadata.csv` uses semicolons. Supply a DataFrame parsed with `pd.read_csv(path, sep=';')`. This is a source-level compatibility assessment; the complete GlioTrace inference has not run here because the runtime lacks its deep-learning dependencies.
- [U373 challenge](https://celltrackingchallenge.net/2d-datasets/): 15-minute intervals; phase-contrast images on polyacrylamide, so it can test technical tracking but cannot validate brain-slice biology. The actual 43,454,399-byte training archive was downloaded and audited below.
- [T98G expert-curated data](https://zenodo.org/records/19026908): 147.7 MB archive; 37 frames, expert-curated masks/lineages, under an electric field. It is an independent technical benchmark with a different assay.
- [GL261 two-photon data](https://zenodo.org/records/20818262): 41.9 GB; no verified per-cell tracking ground truth on the record. Deferred.

## Reproducibility checks and observed training archive

The CLI inventories ZIP files, records SHA256, and inspects NumPy headers without reading all pixels. Run: `python -m gbm_audit.cli data/raw/PhC-C2DH-U373.zip --output results/ctc-audit.json` and `python -m gbm_audit.cli data/raw/single-extracted-roi.npz --output results/glio-roi-audit.json`.

The official U373 training ZIP downloaded successfully. SHA256: `b18185c18fce54e8eeb93e4bbb9b201d757add9409bbf2283b8114185a11bc9e`. It contains two sequences (`01`, `02`), each with **115 image frames and 115 gold tracking masks**. Gold segmentation masks are sparse: **15** and **19** frames respectively. Tracking lineage tables are present for both sequences (8 and 12 rows). An actual TIFF image and its mask were decoded: image is 520 × 696 pixels, `uint8`; tracking IDs appear in the mask. This establishes the technical benchmark input and annotations, but does not establish GlioTrace image quality.

Running the reference-track profiler on all frames recovered 8 and 12 tracking identities, with 757 and 680 consecutive frame-to-frame steps. Median center displacement is 3.162 and 2.236 pixels per frame, respectively. Those numbers validate array/lineage parsing and do **not** estimate GBM brain-slice movement.

| Actual GlioTrace sample | Data verified | Shared rectangular view across its frames | Important limitation |
| --- | --- | --- | --- |
| Set 67, thapsigargin 4 µM, exp 333 ROI 84 | SHA256 `7878bdb3541d365e96f504be1e7958f2e3b3cca68783f253a2672e264f718b57`; T/V/B `(65, 501, 501)`; delta 1.45 | 76.02% of the original rectangular frame | CSV says **64 frames**, array has **65**; the exact timing convention needs resolution. |
| Set 68, thapsigargin 4 µM, exp 337 ROI 63 | SHA256 `1c40f8519930e023530b4912c826e7e231f2270aa2c15023c21461783e86a265`; T/V/B `(68, 501, 501)`; delta 1.35 | 55.79% of the original rectangular frame | Black borders expand during the sequence, so naïve cell disappearance and tracking fragmentation are biased. |

In both samples `Bstack` is entirely zero. Visual checks of early, middle, and late frames found some bright tumor-channel objects persisting, along with dim/overlapping objects. This supports attempting a limited manual tracking pilot, not assuming all cells can be reliably tracked. The common-view percentages are bounding-rectangle diagnostics from the V channel, not measured biological area. The ROI files and diagnostic images remain outside Git pending clarification of dataset redistribution rights.

## Requirements for the next gate (manual pilot)

1. Resolve physical pixel size and time convention (the CSV frame count for exp 333 differs from its NPZ length by one). Test whether border loss and intensity variation seen here recur in representative control ROIs.
2. Curate a small manual tracking set including easy and hard intervals from both mice. Check whether the same-cell identity is discernible and whether annotation disagreements can be resolved.
3. Freeze a mouse/sequence-level split and define minimum usable track length based on actual measured intervals.
4. Check actual download rights for distributing anything derived from the raw dataset; keep raw images outside the repository until clarified.

**Decision:** Stage 0 completed with **GO to Stage 1, manual annotation only**. The actual images, compatible Python implementation, and a genuine technical tracking reference dataset make a constrained pilot feasible. Large-scale uncertainty-aware inference remains *unverified*; the next gate requires manually reviewed tracks before model development.

**Scope and cost:** Around 28.4 MB of brain-slice ROI files and a 43.5 MB U373 training ZIP were transferred instead of downloading the 5.6 GB full archive. Runtime and GPU feasibility on the user's own computer have not been measured. No LLM token or monetary usage accounting is available from this audit. The two sampled ROIs are both treated; biological treatment comparisons require control ROIs.
