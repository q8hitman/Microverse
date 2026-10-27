# Model: Virtual agar (`microverse/agar/model.py`)

**Status: qualitative, educational. Not calibrated.**

## Equations (dimensionless)

    ∂n/∂t = ∇²n − μ n b
    ∂b/∂t = ∇·(D(x) n b ∇b) + p·min(n,1)·∇²b + μ n b − a(n,b) b
    ∂s/∂t = a(n,b) b,         a(n,b) = a₀ / ((1 + b/k₁)(1 + n/k₂))

* n is nutrient, b is active cells and s is cells that have stopped. Colony density shown = b + s.
* Nonlinear spreading D·n·b (Kawasaki et al. 1997): cells move only where there are both cells and food.
* The stopping rate a(n,b) follows Mimura, Sakaguchi & Matsushita (2000).
* D(x) = d₀ × softness × organism spread × (1 + h·ξ), where ξ is smoothed Gaussian noise (agar heterogeneity).

## Numerics

* Explicit Euler, dt = 0.1, on a 160 × 160 grid inside a circular dish (no flux at the dish wall).
* 8-neighbour isotropic stencil (axial weight ⅔, diagonal weight ⅙), so colonies do not grow as crosses
  (tested).

## Parameters (defaults)

| Symbol | Value | Meaning | Evidence |
|---|---|---|---|
| d₀ | 0.4 | spreading coefficient | assumed (tuned for the morphology diagram) |
| a₀, k₁, k₂ | 0.06, 2.0, 0.5 | stopping rate and its half-saturations | assumed |
| heterogeneity | 0.5 | agar variation | assumed |
| μ (organism) | 0.25–1.0 | relative growth (from typical μmax ranks) | assumed |
| spread (organism) | 0.15–1.4 | relative spreading on agar | assumed |
| HOURS_PER_UNIT | 1 | display clock | assumed |
| NUTRIENT_SCALE | 2 | "rich medium = 1" ↦ model n₀ = 2 | assumed |
| PUSH | 0.01 | small linear growth-pressure spreading (keeps compact colonies round on the grid) | assumed |

## Behaviour checked by tests

* Fields stay ≥ 0 and inside the dish, and nutrient is consumed.
* Richer nutrient and softer agar give bigger, more compact colonies; poor nutrient and hard agar give
  smaller, branched colonies that fill less of their disc.
* Spread plates start Poisson(density × 10⁻ᵏ × volume) colonies. Touching colonies merge, so crowded plates
  under-count. Back-calculated CFU/mL = colonies ÷ (10⁻ᵏ × volume).
* Box-counting dimension: ≈2 for a disc, ≈1 for a line.
* Runs are deterministic for a given seed.

## What it does not do

There is no strain-specific calibration, no antibiotic or inhibitor diffusion, no multi-species competition
(planned), and no real time or length scale. It must not be used to predict real colony sizes.

Colony sizes in mm are NOT predictions: the grid (0.56 mm) is far coarser than real colony fronts, so the
mm scale and clock are display conventions only.
