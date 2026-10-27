# MicroVerse — Architecture & Feasibility Assessment

Status: **draft v0.1 (2026-10-27)**, written by Claude Code for review by the project owner and ChatGPT.
Legend used throughout: **[Implemented]**, **[Partial]**, **[Planned]**, **[Tested]** (automated tests pass), **[Validated]** (compared against independent experimental data — nothing is validated yet).

---

## 1. Technical feasibility assessment

**Environment inspected (2026-10-27):** Windows 11 Pro, Python 3.12.10, Node 24, Git 2.55, NVIDIA RTX 4060 Ti (8 GB, driver 610.88), 16 GB RAM. Not installed: Godot, Blender, Rust, .NET, Qt. A project-local `.venv` was approved for PySide6, pyqtgraph, SciPy, pytest.

| Goal | Feasible on this hardware? | Notes |
|---|---|---|
| ODE/PDE population models (Monod, Lotka–Volterra, chemostat, food webs) | Yes, trivially | SciPy `solve_ivp` (LSODA/Radau) handles stiff systems in ms. |
| Stochastic simulation (Gillespie / tau-leaping) | Yes | NumPy vectorised; thousands of replicate runs per minute for small networks. |
| Reaction–diffusion on 2D grids (agar, biofilm) | Yes | 512×512 grids at interactive rates with NumPy; GPU (CuPy/PyTorch) optional later. |
| Agent-based models | Yes up to ~10⁵ agents (vectorised) | Beyond that use *super-individuals* (each agent = N cells) or continuum fields. |
| Flux balance analysis | Yes | COBRApy (GPL-2 / LGPL) + GLPK; licensing to review before bundling. |
| Bioinformatics (FASTA/FASTQ, diversity, trees) | Yes | Biopython (BSD-like), scikit-bio (BSD). |
| Realistic 2D microscopy rendering | Yes | Qt `QPainter`/OpenGL procedural sprites driven by state. |
| Realistic 3D (biofilm volumes, camera fly-through) | Yes, later phase | Candidates: VisPy/pygfx (BSD) in-process, or Godot (MIT) as a separate renderer reading state over a socket. |
| Local AI assistant | Partially | 8 GB VRAM fits a 7–8B quantised model (e.g. via Ollama/llama.cpp). Must never replace the engine. |
| Fully offline core | Yes | All core libraries are local. |
| Zero recurring cost | Yes | Every chosen dependency is free / open source. |

**Main risks**
1. *Scientific scope* is far larger than any one release. Mitigation: one model at a time, each documented and tested before the next.
2. *Data licensing* (KEGG, some BacDive / ComBase terms) may forbid redistribution. Mitigation: store identifiers + user-downloaded copies; record licence per record.
3. *Visual realism vs. honesty.* Mitigation: the renderer is read-only over the simulation state, and every overlay carries a "modelled / conceptual" tag.
4. *Parameter quality.* Many published parameters are strain-, medium- and temperature-specific. Mitigation: every parameter carries provenance and an evidence level (§4).

## 2. Proposed software architecture

Language: **Python 3.12** for engine, analysis and UI (one language, the scientific ecosystem lives there). UI: **PySide6 (Qt 6, LGPL)** + **pyqtgraph (MIT)** for fast live plots. A separate 3D renderer may be added later without changing the engine.

