# Stage 1 reference benchmark report

Date: 2026-09-19. Status: **GO** for the controlled tracking benchmark.

## Scope

This gate freezes the Cell Tracking Challenge PhC-C2DH-U373 training archive as a technical reference. It does not validate glioblastoma invasion in brain tissue and does not create a biological Ground Truth for GlioTrace.

## Input and provenance

- Source: [Cell Tracking Challenge 2D datasets](https://celltrackingchallenge.net/2d-datasets/)
- Local archive: `data/raw/PhC-C2DH-U373.zip`
- Size: 43,454,399 bytes
- SHA-256: `b18185c18fce54e8eeb93e4bbb9b201d757add9409bbf2283b8114185a11bc9e`
- Reference content: expert tracking masks and `man_track.txt` lineage tables
- Raw archive remains outside Git; only the derived manifest schema and code are tracked.

## Frozen split and audit results

| Sequence | Role | Frames | Image/mask shape | Tracking masks | Segmentation masks | Lineage rows | Track IDs | Consecutive links |
|---|---|---:|---|---:|---:|---:|---:|---:|
| 01 | development | 115 | 520 × 696 | 115 | 15 | 8 | 8 | 757 |
| 02 | test | 115 | 520 × 696 | 115 | 19 | 12 | 12 | 680 |

The split is sequence-level: adjacent frames never cross development and test roles. The two-sequence size is sufficient for a reproducible technical pilot, not for a high-powered generalization claim. Leave-one-sequence-out sensitivity will be reported if model tuning requires it.

## Generated artifact

Command:

```bash
PYTHONPATH=src python3 -m gbm_audit.benchmark \
  data/raw/PhC-C2DH-U373.zip \
  --output results/u373-reference-manifest.json
```

The manifest records the archive hash, exact image/mask paths, contiguous frame indices, shape checks, expert lineage intervals, and per-frame reference centroids/areas. Running the command twice produces byte-identical JSON for the same archive.

## Reproducibility checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: **10 tests passed**. Tests cover deterministic manifest generation, centroid extraction, unknown-parent rejection, frame continuity, shape agreement, prior source-audit checks, and prior machine-proposal mechanics.

## Gate decision

**GO** to controlled error injection. The reference identities, centroids, lineage intervals, archive hash, and sequence-level split are reproducible. The next stage may generate seeded missed detections, localization noise, fragments, ID switches, false positives and wrong links from this frozen reference. No HMM, SLDS or Koopman model should be tuned before that error benchmark is complete.

## Remaining limitations

- U373 is 2D phase contrast on a substrate, not live brain-slice imaging.
- Only two sequences are available in this archive.
- The reference labels are used as a technical benchmark, not as independent validation of the GlioTrace biology.
- Pixel and time units must remain dataset-specific until the benchmark metadata are explicitly verified.
