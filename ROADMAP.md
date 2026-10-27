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
- 🟡 Prediction vs Reality: freeze prediction ✅; import observations / compare / error metrics ⏳
- ⏳ School / Research mode switch (same engine, different panels)
- ⏳ Replicate runner for stochastic mode (extinction probability with uncertainty)

## Phase 2 — First laboratories
- ⏳ Ecosystem creator (multi-species chemostat / pond food web builder)
- 🟡 Food microbiology: yoghurt fermentation ✅ (exploratory, needs calibration); laban/cheese/probiotic survival ⏳
- ⏳ Virtual agar: reaction–diffusion colony growth, media properties, colony counting

## Phase 3 — Expanded biological systems
- ⏳ Skin / oral microbiome (community models, not clinical) · Biofilm (attachment, gradients, cross-sections) · Food webs

## Phase 4 — Bioinformatics
- ⏳ FASTA/FASTQ, diversity metrics, phylogenetic trees (Biopython, scikit-bio)

## Phase 5 — Advanced prediction
- ⏳ Uncertainty quantification, parameter calibration (held-out validation), model comparison, digital twins

## Phase 6 — Advanced UX
- ⏳ 3D rendering (pygfx or Godot), local AI assistant (optional), classroom tools, PDF reports, experiment builder

## Immediate next steps (proposed)
0. Review the organism trait table with the supervisor: growth rates, cardinal values and products per organism.
1. Owner/ChatGPT: verify chemostat parameters and taxonomy IDs; review yoghurt assumptions.
2. Prediction vs Reality screen: import measured pH/counts (CSV), compare with a frozen prediction, error metrics.
3. Parameter calibration for the yoghurt model (fit on one dataset, test on another).
4. Stochastic replicate runner; PDF lab report; Arabic names for individual parameters.
See docs/RESEARCH_IDEAS.md for research directions.
