# Dryad three-experiment confirmatory validation — local Mac runbook

Status: **pre-outcome pipeline prepared; real source schema must be inspected locally before the schema lock can be finalized.**

This runbook resumes the originally registered three-experiment Dryad confirmatory arm while preserving the historical Stage E `REVISE` decision and the already-completed `n=1` fallback result. The only change is data acquisition: the Dryad files are downloaded on the local workstation because GitHub-hosted runners received HTTP 403/401 from the public download endpoints.

## Scientific boundary

The pipeline is deliberately split into gates. The first local command verifies the deposited Dryad file identity and inventories file names/schema only. It does **not** calculate tracking-method performance. The real source-member mapping must then be committed in `docs/dryad-confirmatory-schema-lock.json` with `status: LOCKED` before normalization or confirmatory evaluation can run.

No Dryad-specific parameter tuning is allowed. The frozen configuration remains:

- 64 association hypotheses;
- maximum speed gate `1.5 µm/min`;
- pairwise proposal temperature = maximum allowed pairwise link distance / 2;
- calibration temperature `0.25`;
- posterior tracking threshold `0.5`;
- seed `20260922`.

The biological replicate is the **experiment**, not the cell or track. Final biological `n = 3`.

## Local directories

Use only ignored local directories for third-party data and generated results:

```text
data/raw/dryad/
    To Generate Figures.zip
    README_for_To Generate Figures.docx

results/dryad/
    source-inventory.json
    normalized/
        experiment_1.csv
        experiment_2.csv
        experiment_3.csv
        normalized-manifest.json
    confirmatory-result.json
```

`data/raw/*`, `results/*`, and `*.zip` are already excluded by `.gitignore`. Raw Dryad data must not be committed.

## 1. Environment

From the repository root on macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -c constraints.txt -e '.[dryad]'
```

The optional `dryad` extra installs source-inspection support for `.xlsx` and MATLAB `.mat` members. Confirmatory evaluation itself uses the core package and normalized CSV files.

## 2. Acquire the frozen Dryad source locally

Download from Dryad DOI `10.5061/dryad.s4d28`:

- `To Generate Figures.zip`
- `README_for_To Generate Figures.docx`

Place both files unchanged under `data/raw/dryad/`.

The repository already freezes the deposited MD5 identities:

```text
To Generate Figures.zip                  2b70accfbb4d81d41dfb10fcefa60cbf
README_for_To Generate Figures.docx      fcbd2b285b860eb18d7ce600becda06d
```

Do not rename, unzip, edit, recompress, or open the tracking tables before Gate A/B inventory. The inventory command opens the archive only after verifying the deposited digest.

## 3. Gate A/B — source identity + schema-only inventory

Run:

```bash
gbm-dryad-local inventory \
  --source-dir data/raw/dryad \
  --source-manifest docs/external-biological-context-source-manifest.json \
  --output results/dryad/source-inventory.json
```

Expected terminal message:

```text
Wrote schema-only inventory: results/dryad/source-inventory.json
```

The command verifies the source MD5 and size, computes an additional local SHA-256, checks ZIP safety limits, lists archive members, and previews only table/schema metadata where safe. It does not calculate uncertainty, tracking, motion, or method-comparison outcomes.

**STOP HERE after the first real run.** Review `results/dryad/source-inventory.json` and freeze the exact three-experiment source mapping in `docs/dryad-confirmatory-schema-lock.json` before proceeding. This stop is intentional and is part of the preregistered leakage boundary.

## 4. Gate C — commit the real schema lock

After schema review, `docs/dryad-confirmatory-schema-lock.json` must contain, for each of `experiment_1`, `experiment_2`, and `experiment_3`:

- exact archive member path(s);
- file format;
- sheet name or MATLAB variable if applicable;
- delimiter/header row if text;
- exact track/frame/time/x/y/cell-type mapping;
- accepted glioma/tumour cell-type values;
- coordinate conversion to micrometres;
- time conversion to minutes or a frozen frame interval;
- the unchanged inclusion rule.

Only after this mapping has been reviewed and committed should `status` become `LOCKED`.

## 5. Gate D — normalize all three experiments

After the committed schema lock is `LOCKED`:

```bash
gbm-dryad-local normalize \
  --source-dir data/raw/dryad \
  --source-manifest docs/external-biological-context-source-manifest.json \
  --schema-lock docs/dryad-confirmatory-schema-lock.json \
  --output-dir results/dryad/normalized
```

The normalizer writes the canonical columns:

```text
experiment_id,cell_type,track_id,frame,time_min,x_um,y_um
```

It refuses ambiguous mappings, non-finite coordinates, duplicate track/frame observations, non-increasing time, missing experiment identities, digest drift, or an unlocked schema. It records SHA-256 hashes for each normalized experiment and the exact schema-lock hash in `normalized-manifest.json`.

This step still computes no tracking-method performance.

## 6. Gate E/F — one confirmatory evaluation

Run once after the normalized files have passed review:

```bash
gbm-dryad-confirmatory \
  --normalized-dir results/dryad/normalized \
  --schema-lock docs/dryad-confirmatory-schema-lock.json \
  --output results/dryad/confirmatory-result.json
```

The evaluator uses the same frozen configuration on all three experiments. It reports:

- association-error AUPRC: calibrated uncertainty versus distance confidence;
- selective link risk at 80% coverage and full coverage;
- Brier, ECE and NLL calibration metrics;
- hard-NN and uncertainty-compatible link precision/recall/F1;
- reference, hard-NN and uncertainty-aware motion summaries;
- mean-speed, path-length, net-displacement and directionality errors;
- signed paired effects for each experiment;
- within-experiment track-cluster bootstrap for the registered association/link endpoints;
- replicate-aware `n=3` bootstrap summaries across experiments.

Positive effect orientation is explicitly encoded in the output. The small-`n` result remains descriptive/sensitivity evidence and must not be presented as precise population-level inference.

## 7. What is committed after the local run

Do **not** commit the raw Dryad archive or generated normalized CSVs. The intended final evidence committed to GitHub is:

- the locked schema mapping;
- source identities/hashes;
- the confirmatory evaluator code and tests;
- the small machine-readable `confirmatory-result.json` copied into `docs/` only after verification;
- a final report describing all three experiments, including negative results;
- updated README/architecture/reproduction documentation.

## Hard-stop rules

Stop rather than improvise if any of these occurs:

1. source digest mismatch;
2. fewer than three unambiguous experiment identities;
3. tumour/glioma tracks cannot be separated from microglia without subjective choices;
4. time-resolved x/y trajectories cannot be reconstructed without guessing;
5. source format needs an outcome-guided exclusion or parameter choice;
6. deposited reference tracks appear to be produced by the same method being evaluated.

The pipeline is designed to fail closed at these boundaries.