```
┌──────────────────────────────── UI (PySide6) ────────────────────────────────┐
│  Mode shell (School / University / Research)  ·  parameter panels  ·  plots  │
│  Microscope view  ·  Explanation panel  ·  Experiment browser                │
└──────────────▲───────────────────────▲───────────────────────▲──────────────┘
               │ state snapshots (read-only)                    │
┌──────────────┴──────┐  ┌─────────────┴────────────┐  ┌────────┴────────────┐
│ Visualization engine│  │ Explanation engine       │  │ Reporting (CSV/PDF) │
│ renders FROM state  │  │ flux decomposition,      │  │ simulated vs observed│
│ never invents state │  │ stability, sensitivity   │  │ clearly separated    │
└──────────────▲──────┘  └─────────────▲────────────┘  └────────▲────────────┘
               │                       │                        │
┌──────────────┴───────────────────────┴────────────────────────┴────────────┐
│ Simulation scheduler: runs a Model with a seed, solver and time grid;        │
│ records Trajectory (+ config hash) — deterministic or stochastic             │
└──────────────▲─────────────────────────────────────────────▲───────────────┘
               │                                             │
┌──────────────┴──────────────┐              ┌───────────────┴──────────────┐
│ Biological model library    │              │ Prediction & uncertainty     │
│ each Model = state vars,    │              │ replicate runs, parameter    │
│ Parameters (units+source),  │              │ sampling, sensitivity        │
│ rhs / propensities, docs    │              │                              │
└──────────────▲──────────────┘              └───────────────▲──────────────┘
               │                                             │
┌──────────────┴─────────────────────────────────────────────┴───────────────┐
│ Data layer: SQLite (organisms, parameters, sources, experiments, predictions,│
│ observations, model versions) + JSON experiment files                        │
└─────────────────────────────────────────────────────────────────────────────┘
          + Validation framework (Prediction vs Reality)   + optional AI assistant
```

Key contracts:
- **`Model`** — declares state variables (name, unit, description), `Parameter` objects, a deterministic right-hand side, and optionally a reaction list for stochastic simulation. A model is pure computation: no UI, no I/O.
- **`Parameter`** — value, unit, bounds, description, `Source` (citation/DOI) and `evidence` level.
- **`Trajectory`** — time array, state matrix, the full config (model id + version, parameters, seed, solver) and a SHA-256 hash of that config, so every result can be reproduced.
- **Renderer contract** — receives a `Trajectory` + time index; may add *visual* randomness (cell positions, orientation) only from its own seeded RNG, and never changes counts or outcomes.

## 3. Scientific modelling strategy

Choose the model by the question, and keep levels separate:

| Question | Model family | Planned module |
|---|---|---|
| Well-mixed population growth / competition | Logistic, Monod, chemostat ODEs | A, D |
| Predator–prey, food webs | Lotka–Volterra / Rosenzweig–MacArthur / multi-trophic chemostat | A, F |
| Demographic noise, extinction risk | Gillespie SSA, tau-leaping | I |
| Spatial colonies, agar, biofilm | Reaction–diffusion + individual-based growth | C, E |
| Fermentation (acidification, pH) | Monod + product inhibition + acid–base chemistry | D |
| Metabolism | Flux balance analysis on curated GEMs | Metabolic Explorer |
| Evolution | Wright–Fisher / Moran on abstract genotypes | G |
| Data-driven prediction | Regression / Bayesian calibration, held-out validation | J, Validator |

Rules: every model has a doc page (biological meaning, equations, units, assumptions, validity domain, numerics, tests, validation data); **verification** (code solves the equations correctly) is reported separately from **validation** (equations describe reality).

## 4. Scientific database & provenance strategy

SQLite file `data/microverse.sqlite` (schema in `microverse/data/schema.sql`):
- `sources` — citation, DOI/URL, licence, access date.
- `organisms` — name, NCBI Taxonomy ID, group, morphology descriptors, biosafety note.
- `parameters` — organism/model, symbol, value, unit, conditions (T, medium), source_id, evidence level, notes.
- `experiments` — saved configs (JSON) + config hash + model version.
- `predictions` — frozen at creation (hash + timestamp, never updated; corrections create new rows).
- `observations` — imported lab data linked to a prediction.
- `model_versions` — calibrated parameter sets with parent version and validation scores.

Evidence levels: `measured` (direct measurement, cited) · `literature_estimate` · `fitted` (calibrated to data; says which) · `assumed` (exploratory, clearly flagged) · `derived`.
Licensing: external resources (NCBI, UniProt, MGnify are open; KEGG, parts of BacDive/ComBase have restrictions) are referenced by identifier; bulk data are only bundled when the licence allows it.

## 5. Realistic visualization strategy

