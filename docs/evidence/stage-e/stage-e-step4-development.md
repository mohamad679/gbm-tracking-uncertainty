# Stage E-Final development implementation and fit

Date: 2026-09-22. Status: **DEVELOPMENT CONFIGURATION FROZEN PENDING CI**.

## Completed work

The generic Cell Tracking Challenge reader, registered nearest-neighbour
baseline, uncertainty metrics and development-only runner are implemented in
`stage_e_data.py`, `stage_e_metrics.py` and `stage_e_development.py`.
The runner first verifies each official archive identity and performs a
structural audit of both sequences. It decodes image and tracking-mask pixels
only for sequence `01`; sequence `02` remains a schema-and-counts-only
audit.

The compact, machine-readable result is
[`stage-e-development-fit.json`](stage-e-development-fit.json). It contains
only development summaries, selected parameters and structural audits; it does
not contain any locked-test coordinate, tracking or endpoint result.

## Frozen development configuration

| Dataset | Role | Selected maximum speed | Selected radius |
| --- | --- | ---: | ---: |
| GOWT1 | Real fluorescence confirmation | 1.50 µm/min | 31.25 px |
| HeLa | Real DIC confirmation | 1.25 µm/min | 65.7895 px |
| SIM+ | Synthetic diagnostic | 0.20 µm/min | 46.40 px |

Each value was selected over the pre-registered eight-value speed grid by
clean sequence-`01` nearest-neighbour link F1, with exact ties resolved toward
the smaller gate. The uncertainty evaluator uses 64 one-to-one hypotheses;
temperature scaling is fit only on the corresponding corrupted sequence-`01`
development scenarios.

## Access and claim boundary

- The three official archive SHA-256 values match the frozen manifest.
- Sequence `02` TIFF pixels were not decoded.
- No sequence-`02` coordinates were extracted, metrics computed or outcomes
  evaluated.
- This is not a locked-test result and supports no biological, brain-slice or
  clinical claim.

The next permitted action is CI validation and committing this complete
development configuration. Only then may the one-time locked sequence-`02`
evaluation begin.
