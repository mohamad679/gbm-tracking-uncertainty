# External biological-context validation source audit

Date: 2026-09-23

Status: **source selection completed before quantitative outcome inspection**.

This audit identifies public datasets that can strengthen the biological context of the completed technical tracking-uncertainty project. It does not alter the locked Stage E result (`REVISE`) and does not itself constitute biological validation.

## Primary quantitative candidate: Dryad glioma brain-slice tracking data

Dataset: **Comparative dynamics of microglial and glioma cell motility at the infiltrative margin of brain tumours**

- DOI: `10.5061/dryad.s4d28`
- Repository: Dryad
- Related article: Juliano et al., *Journal of the Royal Society Interface* (2018), DOI `10.1098/rsif.2017.0582`
- Model: PDGFB-driven rat glioma
- Preparation: acute living brain slices at the infiltrative tumour margin
- Imaging: two-colour time-lapse fluorescence microscopy
- Reference generation: cells were manually tracked frame by frame
- Biological replication: three separate experiments are reported
- Published tumour-cell tracking counts: 100 tumour cells in experiment 1, 190 in experiment 2, and 50 in experiment 3
- The Dryad record states that the code/data archive contains tracking and PIV data from all three experiments.

Dryad files reported by the public record include:

- `5-16-11.zip` — experiment 1 movie data
- `6-6-11.zip` — experiment 2 movie data
- `3-4-14C2.zip` — experiment 3 movie data
- `To Generate Figures.zip` — code and tracking/PIV data for the three experiments
- `README_for_To Generate Figures.docx`

### Why this is the preferred source

This source is substantially closer to the scientific target than the Cell Tracking Challenge datasets used for Stages A–E. It contains real glioma cells migrating in living brain tissue and independent experiments, together with manually generated single-cell tracks. That combination makes it suitable for a quantitative external biological-context validation provided the deposited tracking files can be converted to an explicit frame/track/x/y representation without reconstructing labels from published outcomes.

### Claim boundary

A successful evaluation on this source could support a bounded statement about technical transfer to a **rat glioma brain-slice context**. It would not establish:

- human glioblastoma-wide generalization;
- patient-level generalization;
- animal-level population inference beyond the three deposited experiments;
- a validated GBM cell state or phenotype;
- treatment effects;
- clinical utility.

## Secondary exploratory source: GlioTrace example data

Dataset: **GlioTrace example dataset**

- DOI: `10.5281/zenodo.21981544`
- Published: 2026
- Context: live PDCX brain slices with migrating glioblastoma cells
- Imaging: high-content confocal time-lapse data
- Public example material: ROIs from two separate mice, stored as GFP and Lectin-594 image stacks
- Related publication: *Reconstructing the single-cell spatiotemporal dynamics of glioblastoma invasion*, Nature Communications (2026)

This source is biologically closer to human GBM/PDCX than the Dryad rat model, but the public example record does not advertise an independent manual ground-truth tracking annotation suitable for a confirmatory accuracy audit. It therefore remains **exploratory only** unless an independent reference-label set is identified.

## Selection decision

1. Use Dryad `10.5061/dryad.s4d28` as the primary quantitative biological-context validation candidate.
2. Treat each of the three experiments as the biological replicate unit; individual tracks/cells must not be presented as independent biological replicates.
3. Keep GlioTrace exploratory until independent reference tracking labels are available.
4. Inspect only file structure and schema before freezing the ingestion map. Do not inspect method-performance outcomes while adapting the parser.
5. Freeze all conversion rules, unit handling, exclusions, and evaluation endpoints before computing the first confirmatory result.

## Source links

- Dryad dataset: https://doi.org/10.5061/dryad.s4d28
- Related glioma-motility article: https://doi.org/10.1098/rsif.2017.0582
- GlioTrace example dataset: https://doi.org/10.5281/zenodo.21981544
