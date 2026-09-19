# Stage A Step 4: development-only tuning

Date: 2026-09-19. Status: **REVISE; NO PARAMETERS LOCKED**

## Scope and leakage boundary

The tuner uses only U373 sequence `01`, whose manifest role is
`development`. It extracts only `clean_0` and `localization_noise_5p0` before
screening or posterior evaluation. It fails closed if the declared split
changes, and its result records `locked_test_sequence_evaluated: false`.
Sequence `02` was not evaluated in this step.

Posterior sampling now uses each corruption scenario's declared seed. This
keeps a retained scenario bit-for-bit stable when the 17-scenario artifact is
filtered to the two tuning scenarios; a regression test compares full and
filtered posterior links.

The predeclared 27-member grid fixes the minimum/maximum radii at 8/16 px,
the density radius at 16 px, density saturation at six neighbours and history
length at four. It crosses motion-uncertainty weights `{0, 1, 2}`, density
weights `{0, 2, 4}` px and cold-start uncertainties `{0, 2, 4}` px.

The two-phase selection rule first requires the frozen clean recall and burden
gates. Only surviving configurations may run posterior sampling and soft
dynamics. Among configurations passing every development gate, the rule would
minimize sigma-5 soft-speed error, clean soft-speed error and candidate burden,
then use the configuration ID as a deterministic tie-break.

Reproduce the development-only search with:

```bash
gbm-adaptive-tuning \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  --output results/stage-a-development-tuning.json
```

Exit status `1` is the expected scientific `REVISE` result; malformed or
inconsistent artifacts return status `2`.

## Development baselines

| Run | Clean recall | Edges / target | Clean soft-speed error | Sigma-5 soft-speed error |
|---|---:|---:|---:|---:|
| fixed 8 px | 0.7913 | 0.7892 | 2.3164 | 0.2204 |
| fixed 12 px | 0.9168 | 0.9144 | 1.3143 | 2.1368 |
| fixed 16 px | 0.9590 | 0.9565 | 0.7834 | 3.8278 |

All speed errors are absolute pixels per frame. These baseline values were
computed from sequence `01` only.

## Grid result

No configuration passed the clean screening gates, so none proceeded to the
posterior/soft-dynamics phase.

| Adaptive result | Configuration | Clean recall | Edges / target | Reduction vs fixed 16 |
|---|---|---:|---:|---:|
| Highest recall | `m2-d0-c4` (tied across density weights) | 0.9472 | 0.9447 | 0.0124 |
| Largest burden reduction | `m0-d0-c0` (tied variants) | 0.8243 | 0.8221 | 0.1405 |

The highest-recall result misses the 0.95 recall threshold and is far below
the required 0.20 burden reduction. The lowest-burden result also misses both
thresholds.

## Feasibility bound

The failure is structural under the frozen metric, not merely a poor grid.
Sequence `01` contains 757 clean consecutive reference links. A recall of at
least 0.95 therefore requires at least `ceil(0.95 * 757) = 720` candidate
edges. The fixed-16 comparator contains only 726 candidate edges in total.
Even a perfect truth-selective generator could reduce burden by no more than

`1 - 720 / 726 = 0.008264` (0.83%).

The pre-registered 20% reduction target is therefore mathematically
incompatible with the 95% recall target on development sequence `01` when
burden is defined as total candidate edges per target observation.

## Decision

Step 4 returns **REVISE**. No adaptive configuration is frozen, and the locked
test evaluation must not proceed under protocol v1. The machine-readable
artifact is
[`stage-a-step4-development-tuning.json`](stage-a-step4-development-tuning.json).

A replacement protocol must be declared before inspecting sequence `02`. It
should retain the 95% recall requirement but replace total edge count with a
burden measure that represents ambiguity or false/excess candidate work; the
new rule and thresholds must be frozen before rerunning development tuning.
