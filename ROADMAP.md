# MicroVerse roadmap

Status keys: ✅ implemented & tested · 🟡 partial · ⏳ planned · 🔬 validated (none yet)

## Phase 1 — Foundation
- ✅ Model contract (state vars, parameters with provenance, rhs, flux terms, stochastic reactions)
- ✅ Scheduler: deterministic (LSODA) + tau-leaping, config hash
- ✅ SQLite schema: sources, organisms, parameters, model versions, experiments, immutable predictions, observations
- ✅ Experiment files (JSON, hash-protected), CSV export
- ✅ Explanation engine (flux decomposition, stability, sensitivity)
- ✅ Desktop shell (PySide6), live plots (pyqtgraph), state-driven microscope view
- ✅ M1 demo: chemostat microcosm
- ✅ Start screen, scenario picker, bilingual organism library, lab framework (v0.2)
- ✅ Organism trait database (30 BSL-1 organisms), Community Builder, interaction analysis, Arabic UI (v0.3)
- ✅ Prediction vs Reality: freeze ✅, import CSV ✅, compare and metrics ✅, report ✅ (v0.5); calibration ⏳
- ⏳ School / Research mode switch (same engine, different panels)
- ✅ Replicate runner for stochastic mode (extinction probability with Wilson CI) (v0.5)
- ✅ Continuous microscope: persistent identities, organism-specific division and motility, 3 view modes (v0.5)

## Phase 2 — First laboratories
- ⏳ Ecosystem creator (multi-species chemostat / pond food web builder)
- 🟡 Food microbiology: yoghurt fermentation ✅ (exploratory, needs calibration); laban/cheese/probiotic survival ⏳
- 🟡 Virtual agar: colony growth ✅, morphology vs food/agar ✅, plate counts ✅ (v0.5, qualitative); two species, inhibition zones, calibration ⏳

## Phase 3 — Expanded biological systems
- ⏳ Skin / oral microbiome (community models, not clinical) · Biofilm (attachment, gradients, cross-sections) · Food webs

## Phase 4 — Bioinformatics
- ⏳ FASTA/FASTQ, diversity metrics, phylogenetic trees (Biopython, scikit-bio)

## Phase 5 — Advanced prediction
- ⏳ Uncertainty quantification, parameter calibration (held-out validation), model comparison, digital twins

## Phase 6 — Advanced UX
- ⏳ 3D rendering (pygfx or Godot), local AI assistant (optional), classroom tools, PDF reports, experiment builder

## Immediate next steps (proposed, after v0.5)
0. Review the organism trait table AND the morphology table (`library/morphology.py`) with the supervisor.
1. Confirm the chemostat parameters against the Fussmann et al. (2000) PDF and supplement.
2. First real data set: yoghurt pH and counts → Prediction vs Reality; then calibration that creates a NEW
   prediction (fit on one data set, test on another).
3. Agar: two species on one plate (competition), and a diffusing inhibitor (educational, benign).
4. Microscope: let ciliates visibly ingest bacteria across panels (inset), and draw spatial structure only when a
   spatial model drives it.
5. Remaining English strings in the Arabic UI (plot titles, scan tab, some legends).
6. Spatial grid for the cell-separation step if drawing caps are raised.
See docs/RESEARCH_IDEAS.md for research directions and docs/OVERNIGHT_PROGRESS.md for status.
