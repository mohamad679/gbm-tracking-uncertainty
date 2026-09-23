# Engineering hardening report

Date: 2026-09-19. Status: **COMPLETE for the first correctness/test hardening milestone.**

## Scope

This milestone hardened failure-prone edge cases without changing the scientific intent of the benchmark.

Implemented changes:

- fixed the appearance descriptor contract so empty/out-of-bounds patches return the same 28-value shape as normal patches;
- reject non-2D images, negative descriptor radius, and non-finite descriptor coordinates;
- reject invalid uncertainty sampling inputs, including non-positive hypothesis counts, non-positive/non-finite distance gates, and non-positive/non-finite temperatures;
- detect mismatched appearance descriptor dimensions before computing appearance distance;
- removed the unused nearest-neighbor computation from uncertainty evaluation;
- hardened the two-state HMM so rows without transition evidence retain a valid fallback transition distribution instead of becoming all-zero rows;
- reject non-finite HMM speed observations and non-positive iteration counts;
- validate positive finite dynamics distance gates and probability thresholds;
- strengthened one-to-one association regression tests;
- expanded CI to Python 3.11, 3.12 and 3.13;
- added an enforced coverage baseline.

## Automated validation

GitHub Actions test run `35440157553` on source commit `8f2c0b38d67231a04e53e9cbdd3466ad9b75966e` completed successfully on Python 3.11, 3.12 and 3.13.

Measured test result on Python 3.13:

- tests executed: **39**
- tests passed: **39**
- package statement coverage: **68%**
- enforced minimum coverage gate: **65%**

Selected core-module coverage from the same run:

| Module | Coverage |
|---|---:|
| `appearance.py` | 86% |
| `baseline.py` | 80% |
| `benchmark.py` | 73% |
| `corruptions.py` | 88% |
| `dynamics.py` | 88% |
| `uncertainty.py` | 82% |
| `validation.py` | 79% |

The package-wide percentage is lower because several exploratory/peripheral modules (`ctc.py`, `overlay.py`, `roi.py`, parts of `proposals.py`) still have limited or no direct unit coverage. The 65% gate is therefore an explicit baseline, not a claim that coverage is already complete.

## Full benchmark regeneration

Because correctness hardening touched numerical code paths, the complete official U373 benchmark was rerun rather than assuming unchanged outputs.

GitHub Actions reproduction run `35440157588` completed successfully:

- tests: success;
- official U373 archive download: success;
- all benchmark/proposal numerical stages: success;
- final audit: success;
- artifact upload: success.

Reproduction provenance:

- source commit: `8f2c0b38d67231a04e53e9cbdd3466ad9b75966e`
- artifact: `u373-reproduced-results`
- artifact SHA-256: `aec4244e9ceca4f83b1a26fdaffca6cd3e5de829c39c0979aff2a771b82154f3`
- official U373 archive SHA-256: `b18185c18fce54e8eeb93e4bbb9b201d757add9409bbf2283b8114185a11bc9e`

## Numerical stability result

The hardened run reproduced the same hashes for the principal scientific outputs produced before this milestone:

- reference manifest: `61d91978cba21b9f1aba8fde048cea72ad9ba740c875e490650862114b19b395`
- corruption benchmark: `dc39b52d7f7ced4ba8368af3b8366f66cba7b34bd039c408fde8a1e71ba53e1a`
- distance uncertainty evaluation: `d11e487656ee219f1075c5c027efe42b4cf387f2afbc0340c8a9d9da746fdcac`
- dynamics evaluation: `cbb360a680960d40778629a0ff2bb44d3cd739a19f205bdb69881a23c791d5c5`
- soft dynamics evaluation: `aac212694272aed5b27c8ad485ea9d1a4cd873d0d8c5c452522af31578ed8915`
- gate sensitivity: `cb7809492cf8af19a88161f8e0af19f1a96ee098a74e2370cee65689feff7efc`
- motion + appearance uncertainty: `cc1bc9619eb2342693129aa45a928069b9d6495d5eb834d8d8967ed12b971ac3`

Therefore the hardening fixes improve validation and edge-case behavior without changing the currently reported U373 benchmark conclusions.

## Current scientific gate

The regenerated final audit remains:

- `technical_benchmark_complete = true`
- `operator_learning_ready = false`
- `biological_validation_claim_supported = false`

No SLDS/Koopman or biological interpretation should be promoted solely because this engineering milestone is complete.

## Remaining test debt

The next coverage improvements should target the currently low-coverage peripheral modules and more CLI/archive failure paths. Increasing the enforced threshold should happen only after those tests are added; the current 65% threshold intentionally prevents regression below the measured 68% baseline while leaving a small CI tolerance.
