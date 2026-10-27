# Development audit (start of v0.5)

Date: 2026-10-27 · Branch: `dev/v0.5` · Starting commit: `a90778b` ("Add v0.4 status report")

## 1. Baseline

| Check | Result |
|---|---|
| Test suite (`pytest`) | **76 passed** in 8.9 s, matching the v0.4 claim |
| Source size | ≈4 800 lines across `core`, `models`, `analysis`, `labs`, `viz`, `ui` |
| Organisms / functions | 30 records, 20 functions (17 derived from traits), as documented |
| Laboratories | Chemostat (7 scenarios), Yoghurt (8), Community Builder (9 presets + custom) |
| Solver | LSODA (`scipy.integrate.solve_ivp`); tau-leaping for the chemostat, with exact extinction |
| Frozen predictions | SQLite triggers forbid UPDATE/DELETE, and a record hash is stored |
| Empirical validation | None (as documented) |

The repository's claims were checked against the code; they were accurate except where noted below.

## 2. Root cause of "organisms suddenly spawn"

All three microscope scenes (`viz/scene.py`, `viz/yogurt_scene.py`, `viz/community_scene.py` at `a90778b`)
turned the model state into drawn cells with an **immigration–death process**:

```python
# every frame, for every species (v0.4)
arr = arr[rng.random(len(arr)) >= mu * dt_real]          # each cell vanishes with probability dt/0.6 s
k = rng.poisson(mu * target * dt_real)                     # new cells…
new = uniform(0, field_width), uniform(0, field_height)    # …dropped at random positions
```

Consequences, all visible in the app:

1. **Cells lived ≈0.6 real seconds.** The whole drawn population was replaced about every 0.6 s, by
   cells appearing at random positions. Measured on v0.4: with playback **paused** for 10 s at
   t = 50 d in the chemostat, **374 cells were dropped at random positions** while only ≈23 were on screen.
2. **This happened even when paused**, because `sync()` ran on every animation frame whether or not
   simulation time moved.
3. **The per-species dilution factor was re-chosen every frame** in 2× steps (`expected_counts`), so the
   target number of drawn cells jumped by a factor of 2 whenever the factor switched.
4. **Positions wrapped** (`x %= width`), so swimmers teleported from one edge to the other.
5. Simulation time was **not interpolated** (`index_at` picked an output row), so counts moved in steps.
6. There was **no identity and no reproduction**: a "new" cell had no parent, so growth could not look
   like division.

So the bug was not one line: the scenes had no persistent individuals at all. The fix (see
`VISUALIZATION_ARCHITECTURE.md`) replaces the process rather than masking it with fades.

## 3. Other findings during the audit

| # | Finding | Type | Status |
|---|---|---|---|
| A1 | Yoghurt model: peptide uptake `y_P·μ_S·X_S` was not limited by the available peptides. Integrated without clipping, the pool reaches **−9 mg/L** (S. thermophilus alone) and −4.7 mg/L (cool scenario). The scheduler's `np.maximum(y, 0)` hid this | **Confirmed bug** | Fixed in model 1.1.0 (uptake × P/(P+0.5)); regression test added |
| A2 | Every organism was labelled "biosafety level 1 (harmless)". Risk group depends on strain and jurisdiction | Correctness of claims | Fixed: per-strain wording, representative strains, test updated |
| A3 | Drawn-cell mass used 0.09 pg × (longest dimension)³, which ignores shape | Rough estimate | Replaced by shape volume × 0.3 pg/µm³ dry mass (documented) |
| A4 | Clipping the solver output at zero (`np.maximum`) can hide negative excursions | Numerical concern | Kept; the new "what changed" check reports when flux terms do not add up to the change |
| A5 | Tau-leap clipping can create mass when a leap overdraws a population | Numerical concern | Documented in SCIENTIFIC_REVIEW; small in practice (populations are large except near extinction) |
| A6 | Chemostat parameters had not been checked against Fussmann et al. (2000) | Provenance | Checked: b_C, K_C, b_B, K_B, m, λ, ε match the published values (see SCIENTIFIC_REVIEW) |
| A7 | No test exercised the Qt workspace; a wiring regression introduced during this work (lost `_run_scan`) was caught only by the screenshot script | Test gap | Added `tests/test_ui_construct.py` (off-screen) |
| A8 | Individual parameter names were English-only | i18n gap | Arabic names for all parameters (`i18n.PARAM_AR`), with a test |

## 4. What was not changed, on purpose

* The three models' equations (apart from A1) and their default parameters were left as they are;
  they are functioning and documented.
* The public scene API (`sync(traj, idx, dt)`, `expected_counts(y)`, `scene.algae`, `scene.cells`,
  `scene.concentration`, track order) was kept so v0.4 code and tests still work.
