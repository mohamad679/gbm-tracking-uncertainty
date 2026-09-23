# Stage C, Step 2 — exact matching trajectory sampler

Date: 2026-09-19. Status: **COMPLETED — development structural audit only**.

## Delivered implementation

`sample_exact_context_matchings` enumerates each Stage B connected component's
complete weighted matching-state distribution, then samples one matching state
per component for each trajectory-ensemble realization. It never samples
candidate links independently. Chosen component states are combined across
transitions and converted into a partition of observations into trajectories.

The implementation records the fixed seed, component partition functions,
enumerated matching counts, sampled link frequencies, matching links and
trajectory membership. It fails closed above the 18-target exact-component
limit and checks, for every sample:

- source and target one-to-one capacity;
- complete observation-to-trajectory partition; and
- membership of every chosen link in the input candidate graph.

Unit tests establish determinism, graph compatibility, trajectory partitioning,
resource-bound enforcement and agreement between sampled link frequency and an
analytic exact marginal.

## Development structural audit

The clean `sequence 01` input was sampled with the frozen 256-member ensemble:

| Check | Result |
| --- | ---: |
| Connected components | 796 |
| Largest component | 1 target |
| Largest exact state set | 2 matching states |
| First-sample links | 587 |
| First-sample trajectories | 178 |
| One-to-one, partition and graph invariants | PASS |

No sequence-`02` input was evaluated. This is a structural check only; no
migration metric, HMM fitting or decision gate has been run.

## Next boundary

The next step implements development-only fitting of the fixed two-state speed
HMM and posterior aggregation of migration/state summaries. Sequence `02`
remains locked.
