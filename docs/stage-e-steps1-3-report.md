# Stage E-Final Steps 1-3 report

Date: 2026-09-22. Decision: **PROTOCOL AND SPLIT LOCKED**.

## Step 1 — research question and claim contract

The final project stage is now a multi-domain reference-backed validation of
tracking uncertainty. Its confirmatory question, comparators, endpoints,
decision gates, reporting rules and claim exclusions are registered in
[`stage-e-protocol.md`](stage-e-protocol.md) and
[`stage-e-protocol.json`](stage-e-protocol.json).

The project may finish with `GO`, `REVISE` or `STOP`; project completion does
not depend on manufacturing a positive result. No outcome has been inspected
or computed in Steps 1-3.

## Step 2 — verified dataset manifest

Three official CTC training archives were downloaded from the registered URLs,
hashed and subjected to a complete ZIP integrity test:

| Dataset | Size (bytes) | SHA-256 | Structure |
| --- | ---: | --- | --- |
| Fluo-N2DH-GOWT1 | 59,331,035 | `1a7bd9a7d1d10c4122c7782427b437246fb69cc3322a975485c04e206f64fc2c` | 92 frames and tracking masks per sequence |
| DIC-C2DH-HeLa | 41,504,758 | `832fed2d05bb7488cf9c51a2994b75f8f3f53b3c3098856211f2d39023c34e1a` | 84 frames and tracking masks per sequence |
| Fluo-N2DH-SIM+ | 99,034,393 | `3e809148c87ace80c72f563b56c35e0d9448dcdeb461a09c83f61e93f5e40ec8` | 65 frames in sequence `01`; 150 in sequence `02`, both with exact masks |

The complete manifest SHA-256 is
`bcd7404dc083f1254655dc184a5857a4b5f43316cae7bf2f58d31f93eee95955`.
Raw archives and annotations remain external and are not committed.

## Step 3 — immutable split

- GOWT1 `01`: development/calibration
- GOWT1 `02`: locked real test
- HeLa `01`: development/calibration
- HeLa `02`: locked real test
- SIM+ `01`: synthetic diagnostic development
- SIM+ `02`: locked synthetic diagnostic test

The split artifact SHA-256 is
`79876f90bd5b59fb5d77cad362a115cac1bb1bf8566790373d309d3eccab3421`.
Its initial access state records that no locked coordinates, motion summaries,
tracking metrics or uncertainty outcomes have been computed.

U373, T98G and Huh7 remain excluded from new Stage E confirmation because they
were consumed in Stages A-D. GlioTrace remains qualitative only because it lacks
the required independent reference labels.

## Result

Steps 1-3 are complete. Stage E is authorized to proceed to implementation of
the registered generic evaluator and baselines while every sequence-`02`
outcome remains locked.
