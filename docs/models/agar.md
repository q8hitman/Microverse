# Model: Virtual agar (`microverse/agar/model.py`)

**Status: qualitative, educational. Not calibrated.**

## Equations

For each organism i (one or two on a plate):

    ∂n/∂t = d_n ∇²n − Σ μ_i n b_i f_i / Y_i                          nutrient: diffuses, is used
    ∂b_i/∂t = ∇·(D_i(x) n b_i f_i ∇b_i) + p·min(n,1)·∇²b_i + μ_i n b_i f_i − a(n,B) b_i
    ∂s_i/∂t = a(n,B) b_i,        a(n,B) = a₀ / ((1 + B/k₁)(1 + n/k₂)),   B = Σ b_i
    ∂h/∂t = d_h ∇²h + Σ y_acid,i μ_i n b_i f_i / Y_i                    lactic acid (if any producer)
    f_i(h) = max(0, 1 − h / (buffer · h_stop,i))²                       acid stops growth at h_stop

* n is nutrient, b active cells, s cells that have stopped, h lactic acid. Colony density shown = Σ (b + s).
* Nonlinear spreading D·n·b (Kawasaki et al. 1997): cells move only where there are both cells and food.
* The stopping rate a(n,B) follows Mimura, Sakaguchi & Matsushita (2000). Crowding counts both organisms.
* D_i(x) = d₀ × softness × organism spread × (1 + h·ξ), where ξ is smoothed Gaussian noise (agar heterogeneity).
* Only lactic acid bacteria make acid (y_acid ≈ 0.9 g lactate per g sugar fermented). They keep little of the food
  as biomass (Y = 0.3), so they use more food per cell than aerobes (Y = 1). Other fermentations are not modelled.
* The acid limit h_stop plays the role of the organism's minimum pH. Values are assumed: lactic acid bacteria
  2.0 (they tolerate more acid than they make, so they slow down but do not stop), yeast and mould 4.0,
  E. coli 0.5, B. subtilis 0.35, P. putida 0.4. Units: with "rich medium = 1" taken as ≈10 g/L fermentable sugar,
  one acid unit ≈ 5 g/L lactic acid. Agar buffering scales every h_stop.

## Diffusion constants (physical, for the assumed clock)

One model length unit is 90/160 = 0.5625 mm (spread-plate grid) and one time unit is `HOURS_PER_UNIT` = 1 h.

| | value in model units | physical value it represents |
|---|---|---|
| d_n (nutrient) | 7.6 | glucose in water ≈ 0.67×10⁻⁹ m²/s ≈ 2.4 mm²/h |
| d_h (lactic acid) | 1.4 × d_n | lactate ≈ 1.0×10⁻⁹ m²/s (≈1.4× glucose) |

Before v0.5.1 the nutrient diffusion was 1 (7.6× too slow for the clock), which made colony edges smooth and
acid halos far too narrow.

## Numerics

* Operator splitting: growth, stopping and cell spreading by explicit Euler, with as many equal sub-steps as the
  local spreading rate needs for stability; then diffusion of nutrient and acid in their own cheap sub-steps.
* 8-neighbour isotropic stencil (axial weight ⅔, diagonal weight ⅙) implemented as 3×3 convolutions, so colonies
  do not grow as crosses (tested).
* The dish wall is no-flux for every field (neighbour weights are zero across it). Before v0.5.1 it absorbed
  nutrient.
* Spread plates: 160 × 160 grid (0.56 mm cells). Spot mode: 240 × 240 (0.375 mm cells; `spot_res` = 1.5) with the
  same physics (dx and dt rescaled), so one colony's edge is resolved better. A colony is the same size on both
  grids within 20 % (tested; the coarse grid smears edges slightly outwards).
* Spread plates: a plated colony-forming unit starts as a few cells in one grid square (`FOUNDER` = 4 × `ONE_CELL`),
  so it needs ≈25 doublings to become visible. `ONE_CELL` ≈ 3×10⁻⁹ of full density is an **assumed** scale (≈10⁹
  cells/mm² in a full colony); it puts ≈5×10⁷ cells in a just-visible grid square, while a visual-counting study found
  ≈5×10⁶ cells in a just-visible E. coli colony (London et al. 2010, PLoS ONE 5:e8609). A 10× error in the scale moves
  appearance by ≈3 doublings (≈1 h for E. coli on rich agar). With the default settings the first colonies appear at
  ≈10 h (E. coli), ≈26 h (yeast) and ≈38 h (mould): illustrative timings from the relative growth rates, not
  calibrated per organism. Each organism has a usual incubation time (24 h bacteria, 48 h yeast, 72 h mould) that the
  page suggests until the user sets a duration. Before v0.5.2 a founder was 2 % of a full colony spread over ≈2 mm, so
  colonies appeared within an hour already ≈6 mm across.
