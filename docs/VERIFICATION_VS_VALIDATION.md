# Verification vs. validation

| | Verification | Validation |
|---|---|---|
| Question | Does the code solve the equations we wrote down? | Do those equations describe real microbes? |
| Evidence | Analytic solutions, conservation laws, consistency checks, reproducibility | Independent laboratory or field observations |
| Can be automated? | Yes — `tests/` | Partly — needs real data, held out from calibration |
| M1 status | **Done for the core** (76 tests) | **Not done** |

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
