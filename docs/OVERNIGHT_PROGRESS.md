# Overnight progress report — MicroVerse v0.5

Branch: **`dev/v0.5`** (main is unchanged). All work was done autonomously and committed in small steps.

## 1. Starting commit
`a90778b` — "Add v0.4 status report (Arabic, HTML and PDF)". Baseline: **76 tests passed**.

## 2. Actual root cause of the spawning problem
Every microscope scene converted the model state into drawn cells with an **immigration–death process**.
Each frame, every drawn cell vanished with probability dt/0.6 s, and new cells were created at **uniformly
random positions** at rate target/0.6 s. So:

* every drawn cell lived ≈0.6 s of real time;
* it happened **even while paused**, because the scene was updated on every animation frame;
* the per-species dilution factor was re-chosen each frame in 2× steps, so target counts jumped;
* positions wrapped around the edges (teleporting);
* the state was not interpolated between solver rows.

Measured on v0.4: chemostat paused at t = 50 d for 10 s → **374 cells dropped at random positions** with ≈23
cells on screen. Details and code excerpts are in `docs/DEVELOPMENT_AUDIT.md` §2.

## 3. Files changed (since `a90778b`)
New: `viz/population.py`, `viz/specimen.py`, `viz/field.py`, `library/morphology.py`, `ui/specimen_view.py`,
`ui/specimen_paint.py`, `ui/reality_page.py`, `ui/agar_page.py`, `ui/interaction_graph.py`, `agar/model.py`,
`analysis/reality.py`, `analysis/changes.py`, `analysis/replicates.py`, 7 new test files, 4 new scripts,
and 4 new docs plus `docs/models/agar.md` and `docs/images/`.
Modified: the three scenes and three lab widgets, `workspace.py`, `main_window.py`, `start_screen.py`,
`organism_card.py`, `trajectory.py`, `db.py`, `schema.sql`, `i18n.py`, `organisms.py`, `guide.py`, `yogurt.py`,
`labs/__init__.py`, README, CHANGELOG, ROADMAP and the verification and yoghurt model docs.
`git diff --stat a90778b..HEAD`: about 50 files, +5 900 / −740 lines.

## 4. Features — status

| Feature | Status |
|---|---|
| Persistent visual identities, no orphan spawns, no teleporting, pause/settle, replay | ✅ completed (tested) |
| 12 organism-specific reproduction styles (fission, chains, packets, budding, autospores, coenobium, diatom valve, transverse/longitudinal fission, amoeboid fission, parthenogenesis, hyphal branching) | ✅ completed |
| 11 motility styles (Brownian, run-and-tumble, run-reverse, ciliary, flagellar, amoeboid, gliding, sessile stalk contraction, corona, creeping, hyphal) | ✅ completed |
| Simulation time vs render time, interpolation, adjustable playback and swimming speed | ✅ completed |
| Morphology spec for all 30 organisms, with provenance and references | ✅ completed |
| Three view modes (Realistic, Microscope = phase contrast or Gram stain, Explanation overlays) | ✅ completed |
| Zoom, pan, click-to-inspect (cells per mL represented, state, division style, shape source) | ✅ completed |
| Prediction vs Reality (CSV import, mapping, validation, re-simulation of the frozen prediction, metrics, explanation, HTML/JSON report, DB records) | ✅ first usable version |
| "What changed and why" in the Why panel (exact flux attribution, consistency %, evidence, sensitivity, measurement) | ✅ completed |
| Chemostat: repeated stochastic runs with extinction probability and CI | ✅ completed |
| Community: interaction network in Who's Who | ✅ completed |
| Virtual Agar foundation (colony growth, morphology vs food and agar, plate counts, time-lapse, counted markers) | 🟡 foundation (qualitative, one species) |
| Yoghurt calibration interface | ⏳ planned: no observational data set yet; calibration must create a NEW prediction |
| Ciliates visibly eating bacteria across panels | ⏳ planned |
| Full Arabic for plot titles, scan tab and some legends | 🟡 partial (all parameters and new screens are bilingual) |

## 5. Bugs fixed
1. Abrupt spawning and flicker (root cause above).
2. **Yoghurt model 1.0.0: peptide pool went negative** (down to −9 mg/L), hidden by clipping. Fixed in 1.1.0;
   regression test added.
3. Blanket "biosafety level 1 (harmless)" claim. Now per strain and jurisdiction, with representative strains.
4. Drawn-cell mass ignored shape. Now uses shape volume × dry mass density.
5. Agar grid artefacts (cross- and square-shaped colonies). Fixed with an isotropic stencil, round founders and a
   growth-pressure term.
