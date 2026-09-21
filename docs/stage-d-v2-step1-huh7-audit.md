# Stage D v2 Step 1: Huh7 data-only audit and lock

Date: 2026-09-21. Status: **PASS — LOCKED UNEVALUATED**.

The official CTC `Fluo-C2DL-Huh7` training archive passed the frozen identity,
archive-safety and schema checks. The local archive is exactly `38151145`
bytes with SHA-256
`1912658c1b3d8b38b314eb658b559e7b39c256917150e9b3dd8bfdc77347617d`.
The archive and reference annotations remain ignored by Git and are not
redistributed.

The pre-registered lexicographic rule locked sequence `01`. It contains 30
contiguous 1024×1024 frames, 34 lineage tracks and 883 structurally available
velocity-transition slots. Its evaluated member set is pinned by SHA-256
`336437c884752db20daf29eac3b4d59b55a3355f3c3b8a16af119deb97680e81`.

This was a data-only audit. It did not extract centroids, calculate motion,
fit models or expose predictive outcomes. Sequence `02` was structurally
audited but is excluded from this Stage D v2 evaluation by the selection rule.
The complete machine-readable lock is
[`stage-d-v2-huh7-locked-audit.json`](stage-d-v2-huh7-locked-audit.json).

The lock makes one independent evaluation permissible. It is not an
evaluation result and does not support a biological or clinical claim.
