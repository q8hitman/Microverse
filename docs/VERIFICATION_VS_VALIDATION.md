# Verification vs. validation

| | Verification | Validation |
|---|---|---|
| Question | Does the code solve the equations we wrote down? | Do those equations describe real microbes? |
| Evidence | Analytic solutions, conservation laws, consistency checks, reproducibility | Independent laboratory or field observations |
| Can be automated? | Yes — `tests/` | Partly — needs real data, held out from calibration |
| Status (v0.5) | **Done for the core, the visual rules and the comparison maths** (188 tests) | **Not done** |

## What the M1 tests verify
- Flux terms sum exactly to the right-hand side (explanations are consistent with the dynamics).
- Analytic Jacobian = finite-difference Jacobian.
- Algae-only equilibrium N* = K_C·δ/(b_C−δ) is reached; nitrogen mass balance N + C → Nᵢ without rotifers.
- Washout threshold δ_c = b_C·Nᵢ/(K_C+Nᵢ).
- Analytic coexistence equilibrium is a fixed point; stable cases converge to it; unstable cases cycle.
- Deterministic and stochastic runs are reproducible from the config (seed, hash); stochastic mean ≈ deterministic in large volumes; extinction is exact and reported.
- Database predictions cannot be updated or deleted; experiment files detect tampering.
- The renderer never modifies the trajectory, and drawn counts follow the state.

## What would count as validation (planned)
1. Check every default parameter against Fussmann et al. (2000) and its supplement (owner / ChatGPT review).
2. Qualitative: compare the regime-versus-δ pattern with the published experimental chemostats.
3. Quantitative: import chemostat time series (algae cells/mL, rotifers/mL), compare with a **frozen** prediction, compute errors (RMSE on log densities, period and amplitude error), recalibrate on one dataset, evaluate on a different one.

Until then, outputs are **mechanistic predictions** from literature-based parameters.

## Added in v0.5
- **Visual engine** (`tests/test_visualization.py`): no drawn cell appears without a parent (or entering from
  the edge); no teleporting; cells stay in the field; drawn counts follow the model; one sample factor per run;
  nothing is born or dies while paused; replay; deterministic for a seed; every division style keeps the mother
  and puts the daughters nearby; motility styles are distinct and continuous; speed of the scene update.
- **Prediction vs Reality** (`tests/test_reality.py`): CSV parsing (BOM, semicolons, comments, decimal comma),
  timestamps, units including log10 CFU, range checks, metrics against hand calculations, log scale for counts,
  time-shift detection, a frozen prediction re-simulated exactly, saving a report never changes the prediction,
  tampering is detected.
- **Explanations** (`tests/test_changes.py`): the reported flux terms add up to the actual change.
- **Replicates** (`tests/test_replicates.py`), **Agar** (`tests/test_agar.py`), **UI construction** off-screen
  (`tests/test_ui_construct.py`), and a regression test for the yoghurt peptide fix.

The comparison page is the tool for validation, but no laboratory data set has been compared yet.
