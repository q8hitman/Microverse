# Model: `yogurt` (v1.0.0) — EXPLORATORY

## Biological interpretation
Milk inoculated with *Streptococcus thermophilus* (ST) and *Lactobacillus delbrueckii* subsp. *bulgaricus* (LB) and held at a constant temperature. Both ferment the glucose half of lactose to lactic acid and excrete galactose. Falling pH makes casein micelles aggregate (gel onset ≈ pH 5.2, end point ≈ pH 4.6 = casein isoelectric point). LB proteolysis releases peptides that ST needs; ST produces formate that stimulates LB (protocooperation).

## State variables
XS, XL (10⁸ CFU/mL) · Lac, Gal, A (g/L) · P peptides, F formate (mg/L). Time in hours.

## Equations
```
μ_S = μ_S,opt · CTMI(T; T_min,S, T_opt,S, T_max,S) · CPM(pH; pH_min,S, 6.5) · Lac/(0.5+Lac) · [a_S + (1−a_S)·P/(K_P+P)]
μ_L = μ_L,opt · CTMI(T; T_min,L, T_opt,L, T_max,L) · CPM(pH; pH_min,L, 5.8) · Lac/(0.5+Lac) · [a_L + (1−a_L)·F/(K_F+F)]
dXS/dt = μ_S XS                 dXL/dt = μ_L XL
r_A = α(μ_S XS + μ_L XL) + β_S·g_S·XS + β_L·g_L·XL      (Luedeking–Piret; g = acid activity, active down to pH_min − 0.5)
dA/dt = r_A    dLac/dt = −1.90 r_A    dGal/dt = +1.00 r_A   (342.3/(2·90.08) g lactose per g lactate)
dP/dt = k_P·CTMI_L·XL − y_P μ_S XS     dF/dt = y_F μ_S XS
pH: solves  Z + [H⁺] = Σ_i B_i/(1+10^(pKa_i−pH)) + A/(1+10^(3.86−pH))   (B_i: 71.3 mM pKa 6.8, 22.4 mM pKa 5.1, 66.7 mM pKa 4.4, × buffer strength)
```
CTMI: Rosso et al. 1993; CPM: Rosso et al. 1995.

## Parameters and evidence
Process parameters are experimenter controls. Lactose and optimal temperatures are literature estimates. **All interaction, acid-production and cardinal-limit values are assumed (illustrative)**, chosen so the default run shows typical textbook behaviour: pH 4.6 after ≈5–6 h at 43 °C with ≈10⁷ CFU/mL of each species; co-culture faster than either monoculture; failure near 50 °C. The buffer model was fitted to approximate textbook acidification points (±0.08 pH), not to a measured titration curve.

## Assumptions
See the "Assumptions" list in the app (`microverse/analysis/explain_yogurt.py`). Main exclusions: cell death, phages, EPS/texture, Gal⁺ strains, CO₂/folate/urease cross-feeding, oxygen.

## Verification tests (tests/test_yogurt_and_labs.py)
Cardinal functions = 1 at optimum and 0 outside limits; pH curve monotonic with pH 6.65 at zero acid; flux terms sum to rhs; lactose/galactose/lactate stoichiometry; monocultures stay mono; 50 °C fails; sensitivity signs (μ_S −, buffer +); scene does not modify state.

## Validation status
**Not validated.** Ideal first study: measure pH every 15–30 min for several temperatures and starter ratios, freeze the predictions first, then calibrate on part of the data and test on the rest.
