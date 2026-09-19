# Stage A Step 2: adaptive candidate generator v1

Date: 2026-09-19. Status: **COMPLETED; AWAITING STEP 3 INTEGRATION**

## Scope

This step implements a standalone, deterministic and truth-blind candidate
graph generator. It deliberately does not connect the graph to hypothesis
sampling, calibration or downstream dynamics. Those integrations occur in
Step 3, before development-sequence tuning or locked test evaluation.

## Algorithm

For each source observation, v1 builds a short past-only history using a
deterministic greedy association under the conservative 8-pixel base gate.
The history supplies a constant-velocity prediction and a motion-uncertainty
estimate derived from changes between recent velocity vectors.

The adaptive radius is:

\[
r_{i,t}=\operatorname{clip}
\left(
r_{min}+\alpha\sigma_{motion,i,t}+\beta d_{local,i,t},
r_{min},r_{max}
\right)
\]

where the default, not-yet-tuned configuration is:

- `r_min = 8 px`
- `r_max = 16 px`
- `alpha = 1`
- `beta = 4 px`
- local density radius `16 px`, saturated at six neighbours
- cold-start motion uncertainty `4 px`
- maximum seed-history length four observations

An edge is retained when it lies either inside the original 8-pixel circle
around the source or inside the adaptive circle around the predicted position.
Keeping the base circle prevents a constant-velocity prediction from deleting
short true links during abrupt turns.

## Truth-blindness and determinism

Candidate generation reads only:

- `observation_id`
- `frame`
- `x_px`
- `y_px`

Reference identities, link labels and evaluation truth are not read. Tests
verify that adding truth fields cannot change the output and that shuffling
input observations produces the same graph.

## Output contract

The generator returns:

- the complete configuration;
- one diagnostic gate row per eligible source observation;
- one row per candidate edge;
- candidate edge and target-observation counts;
- candidate burden in edges per target observation.

Each edge records direct distance, prediction residual, adaptive radius and
whether inclusion came from the base gate, adaptive gate or both.

## Step decision

Step 2 passes its engineering gate when validation, truth-blindness,
determinism, base-gate retention, adaptive recovery and radius-clipping tests
all pass. This is not the Stage A scientific gate. No recall, burden or
downstream-performance claim is made until Steps 3–5.

All six generator tests pass as part of the 60-test package suite. Package
coverage is 70%, and this module has 89% statement coverage.
