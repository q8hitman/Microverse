# Scientific review (v0.5)

This review keeps **confirmed programming or modelling errors** (with evidence, now fixed) separate from
**suspected scientific issues** (judgement calls, open questions, things to check with a supervisor).
Nothing in MicroVerse has been validated against laboratory data yet.

## A. Confirmed errors (fixed)

| # | Where | Evidence | Fix |
|---|---|---|---|
| A1 | `models/yogurt.py`, peptide pool P | Integrated without the scheduler's clipping, P fell to −9.0 mg/L (S. thermophilus alone), −4.7 (cool), −1.5 (fortified), −0.47 (classic). The new "what changed" check flagged that the P terms explained 160 % of the change | Uptake now saturates in P: `y_P·μ_S·X_S·P/(P+0.5)`. Model version 1.0.0 → **1.1.0**. Test `test_peptide_pool_never_needs_clipping`. Frozen predictions made with 1.0.0 are re-simulated with the new code and the comparison page says so |
| A2 | Organism records | "Biosafety level 1 (harmless)" applied to every species. Risk group is assigned per strain and per jurisdiction (e.g. E. coli K-12 versus other E. coli) | Records now say that typical teaching/food strains are Risk Group 1 in most national lists and that classification is per strain and country; the representative strain is named (K-12, 168, KT2440, S288C, SB210, PCC 7942, NRC-1…) |
| A3 | Visual scenes | Cells were created at random positions every frame (see DEVELOPMENT_AUDIT §2). The graphs were right but the picture contradicted them (cells "born" while paused) | Persistent visual engine; tests prove that no orphan cells appear and that nothing changes while paused |

## B. Checked and found consistent

* **Chemostat model vs Fussmann et al. (2000), Science 290:1358.** Structure: Monod nitrogen uptake by
  Chlorella; Holling-II recruitment of Brachionus from egg-bearing females R only, while grazing is by all B
  (B/ε); senescence λ moves R to non-reproducing; mortality m plus washout δ. Default parameters
  b_C = 3.3 d⁻¹, K_C = 4.3 µmol N/L, b_B = 2.25 d⁻¹, K_B = 15 µmol N/L, m = 0.055 d⁻¹, λ = 0.4 d⁻¹, ε = 0.25
  agree with the values reported in the paper, as quoted in Shertzer et al. (2002, J. Anim. Ecol. 71:802).
  N_i = 80 µmol N/L is the paper's inflow. *To do: confirm against the paper's PDF and its supplement; the
  check here relied on secondary quotations of the paper.*
* **Units.** Chemostat in µmol N/L and days; yoghurt in g/L, 10⁸ CFU/mL and hours; community in mg/L and hours.
  Conversions to drawn cells: chemostat via the documented cells per µmol N factors; yoghurt via CFU;
  community via morphology volume × 0.3 pg/µm³ dry mass.
* **Non-negativity.** Every scenario and preset stays ≥ 0 (the minimum is exactly 0 where populations die out).
* **Reproducibility.** Deterministic runs are identical for identical configurations (config hash). Stochastic
  runs are identical for the same seed and differ for different seeds. The replicate runner uses seeds
  s, s+1, … so a whole replicate set is reproducible.
* **Explanations follow the dynamics.** For every significant change, the flux terms, integrated exactly by
  re-solving the ODE with accumulators, account for the observed change to within 12 % in the tests (exactly,
  up to solver tolerance, where nothing is clipped).

## C. Suspected issues and open questions (not changed)

| # | Topic | Why it matters | Suggested action |
|---|---|---|---|
| C1 | Clipping at zero (`np.maximum` on solver output and in the RHS) | It can hide negative excursions, as A1 showed. Any remaining case shows up as "terms explain ≠ 100 %" in the Why panel | Prefer formulations that cannot go negative (saturating uptake) over clipping |
| C2 | Tau-leap overdraw | A leap that removes more than exists is clipped to 0, which can create mass slightly | Use a smaller leap near extinction or switch to exact SSA below a threshold (Cao et al. 2006) |
| C3 | Community traits (μmax, Ks, yields, cardinal T/pH) | Textbook orders of magnitude, `literature_estimate` or `assumed`, not fitted | Review the trait table with the supervisor; calibrate one organism at a time on growth curves |
| C4 | Community biomass as dry mass | Yields are treated as dry-weight yields; drawn-cell numbers depend on this | State it in the model page (done in code comments); confirm per organism |
| C5 | Yoghurt pH model | Charge balance with three lumped buffers; post-acidification depends on β terms that are assumed | Compare with published milk titration curves; add a buffer-capacity measurement |
| C6 | Yoghurt peptide uptake constant (0.5 mg/L) | New constant, chosen small so the fix changes results only when P is nearly exhausted | Treat it as `assumed`; sensitivity on it is very small |
| C7 | Rotifer egg display | Eggs are drawn on a fraction R/B of animals (1–2 eggs each); the model has no egg counts | Keep it as visual only (documented) |
| C8 | Agar model | Dimensionless and qualitative (Kawasaki 1997 / Mimura 2000 type). The clock (1 unit ≈ 1 h) and mm scale are assumed; organism differences are relative growth and spreading only | Use it for qualitative teaching; do not read absolute colony sizes as predictions |
| C9 | Drawn morphology | From typical textbook descriptions; strain-to-strain and condition-dependent shape (filamentation, sporulation, pseudohyphae) is not modelled | Add condition-dependent morphology only if a model drives it |

## D. Measurements that would validate each lab first

* **Yoghurt:** pH every 15–30 min at two temperatures, plus selective counts (M17, acidified MRS) at 0, 2, 4
  and 6 h. Import them with **Prediction vs Reality**; the time-shift metric separates lag or rate errors
  from shape errors.
* **Chemostat:** algal and rotifer counts every 1–2 days over ≥ 3 cycles at two dilution rates.
* **Community presets:** pH and selective counts for the pickle succession (L. lactis to L. plantarum).
* **Agar:** colony radius against time at two agar concentrations and two nutrient levels (qualitative
  morphology diagram).
