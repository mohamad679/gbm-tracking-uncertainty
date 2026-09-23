# Dryad three-experiment confirmatory validation — local Mac runbook

Status: **COMPLETE**. Source identity, schema-only inspection, committed schema lock, normalization, structural QC and the one-time frozen confirmatory evaluation have all been completed.

This runbook records the exact local path used to resume the originally registered three-experiment Dryad arm after GitHub-hosted public download routes returned HTTP 403/401. The acquisition workaround changed only where the already-frozen public files were downloaded; it did not change the scientific target, method configuration, Stage E decision, or endpoint definitions.

## Scientific boundary

The completed pipeline preserves these boundaries:

- historical Stage E remains `REVISE`;
- no Dryad-specific parameter fitting or retuning was performed;
- the experiment is the biological replicate (`n = 3`), not the cell or track;
- the final claim is external **technical transfer** in rat glioma brain-slice experiments, not human GBM-wide or clinical validation;
- with `n = 3`, experiment-level intervals are descriptive/sensitivity evidence rather than precise population-level inference.

Frozen configuration:

- 64 association hypotheses;
- maximum speed gate `1.5 µm/min`;
- pairwise proposal temperature = maximum allowed pairwise link distance / 2;
- calibration temperature `0.25`;
- posterior tracking threshold `0.5`;
- seed `20260922`.

## Locked source mapping

The deposited `MasterFigures_Control.m` identifies the tumour datasets as:

- `experiment_1`: `GFPOrlando` — c1 `5-16-11` tumour/GFP tracking data;
- `experiment_2`: `6-6-11_Tumor_Tracking_Data`;
- `experiment_3`: `3-14-11_Tumor_Tracking_Data`.

The deposited MATLAB analysis defines `StoreData` as:

```text
column 1 = elapsed time in hours
column 2 = cell/track identifier
column 3 = x coordinate in µm
column 4 = y coordinate in µm
```

Canonical time is converted to minutes. Because acquisition timing is irregular in places, canonical `frame` is the deterministic sorted rank of each distinct global elapsed-time value, while exact source elapsed time is retained for pairwise `dt` and motion calculations.

The committed lock is `docs/dryad-confirmatory-schema-lock.json` with `status: LOCKED`.

## Local source identities

Place the unchanged Dryad files under `data/raw/dryad/`:

```text
To Generate Figures.zip
README_for_To Generate Figures.docx
```

Frozen MD5 identities:

```text
To Generate Figures.zip                  2b70accfbb4d81d41dfb10fcefa60cbf
README_for_To Generate Figures.docx      fcbd2b285b860eb18d7ce600becda06d
```

Raw third-party source files and generated normalized CSVs remain local and are not committed.

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -c constraints.txt '.[dryad]'
```

## Gates A/B — source identity and schema-only evidence

```bash
gbm-dryad-local inventory \
  --source-dir data/raw/dryad \
  --source-manifest docs/external-biological-context-source-manifest.json \
  --output results/dryad/source-inventory.json

gbm-dryad-schema-probe \
  --source-dir data/raw/dryad \
  --source-manifest docs/external-biological-context-source-manifest.json \
  --output results/dryad/schema-evidence.json
```

These commands inspect identity/schema/documentation only. They do not calculate method-performance outcomes.

## Gate C — schema lock

Complete before outcomes. The committed lock freezes the exact source members, `StoreData` mapping, tumour-only identity, unit conversions, global-time-rank frame rule and all-eligible-observation inclusion rule.

## Gate D — normalization

```bash
gbm-dryad-local normalize \
  --source-dir data/raw/dryad \
  --source-manifest docs/external-biological-context-source-manifest.json \
  --schema-lock docs/dryad-confirmatory-schema-lock.json \
  --output-dir results/dryad/normalized
```

Observed structural QC from the completed run:

| Experiment | Tracks | Observations | Global frames | Time range (min) |
| --- | ---: | ---: | ---: | ---: |
| 1 | 100 | 7,399 | 74 | 0–1132 |
| 2 | 190 | 19,189 | 101 | 0–300 |
| 3 | 50 | 2,499 | 50 | 0–779 |

No observations were excluded by a cell-type filter; the selected members are dedicated tumour-cell sources.

## Gates E/F — one-time confirmatory evaluation

The evaluator was run once after structural QC:

```bash
gbm-dryad-confirmatory \
  --normalized-dir results/dryad/normalized \
  --schema-lock docs/dryad-confirmatory-schema-lock.json \
  --output results/dryad/confirmatory-result.json
```

Final mixed result:

- association-error AUPRC uncertainty-minus-distance was positive in 3/3 experiments; mean effect `+0.596419`;
- selective-risk benefit was positive in 3/3 experiments; mean effect `+0.079359`;
- uncertainty-compatible p≥0.5 link-F1 effect versus hard NN was negative in 3/3 experiments; mean effect `-0.012764`;
- mean-speed, path-length and net-displacement fidelity were worse for the p≥0.5 uncertainty reconstruction; directionality was mixed;
- candidate-graph reference-link coverage was approximately 99.6%, 97.6% and 99.7%, and the frozen `1.5 µm/min` gate was not retuned.

The detailed interpretation is in `docs/dryad-confirmatory-final-report.md`.

## Committed final evidence

Committed:

- `docs/dryad-confirmatory-local-resumption-protocol.json`;
- `docs/dryad-confirmatory-schema-lock.json`;
- `src/gbm_audit/dryad_local.py` / `dryad_local_safe.py` / `dryad_schema_probe.py`;
- `src/gbm_audit/dryad_confirmatory.py`;
- tests and CI validation;
- `docs/dryad-confirmatory-final-report.md`;
- `docs/dryad-confirmatory-result.json.gz` — deterministic gzip of the one-time result.

The compressed result SHA-256 is `371e67c0ec026f4ea0ffa9e89748b9c55bcc612a3cee2ef7df9c0363261b1e31`; the uncompressed JSON SHA-256 is `7eb61dc829ad0eb7076dd46801d8e2f2a4863f6369494115ef0353be6ec6139f`.

## Hard-stop rule for any future reproduction

If a future reproduction encounters digest drift, ambiguous tumour/microglia identity, schema drift, or a need for outcome-guided remapping/retuning, stop rather than adapting the frozen analysis. The completed result is historical evidence and must not be optimized retrospectively.
