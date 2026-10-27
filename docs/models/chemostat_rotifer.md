# Model: `chemostat_rotifer` (v1.0.0)

## Biological interpretation
A continuously diluted, well-mixed culture vessel (chemostat). Medium containing nitrogen at concentration Nᵢ flows in at dilution rate δ (volume exchanged per day ÷ vessel volume) and culture flows out at the same rate.
- **N** – dissolved inorganic nitrogen (µmol N L⁻¹), the limiting nutrient.
- **C** – *Chlorella vulgaris* biomass (µmol N L⁻¹), takes up N with Monod kinetics.
- **R** – *reproducing* (egg-bearing) *Brachionus calyciflorus* (µmol N L⁻¹). Rotifers lose fecundity with age, modelled as a decay λ from R to the non-reproducing pool.
- **B** – total rotifer biomass (µmol N L⁻¹); all rotifers graze, only R produce offspring.

## Equations (Fussmann et al. 2000)
```
dN/dt = δ (Nᵢ − N) − F_C(N) C
dC/dt = F_C(N) C − F_B(C) B / ε − δ C
dR/dt = F_B(C) R − (δ + m + λ) R
dB/dt = F_B(C) R − (δ + m) B

F_C(N) = b_C N / (K_C + N)      (Monod uptake)
F_B(C) = b_B C / (K_B + C)      (Holling type II grazing)
```

## Parameters
| Symbol | Meaning | Default | Unit | Evidence |
|---|---|---|---|---|
| δ | dilution rate | 0.5 | d⁻¹ | experimental control variable |
| Nᵢ | inflow nitrogen | 80 | µmol N L⁻¹ | literature_estimate |
| b_C | max algal uptake/growth rate | 3.3 | d⁻¹ | literature_estimate |
| K_C | half-saturation for N | 4.3 | µmol N L⁻¹ | literature_estimate |
| b_B | max rotifer recruitment rate | 2.25 | d⁻¹ | literature_estimate |
| K_B | half-saturation for algae | 15 | µmol N L⁻¹ | literature_estimate |
| ε | rotifer assimilation efficiency | 0.25 | – | literature_estimate |
| m | rotifer mortality | 0.055 | d⁻¹ | literature_estimate |
| λ | loss of fecundity (ageing) | 0.4 | d⁻¹ | literature_estimate |

**Provenance warning:** default values were entered from the developer's knowledge of Fussmann et al. (2000) and **have not yet been checked against the paper's table**. Action item for the owner/ChatGPT: verify each value and unit against the original article and its supplementary material; then update `microverse/models/chemostat_rotifer.py` and change evidence to `measured`/`literature_estimate` with page references.

NCBI Taxonomy IDs used (3077 *Chlorella vulgaris*, 104777 *Brachionus calyciflorus*) should also be confirmed.

Display conversions (render only): 1 µmol N L⁻¹ of algae ≈ 2×10⁴ cells mL⁻¹ and 1 µmol N L⁻¹ of rotifers ≈ 0.7 individuals mL⁻¹. Evidence: **assumed** (order-of-magnitude from typical cell N content). They only affect how many sprites are drawn, never the dynamics.

## Assumptions
Well-mixed vessel; single limiting nutrient; constant temperature and light; no wall growth; no algal clumping or defence evolution (Yoshida et al. 2003 showed algal evolution changes the cycles — deliberately excluded here); rotifer eggs not modelled explicitly; deterministic mode ignores demographic noise.

## Validity domain
δ ∈ [0, ~1.6] d⁻¹ (above that the rotifers cannot persist in the model); Nᵢ in the tens–hundreds of µmol L⁻¹; laboratory chemostats at ~25 °C.

## Numerics
Deterministic: SciPy `solve_ivp` LSODA, rtol 1e-8, atol 1e-10, non-negativity clipped at evaluation. Stochastic: tau-leaping on six reaction channels with Poisson increments in a finite culture volume (individual-level units = 1 algal cell / 1 rotifer, converted with the display conversions above), fixed seed. Long-run regime: coexistence equilibrium in closed form (C* from dR/dt = 0, N* from a quadratic, B* and R* from mass balance), stability from eigenvalues of the analytic Jacobian.

## Verification tests (tests/test_chemostat.py)
Algae-only analytic equilibrium N* = K_C δ/(b_C − δ); washout above δ_c = b_C Nᵢ/(K_C + Nᵢ); analytic Jacobian = finite-difference Jacobian; seeds reproducible; config hash stable; stochastic mean ≈ deterministic at large volume.

## Validation status
**Not validated.** Planned: compare the regime scan (equilibrium / cycles / extinction vs δ) to the published experimental pattern, and allow the owner to import chemostat counts.