Three views over the *same* state:
1. **Realistic view** — procedural rendering of each organism from morphology descriptors (size in µm, shape, colour, motility type) and reference images. Rendered cell counts = state density × sample volume (Poisson-sampled), so what you see follows the numbers.
2. **Microscope view** — the same scene with optical constraints (brightfield, phase contrast, fluorescence; resolution limit, depth of field).
3. **Explanation view** — overlays of invisible quantities (nutrient concentration, fluxes, gradients), always labelled "modelled".

Tech path: Qt `QPainter` 2D now (M1) → OpenGL/pygfx for large scenes and microscopy effects → optional 3D (pygfx or Godot) for biofilms and food webs. Hypothetical morphology is labelled "predicted".

## 6. Performance strategy (RTX 4060 Ti, 16 GB RAM)

- Well-mixed models: ODE solvers, microseconds per step; precompute the full trajectory, then play it back (time machine for free).
- Stochastic: tau-leaping, vectorised replicates; run in a worker thread or process so the UI never freezes.
- Spatial: NumPy grids; optional GPU backend (CuPy / PyTorch) behind one array-API interface; never required.
- Rendering: draw at most a few thousand sprites (render a statistically representative sample window, not every cell); level of detail by zoom.
- Memory: trajectories stored as float32 with configurable save interval.

## 7. Modular roadmap

See `ROADMAP.md` (kept up to date). Summary: Phase 1 foundation + M1 demo → Phase 2 ecosystem / fermentation / agar labs → Phase 3 microbiome, biofilm, food webs → Phase 4 bioinformatics → Phase 5 uncertainty, calibration, Prediction vs Reality → Phase 6 3D, AI assistant, classroom, reporting.

## 8. Dependencies & licences

| Package | Purpose | Licence | Status |
|---|---|---|---|
| Python 3.12 | runtime | PSF | installed |
| NumPy | arrays | BSD-3 | installed in .venv |
| SciPy | ODE solvers, root finding | BSD-3 | installed in .venv |
| PySide6 (Qt 6) | desktop UI | LGPL-3 (dynamic linking OK) | installed in .venv |
| pyqtgraph | live plots | MIT | installed in .venv |
| pytest | tests | MIT | installed in .venv |
| SQLite (stdlib `sqlite3`) | database | public domain | built-in |
| Candidates later | Biopython (BSD-3-like), scikit-bio (BSD-3), pandas (BSD-3), scikit-learn (BSD-3), PyTorch (BSD-3), COBRApy (GPL-2/LGPL, check), pygfx (BSD-2), Godot (MIT), ReportLab (BSD) for PDF | — | not installed |

## 9. Repository structure

```
MicroVerse/
├── README.md  ROADMAP.md  CHANGELOG.md
├── docs/
│   ├── ARCHITECTURE.md        (this file)
│   ├── MILESTONE_1.md         (spec of first working milestone)
│   ├── VERIFICATION_VS_VALIDATION.md
│   └── models/                (one page per model)
├── microverse/
│   ├── core/       model.py, parameters.py, scheduler.py, trajectory.py
│   ├── models/     chemostat_rotifer.py, yogurt.py
│   ├── labs/       base.py (Lab, Scenario), chemostat.py, yogurt.py — one package per lab
│   ├── library/    organisms.py (bilingual organism cards)
│   ├── analysis/   stability.py, explain.py, sensitivity.py
│   ├── data/       schema.sql, db.py, seed.py
│   ├── io/         experiment.py (save/load reproducible configs)
│   ├── viz/        scene.py, yogurt_scene.py (Qt-free scenes that read state)
│   └── ui/         app.py, main_window.py, start_screen.py, workspace.py, organism_card.py, *_widget.py, style.py
├── scripts/        ui_smoke.py (screenshot smoke test)
├── MicroVerse.bat  (launcher)
├── tests/
├── data/           (local SQLite db, git-ignored)
└── experiments/    (saved experiment JSON files)
```

## 10. First milestone

Specified in `docs/MILESTONE_1.md`.
