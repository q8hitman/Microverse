# Changelog

## 0.5.0 — 2026-10-27 — Continuous microscope, Prediction vs Reality, Virtual Agar
- **Fixed: organisms popped in and out.** Root cause: every scene used an immigration–death process. Drawn
  cells vanished with probability dt/0.6 s and new ones were dropped at random positions every frame, even
  while paused (374 random spawns in 10 s with 23 cells on screen, measured on v0.4). The dilution factor also
  changed in 2× steps, and positions wrapped across edges. Replaced by a persistent visual engine
  (`viz/population.py`, `viz/specimen.py`): agents with ids; counts change only through division (12
  organism-specific styles), lysis, grazing by a visible predator, or swimming out of or into view; one sample
  factor per run; interpolated state; reflecting edges.
- **Morphology for all 30 organisms** (`library/morphology.py`): shape, size, arrangement, motility (11 styles
  with literature speeds), division style, structures, provenance. Procedurally drawn in three modes
  (Realistic, Microscope = phase contrast or Gram stain, Explanation overlays). Zoom, pan, click-to-inspect,
  Replay, swimming-speed control, playback using measured frame time.
- **Prediction vs Reality** (start screen): import measurements (CSV), map columns and units (log10 CFU,
  timestamps), validate, re-simulate the frozen prediction (hashes and model version checked, never modified).
  Metrics: RMSE, MAE, bias, NRMSE, R², best time shift. Plain-language explanation; HTML/JSON report;
  observations and an append-only comparisons table in the database.
- **Why? panel: "What changed, and why"**: for each variable that changed, the flux terms responsible, integrated
  exactly, with the share of the change they explain, the parameter evidence, sensitivity and a measurement that
  would test it.
- **Replicates tab** (chemostat): N stochastic runs with consecutive seeds; extinction probability with a Wilson
  95 % CI; 5–95 % envelopes.
- **Virtual Agar** (start screen): 2-D colony model (Kawasaki 1997 / Mimura 2000 type) on a 90 mm dish;
  compact versus branched morphology from food and agar firmness; spread-plate counts with Poisson founders and
  merging colonies; time-lapse; counted-colony markers. Qualitative.
- **Who's Who interaction network**: trait-based arrows (eats, feeds, oxygen, acid, compete) plus measured
  results.
- **Scientific fixes:** yoghurt model 1.1.0 (peptide pool could go negative; see SCIENTIFIC_REVIEW A1);
  biosafety described per strain and jurisdiction with representative strains; drawn-cell mass from shape volume.
  The chemostat parameters were checked against the values reported for Fussmann et al. (2000).
- **Arabic:** names for every model parameter; new screens are bilingual.
- **Tests:** 188 (was 76), including off-screen construction of every screen.
- Docs: DEVELOPMENT_AUDIT, VISUALIZATION_ARCHITECTURE, SCIENTIFIC_REVIEW, OVERNIGHT_PROGRESS, models/agar.

## 0.4.0 — 2026-10-27 — What each organism does; two-panel microscope; calmer interface
- **Function reference** (`microverse/library/functions.py`): 20 functions (primary producer, oxygen producer,
  lactic/alcohol fermenter, acidifier, decomposer, cross-feeder, aerobic scavenger, bacterial/algal grazer,
  top predator, grazing-resistant, nitrogen fixer, nitrifier, methanogen, mixotroph, oxygen-sensitive, food starter,
  model organism, extremophile), each explained in English and Arabic with how the simulation represents it and
  something to try. 17 are DERIVED FROM THE SIMULATION TRAITS, so the label and the behaviour cannot disagree;
  3 are assigned by hand and marked as such.
- **SQLite organism database**: tables `organism_db`, `functions`, `organism_functions` in data/microverse.sqlite,
  refreshed at every start; `scripts/build_database.py`; CSV export for Excel (Arabic preserved).
- **Library**: browse By Organism or By Function, search across names/groups/functions/roles, function chips on every
  card, a "What it does" table per organism; export a printable **organism guide (PDF)** in English or Arabic.
- **Who's Who** tab in every lab: what each organism in that lab does, and what their traits suggest will happen
  between them (who eats whom, who feeds whom, who supplies oxygen, whose acid hurts whom, who competes).
- **Two-panel microscope** in the Community Builder: 100× for cells ≤ 15 µm, 10× for larger organisms, true relative
  size inside each panel, its own scale bar, and a readable legend on a solid plate below the images.
