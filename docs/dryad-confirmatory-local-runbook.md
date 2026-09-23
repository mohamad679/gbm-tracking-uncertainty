# Dryad three-experiment confirmatory validation — local Mac runbook

Status: **real source schema reviewed and LOCKED pre-outcome; Gate D normalization is next.**

This runbook resumes the originally registered three-experiment Dryad confirmatory arm while preserving the historical Stage E `REVISE` decision and the already-completed `n=1` fallback result. The only acquisition change is that the Dryad files are downloaded on the local workstation because GitHub-hosted runners received HTTP 403/401 from the public download endpoints.

## Scientific boundary

The pipeline is deliberately split into gates. Source identity, archive structure, legacy XLS headers, MATLAB `StoreData` structure, deposited MATLAB code, and deposited README documentation were inspected without calculating tracking-method performance. The resulting mapping has now been committed in `docs/dryad-confirmatory-schema-lock.json` with `status: LOCKED` before normalization or confirmatory evaluation.

No Dryad-specific parameter tuning is allowed. The frozen configuration remains:

- 64 association hypotheses;
- maximum speed gate `1.5 µm/min`;
- pairwise proposal temperature = maximum allowed pairwise link distance / 2;
- calibration temperature `0.25`;
- posterior tracking threshold `0.5`;
- seed `20260922`.

The biological replicate is the **experiment**, not the cell or track. Final biological `n = 3`.

## Locked source mapping

The deposited `MasterFigures_Control.m` identifies the tumour datasets as:

- `experiment_1`: `GFPOrlando` — deposited README identifies this as the c1 `5-16-11` tumour/GFP tracking data;
- `experiment_2`: `6-6-11_Tumor_Tracking_Data`;
- `experiment_3`: `3-14-11_Tumor_Tracking_Data`.

All three normalized inputs use the deposited MATLAB `StoreData` convention documented by the source analysis code:

```text
column 1 = elapsed time in hours
column 2 = cell/track identifier
column 3 = x coordinate in µm
column 4 = y coordinate in µm
```

The deposited source has irregular acquisition timing in places. Therefore canonical `frame` is **not** reconstructed from a fixed interval. It is the deterministic sorted rank of each distinct global elapsed-time value within an experiment. Exact source elapsed time is retained and converted from hours to minutes for pairwise `dt` and motion calculations.

The deposited README separately mentions `3-4-14C2` in the PIV/supplementary-movie context. The locked single-cell tracking schema does not equate that PIV label with the explicitly named `3-14-11_Tumor_Tracking_Data` member used by `MasterFigures_Control.m` as experiment 3.

## Local directories

Use only ignored local directories for third-party data and generated results:

```text
data/raw/dryad/
    To Generate Figures.zip
    README_for_To Generate Figures.docx

results/dryad/
    source-inventory.json
    schema-evidence.json
    normalized/
        experiment_1.csv
        experiment_2.csv
        experiment_3.csv
        normalized-manifest.json
    confirmatory-result.json
```

`data/raw/*`, `results/*`, and `*.zip` are excluded by `.gitignore`. Raw Dryad data must not be committed.

## 1. Environment

From the repository root on macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -c constraints.txt '.[dryad]'
```

The optional `dryad` extra installs source-inspection support for `.xlsx`, legacy `.xls`, and MATLAB `.mat` members. Confirmatory evaluation itself uses the core package and normalized CSV files.

## 2. Acquire the frozen Dryad source locally

Download from Dryad DOI `10.5061/dryad.s4d28`:

- `To Generate Figures.zip`
- `README_for_To Generate Figures.docx`

Place both files unchanged under `data/raw/dryad/`.

The repository freezes the deposited MD5 identities:

```text
To Generate Figures.zip                  2b70accfbb4d81d41dfb10fcefa60cbf
README_for_To Generate Figures.docx      fcbd2b285b860eb18d7ce600becda06d
```

The source identity must match before any archive member is inspected.

## 3. Gates A/B — source identity and schema-only evidence

Source inventory:

```bash
gbm-dryad-local inventory \
  --source-dir data/raw/dryad \
  --source-manifest docs/external-biological-context-source-manifest.json \
  --output results/dryad/source-inventory.json
```

Schema evidence probe:

```bash
gbm-dryad-schema-probe \
  --source-dir data/raw/dryad \
  --source-manifest docs/external-biological-context-source-manifest.json \
  --output results/dryad/schema-evidence.json
```

These commands verify source identity and inspect only schema/documentation evidence. They do not calculate uncertainty, association, tracking, motion, or method-comparison outcomes.

## 4. Gate C — committed schema lock

Gate C is complete. `docs/dryad-confirmatory-schema-lock.json` is `LOCKED` with:

- exact tumour-only MATLAB source member for each of the three experiments;
- `StoreData` as the MATLAB variable;
- exact column mapping `time, track, x, y`;
- tumour/glioma identity by dedicated source-member separation from microglia;
- coordinate scale `1.0` to µm;
- time scale `60.0` from hours to minutes;
- deterministic `global_time_rank` frame reconstruction;
- unchanged all-eligible-observation inclusion rule.

This lock was committed before any Dryad confirmatory method-performance calculation. If normalization now exposes a source-format inconsistency, stop rather than changing the mapping based on downstream outcomes.

## 5. Gate D — normalize all three experiments

Pull the commit containing the locked schema and frame adapter, reinstall the package, then run:

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

It refuses ambiguous mappings, non-finite coordinates, duplicate track/frame observations, non-increasing time, missing experiment identities, digest drift, or an unlocked schema. For the locked Dryad mapping it also records the deterministic global-time-rank frame count and exact time range. SHA-256 hashes for each normalized experiment and the exact schema-lock hash are written to `normalized-manifest.json`.

This step still computes **no tracking-method performance**.

After normalization, inspect and share `results/dryad/normalized/normalized-manifest.json` before running the confirmatory evaluator. Structural QC may be reviewed at this point; no method-performance result should yet be generated.

## 6. Gates E/F — one confirmatory evaluation

Run once only after the normalized manifest has passed structural review:

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
- source identities/hashes and schema evidence provenance;
- the confirmatory evaluator code and tests;
- the small machine-readable `confirmatory-result.json` copied into `docs/` only after verification;
- a final report describing all three experiments, including negative results;
- updated README/architecture/reproduction documentation.

## Hard-stop rules

Stop rather than improvise if any of these occurs:

1. source digest mismatch;
2. fewer than three unambiguous experiment identities;
3. tumour/glioma tracks cannot be separated from microglia without subjective choices;
4. time-resolved x/y trajectories cannot be reconstructed without the locked mapping;
5. source format needs an outcome-guided exclusion or parameter choice;
6. deposited reference tracks appear to be produced by the same method being evaluated.

The pipeline is designed to fail closed at these boundaries.
