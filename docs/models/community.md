# Model: `community` (v1.0.0) — EXPLORATORY

A general, trait-driven model. The user picks organisms; the equations are assembled from the traits stored in `microverse/library/organisms.py`. Nothing about any particular pair is hard-coded, so the interactions are consequences of the mechanisms.

## State (mg/L, time in hours)
Eight shared pools — **poly** (polymers), **sug** (sugars), **lac** (lactate), **ace** (acetate), **eth** (ethanol), **nh4** (inorganic nitrogen), **o2** (dissolved oxygen), **det** (detritus) — plus one biomass variable per organism.

## Growth
For organism *i*:
```
base_i = µ_max,i · scale · CTMI(T; Tmin,Topt,Tmax) · CPM(pH; pHmin,pHopt,pHmax) · f_O2
f_O2 = o2/(K+o2)                 aerobe          (photoautotrophs: 1, they make their own)
     = Ki/(Ki+o2)                anaerobe
     = max(o2/(K+o2), 0.55·Ki/(Ki+o2))   facultative
     = o2/(K+o2) · 1/(1+o2/4)    microaerophile

heterotroph      µ = base · S/(Ks+S) · N/(K_N+N),  S = Σ of the pools it can eat
photoautotroph   µ = base · light · NH4/(Ks+NH4)         (releases 1.4 mg O₂ per mg biomass)
chemolithotroph  µ = base · NH4/(Ks+NH4)                 (consumes NH₄, needs O₂)
predator         I = I_max · base-factors · P/(Ks,prey+P) · X,   growth = yield · I · N/(K_N+N)
                 P = Σ over prey with size ≤ prey_size_max of X²/(X+refuge)
```
Uptake is split across the usable pools in proportion to their concentration. Fermenters convert a fixed fraction of the substrate they consume into their products (`products` in the trait table); the rest is respired, consuming O₂ if they can use it. Organisms with a `hydrolysis` trait convert polymers into sugars outside the cell, which **any** organism can then take up.

Every organism dies at its basal rate — including when temperature, pH or oxygen is outside its limits so it cannot grow. Dead biomass becomes detritus, which is slowly converted back to polymers and mineralised nitrogen.

pH is solved from a charge balance between the lactate and acetate produced and a single lumped medium buffer (`buffer`, mmol/L, pKa 6.4), anchored at the chosen starting pH. Oxygen exchanges with the air at rate `aeration`; a sealed vessel (`aeration = 0`) starts purged, as an anaerobic jar does, and any excess oxygen above saturation bubbles out.

## Prey refuge
Grazing acts on `X²/(X+refuge)`, so a small amount of each prey is inaccessible (cells attached to the wall, in aggregates or in biofilm). This is a standard device: without it a deterministic model drives prey to exactly zero and no recovery is possible. It is smooth, which also keeps the solver stable.

## Interactions
`analysis/interactions.py` measures them instead of asserting them: it re-runs every organism **alone** and every **pair** in the same environment, then takes log₁₀(final biomass in the pair / alone) for each direction. Signs give the type (mutualism, commensalism, competition, amensalism, predation, none; threshold 0.15 ≈ 40%). The mechanism sentences are derived from the two organisms' traits — shared substrates, size versus prey limit, products versus substrates, acid versus pH limit, oxygen production or consumption, nitrogen fixation.

## Assumptions
Listed in the app's "Why?" panel. Main exclusions: spatial structure and biofilm, salinity, phosphorus, silicate, vitamins and trace metals, antibiotics and bacteriocins, phages, sporulation and dormancy, evolution, and prey selection by anything other than size.

## Verification tests (`tests/test_community.py`)
Flux terms sum to the right-hand side; cardinal functions; pH monotonic in acid and resisted by buffer; organics + biomass never increase in a closed vessel; nothing grows without its substrate; an organism outside its limits declines instead of freezing; anaerobes are inhibited by oxygen; photoautotrophs make oxygen and need light; an acid producer stops at its own pH minimum; the refuge prevents absolute extinction; a grazer cannot eat prey above its size limit; interaction classification and reproducibility; all presets run and explain in both languages; the scene never modifies the state.

## Validation status
**Not validated.** Trait values are textbook estimates. Use the predictions to design experiments; measure plate counts, pH and dissolved oxygen, then compare against a frozen prediction.