- **Interface** (Vercel interface guidelines + graphic-design skill): parameter groups for organism traits start
  folded; visible keyboard focus; cards reachable with Tab/Enter; confirmation before the irreversible "freeze";
  friendly error messages with details on demand; Arabic mirrors the whole layout (right-to-left).
- Tests: 76 total (22 new for functions, database, CSV and guide).

## 0.3.0 — 2026-10-27 — Organism database, Community Builder, Arabic
- **Organism database** (`microverse/library/organisms.py`): 30 biosafety-level-1 organisms — lactic acid bacteria,
  acetic acid bacteria, Bacillus, E. coli K-12, Pseudomonas, Azotobacter, Nitrosomonas, cyanobacteria, archaea
  (methanogen, halophile), yeasts, moulds, algae, a diatom, ciliates, an amoeba, a flagellate and rotifers.
  Each record carries BOTH the descriptive card (bilingual) and the physiological traits the simulation uses.
- **Community Builder lab**: pick 2–5 organisms (or one of 9 presets); the equations are assembled from their traits.
  Competition, predation, cross-feeding, acid inhibition, oxygen coupling and nutrient recycling all emerge.
- **Interaction analysis**: re-runs each organism alone and each pair together, classifies the interaction from the
  measured effects, and explains the mechanism from the traits.
- **Arabic**: language switch in the start screen. Predictions, explanations, organism cards, scenarios, outcomes and
  most of the interface are bilingual; the explanation panel renders right-to-left. (Individual parameter names are
  still English.)
- **Clearer interface**: Help → "How to use MicroVerse", tooltips on every button, grouped parameters, a microscope
  view that states its own concentration factors, and a "Why?" panel that says everything is computed, not stored.
- Model fixes found by testing: organisms outside their limits now die instead of freezing; photoautotrophs are not
  oxygen-gated; sealed vessels start purged; oxygen cannot supersaturate; nitrogen limitation is smooth.
- Tests: 54 total (21 new for the database, community model and interactions).

## 0.2.0 — 2026-10-27 — Start screen, organism library, yoghurt lab
- Start screen: choose a lab → see its organisms → choose a scenario (research question) → start. Planned modules listed as "coming next".
- Organism library: bilingual (English/Arabic) cards with classification, NCBI Taxonomy ID, size, shape, metabolism, reproduction, role, model variables, biosafety, references; drawn portraits.
- Lab framework (`microverse/labs/`): each lab bundles model, organisms, scenarios, parameter groups, plots, explanation, scan, scene.
- New model `yogurt` v1.0.0 (exploratory): CTMI/CPM cardinal growth, protocooperation (peptides/formate), Luedeking–Piret acid, lactose→lactate+galactose stoichiometry, charge-balance pH of milk. Explanation engine, temperature scan, Gram-stain smear + jar/pH-meter view.
- Chemostat lab: 7 scenarios (cycles, damped, stable, rotifer extinction, washout, paradox of enrichment, stochastic small vessel).
- UI: new workspace (header with question and prediction, grouped parameters with evidence dots, multiple linked plots, organisms and model tabs), dark stylesheet, chart colours checked with the dataviz palette validator.
- Sensitivity now accepts any output metric; 11 new tests (33 total).

## 0.1.0 — 2026-10-27 — Milestone 1
- Architecture & feasibility assessment (`docs/ARCHITECTURE.md`), M1 spec, model doc, verification-vs-validation doc, roadmap.
- Core: `Parameter`/`Source`/`Evidence` provenance, `Model` contract, `RunConfig` + SHA-256 hash, `Trajectory`, scheduler (LSODA, tau-leaping with exact extinction).
- Model `chemostat_rotifer` v1.0.0 (Fussmann et al. 2000) with analytic equilibria, analytic Jacobian, 9-channel stochastic formulation.
- Analysis: regime classification (linear stability), explanation engine, elasticities, δ regime scan, oscillation period.
- Data: SQLite schema with append-only predictions (triggers), seeding of parameters/sources/organisms; experiment JSON files.
- Visualization: state-driven microscope scene (Poisson-tracked counts, eggs from R/B, culture tint from C) and Qt painter.
- UI: parameter panel with evidence badges, live plot + playback, regime-scan tab, explanation panel, sensitivity, freeze prediction, open/save/export.
- Tests: 22 pytest verification tests; `scripts/ui_smoke.py` screenshot smoke test.