6. Two regressions introduced during the night and fixed before the end: a lost `_run_scan` method, and a
   syntax error in the graph label alignment. Both are now covered by `tests/test_ui_construct.py`.

## 6. Tests run and results
* Baseline: 76 passed.
* Final: **188 passed** (`.venv\Scripts\python -m pytest -q`, about 65 s).
  New: visualization 72, reality 18, agar 8, changes 4, replicates 3, UI construction 5, plus regression tests.
* UI smoke scripts run with screenshots: `ui_smoke.py`, `ui_smoke_v05.py`, `ui_smoke_reality.py` (scratch
  database), `ui_smoke_agar.py`, `morphology_gallery.py`.

## 7. Visual evidence
`docs/images/` (committed) and `screenshots/` (local):
* `v05_full_window.png`: whole workspace with the new controls.
* `v05_chem_seq3.png`, `v05_chem_microscope.png`: chemostat in realistic and phase-contrast modes.
* `v05_mix_explain.png`: five-species community.
* `v05_yog_microscope.png`: yoghurt Gram stain.
* `v05_gallery_natural.png`, `v05_gallery_microscope.png`: all 30 organisms, resting and mid-division.
* `v05_reality.png`: Prediction vs Reality with synthetic data (a delay of 0.48 h was detected as "model early by 0.48 h").
* `v05_agar_count.png`, `v05_agar_dendritic.png`, `v05_agar_mould.png`: plate count, branched B. subtilis,
  mould mat.

**Limitation:** the screenshots were inspected by the developer (an AI) frame by frame, not watched live by a
person. Continuity is proven by tests (no orphan cells, bounded per-frame displacement), but how smooth it
*feels* at 30 fps on the target PC still needs a human look.

## 8. Performance findings
Scene update per frame: v0.4 0.05–0.19 ms → v0.5 0.2–2.1 ms. Painting: 1.6–4.6 ms. Both are far inside the
33 ms budget at 30 fps, and a test enforces < 8 ms per scene update. An agar run is 0.3–3 s in a background
thread. The target GPU is not used (QPainter is CPU), and does not need to be at these caps.

## 9. Scientific limitations
* No model is validated against laboratory data. The comparison tool exists, but no real data set has been
  imported yet.
* Community traits and morphology are literature estimates. Agar is qualitative: its mm scale and clock are
  display conventions.
* The microscope is a cohort visualization: only the counts (× sample factor) are model output; positions,
  paths and individual division timing are illustrative.
* The chemostat parameters were checked against secondary quotations of Fussmann et al. (2000); confirm them in
  the paper's PDF.
* See `docs/SCIENTIFIC_REVIEW.md` §C for the suspected issues list.

## 10. Remaining work (exact continuation plan)
1. Look at the app live on the target PC (Windows, RTX 4060 Ti): play each lab at default and 4× speed in all
   three modes and note anything that still looks like popping. If needed, tune `division_s` per species in
   `library/morphology.py` and `_pressure_duration` in `viz/population.py`.
2. Import the first real yoghurt data set (pH every 15–30 min and selective counts) in Prediction vs Reality.
3. Calibration screen: fit on data set A and create a NEW frozen prediction, then test it on data set B
   (never touch the old one).
4. Agar: two species on one plate; a diffusing benign inhibitor (e.g. acid from a lactic acid bacterium);
   finer grid in spot mode.
5. Microscope: an inset showing a ciliate ingesting bacteria from the 100× panel; spatial structure only if a
   spatial model drives it.
6. Translate the remaining English strings in the Arabic UI (plot titles, scan tab, evidence legend).
7. Open a pull request from `dev/v0.5` to `main` after review (GitHub CLI is not installed here).

## 11. Final commit
The commit that adds this report is the last commit on `dev/v0.5`; run `git log -1 dev/v0.5` to see its hash.
The previous commit was `31bc456`.

## 12. How to run the updated application
```bash
git checkout dev/v0.5
.venv\Scripts\python -m microverse.ui.app
```
Or double-click `MicroVerse.bat` while the `dev/v0.5` branch is checked out. Tests:
`.venv\Scripts\python -m pytest -q`. Screenshot scripts are in `scripts/`. New screens are on the start screen:
**📏 Prediction vs Reality** and **🧫 Virtual Agar**. In any lab, use the **View** and **Swimming** menus under
the player, wheel to zoom, and click an organism to inspect it.
