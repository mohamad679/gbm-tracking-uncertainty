# Stage C v2 Step 2 — T98G data-only audit

Date: 2026-09-20. Decision: **PASS — LOCKED UNEVALUATED**.

## Scope

This step audited the independent T98G electrotaxis source before Stage C v2
development. It verified source identity, reuse rights, archive checksums, ZIP
integrity, parser determinism and CTC-like reference structure. It did not run
tracking, construct corruption scenarios, calculate migration summaries or
inspect any Stage C v2 performance.

The source is Zenodo record `19026908`, DOI
[`10.5281/zenodo.19026908`](https://doi.org/10.5281/zenodo.19026908), published
2026-03-15. The record API declares open access and `CC-BY-4.0`. Dataset rights
remain separate from the repository's MIT source-code license.

## Frozen source identity

| Field | Locked value |
| --- | --- |
| Archive | `T98G_electrotaxis.zip` |
| Size | 147,735,077 bytes |
| Zenodo MD5 | `5e89fc619d40e1e8f4aa8e733abc2f87` |
| SHA-256 | `1b80d50f61efca6729af4ef691adab77d06c358fbda7a73744eb4e9b252abd6c` |
| ZIP integrity | PASS; 298 files, 469,651,691 uncompressed bytes |
| Registered corruption seed | `20260920` |

## Qualified locked test

Only `T98G_human/T98G_sample` qualifies. It contains 37 raw frames, 37
human-curated segmentation masks, 37 tracking masks and one 101-row lineage
table. All images are 2D `uint16` arrays of 1022×1024 pixels; raw source frames
1–37 map deterministically to reference frames 0–36.

The structural parser confirmed:

- contiguous raw and reference frame indices;
- identical image/reference shapes in every frame;
- known, temporally non-overlapping lineage parents;
- no tracking-mask label outside its declared lineage interval;
- every lineage ID appears in at least one tracking mask; and
- deterministic archive, raw-frame, lineage and selected-member hashes.

The lineage declares 2,653 active label instances and the masks contain 2,648;
the five absent in-interval instances are preserved as explicit observation
gaps. They are neither imputed nor treated as an audit failure because the
existing reference schema supports missing observations within a lineage
interval.

`T98G_detectron2` passed the same structural checks but is excluded from the
locked test: it is an automated-segmentation variant of the same raw sequence
and identical lineage, not a second independent sequence.

## Evaluation boundary

The machine-readable artifact
[`stage-c-v2-t98g-locked-manifest.json`](stage-c-v2-t98g-locked-manifest.json)
contains structural counts and hashes only. It exports no reference
coordinates or trajectories and explicitly records:

- `tracking_metrics_computed: false`;
- `migration_summaries_computed: false`;
- `performance_evaluation_run: false`; and
- `lock_state: LOCKED_UNEVALUATED`.

U373 sequence `01` remains the sole development source. Consumed U373 sequence
`02` remains archival-only and cannot enter Stage C v2 fitting or selection.
T98G must remain unevaluated until the localization, proposal-recovery and
conformal values are frozen from sequence `01`.

## Reproduction

`.github/workflows/audit-t98g.yml` downloads the frozen archive, enforces both
published MD5 and independently recorded SHA-256, reproduces the structural
artifact byte-for-byte and runs the audit contract tests. Any archive drift,
unsafe ZIP, schema mismatch, label outside a lineage interval, variant mismatch
or accidental output drift fails closed.

This PASS qualifies T98G only as a technical independent locked test. It is not
a tracking-performance result and makes no GlioTrace biological claim.