* Spot mode is different on purpose: it seeds a dense drop of culture (density 0.5, ≈2.8 mm across), which is visible
  from the start, as a real spotted drop is.

## Parameters (defaults)

| Symbol | Value | Meaning | Evidence |
|---|---|---|---|
| d₀ | 0.4 | spreading coefficient | assumed (tuned for the morphology diagram) |
| a₀, k₁, k₂ | 0.06, 2.0, 0.5 | stopping rate and its half-saturations | assumed |
| heterogeneity | 0.5 | agar variation | assumed |
| μ (organism) | 0.25–1.0 | relative growth (from typical μmax ranks) | assumed |
| spread (organism) | 0.02–1.4 | relative spreading on agar | assumed |
| d_n | 7.6 | nutrient diffusion | derived from glucose D (above) |
| ACID_DIFFUSION | 1.4 | lactate / glucose diffusion ratio | literature values in water |
| y_acid, Y (lactic bacteria) | 0.9, 0.3 | acid per food fermented; biomass per food | literature order of magnitude |
| h_stop | 0.35–4 | acid limit per organism | assumed |
| HOURS_PER_UNIT | 1 | display clock | assumed |
| NUTRIENT_SCALE | 2 | "rich medium = 1" ↦ model n₀ = 2 | assumed |
| PUSH | 0.01 | small linear growth-pressure spreading (keeps compact colonies round on the grid) | assumed |

## Plating

* Spread plate: Poisson(density × 10⁻ᵏ × volume) founders at random positions; with two organisms each founder
  is organism 2 with probability `mix2`. Touching colonies merge, so crowded plates under-count.
  Back-calculated CFU/mL = colonies ÷ (10⁻ᵏ × volume). Counts per organism go to the majority organism of each
  merged colony.
* Spot: one central spot, or two spots `spot_gap_mm` apart.
* `delay2_h`: organism 2 is added this long after organism 1 (a deferred test, as in the classic deferred
  antagonism plate: the first organism grows and releases acid before its neighbour arrives).

## Behaviour checked by tests

* Fields stay ≥ 0 and inside the dish; nutrient is consumed; the wall is no-flux.
* Richer nutrient and softer agar give bigger, more compact colonies; poor nutrient and hard agar give smaller
  colonies that fill less of their disc.
* Plate counts follow the dilution formula; crowded plates under-count; founders are Poisson; deterministic per seed.
* Box-counting dimension: ≈2 for a disc, ≈1 for a line.
* Only lactic acid bacteria make acid, bounded by the food they ferment; it spreads outwards.
* Two organisms are planted and counted separately; a deferred organism appears only after its delay.
* In the acid halo (acid has spread there, no lactic colony grows there) E. coli grows much less than on the same
  plate without acid, buffering protects it, and acid-tolerant yeast is hardly affected.

## Known limitations

* **Colony size and clock.** Spread-plate E. coli colonies (rich agar) measure ≈1.9 mm at 12 h, ≈6.6 mm at 24 h and
  ≈15 mm at 48 h; real colonies are ≈1 mm, 2–3 mm and 4–6 mm. So the model is ≈2–3× too large after the first day
  (v0.5.1: 8.4, 11.9 and 18.4 mm, i.e. 3–5×). The remaining error is a grid limit: the edge of a real colony is a
  thin monolayer, but here it advances about one grid square (0.56 mm) every few hours almost regardless of the
  spreading constants. Rules that suppress the vanishing low-density tails at the front do slow it (to ≈0.13 mm/h),
  but on this grid they also make compact colonies grow square (tested and rejected in v0.5.2). Consequence: plates
  crowd and merge at lower counts than real plates, so the model's "countable" range is lower than the 30–300 rule.
  Sizes in mm are not predictions.
* **Branched (dendritic) colonies are not reproduced.** Poor, hard agar gives lobed, irregular colonies, but not the
  thin DLA-like branches seen with B. subtilis. Branches would be thinner than a grid cell; a much finer grid
  or a different growth rule would be needed. (v0.5 wrongly called its B. subtilis screenshot "branched"; it was a
  compact disc.)
* No strain-specific calibration, no antibiotics (by design), no real time or length scale.

It must not be used to predict real colony sizes or real inhibition-zone widths.
