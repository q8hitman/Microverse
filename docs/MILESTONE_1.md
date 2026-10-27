# Milestone 1 — "Chemostat Microcosm": algae, rotifers and nitrogen

## Why this system
- **Low risk.** A green alga (*Chlorella vulgaris*) and a freshwater rotifer (*Brachionus calyciflorus*) are harmless organisms that are used in teaching labs.
- **Real experimental benchmark.** Fussmann, Ellner, Shertzer & Hairston (2000), *Science* 290:1358–1360, grew exactly this system in nitrogen-limited chemostats and showed that by changing **only the dilution rate δ** it switched between *coexistence at equilibrium*, *predator–prey cycles* and *extinction*. So M1 has a published qualitative pattern to compare against later (Prediction vs Reality), rather than a canned animation.
- **Real modelling.** Monod nutrient uptake, Holling type II grazing, a stage structure (egg-bearing rotifers age), chemostat washout. Outcomes come from the equations: changing a slider changes the result for reasons the explanation engine can trace.

## Scope (what M1 must do)
| # | Feature | Acceptance criterion |
|---|---|---|
| 1 | Model library entry `chemostat_rotifer` | Equations, parameters with units, provenance and evidence level; doc page in `docs/models/`. |
| 2 | Deterministic simulation | SciPy LSODA; results reproducible to numerical tolerance. |
| 3 | Stochastic simulation | Tau-leaping with demographic noise in a finite volume, fixed seed ⇒ identical results. |
| 4 | Scheduler + trajectory | Every run stores the full config + SHA-256 hash. |
| 5 | Adjustable parameters | UI panel with units, bounds, source tooltip, evidence badge; "reset to literature values". |
| 6 | Graphs | Live time series of N, C, R, B with playback cursor; dilution-rate regime scan (min/max of algae vs δ). |
| 7 | Visible changes | Microscope view rendered **from the state**: chamber view (rotifers, eggs on egg-bearing ones, water tint from algal density) + high-magnification inset of algal cells. Counts are Poisson samples of state × sample volume. |
| 8 | Traceable explanation | At any time point: each flux term with its number, the dominant processes, long-run regime from equilibrium + Jacobian eigenvalues, sensitivity (elasticities), assumptions, alternative outcomes, suggested lab measurements. |
| 9 | Reproducible experiment saving | Save/load JSON; freeze a prediction into SQLite (immutable). |
| 10 | Tests | pytest for the computational core (analytic equilibria, washout threshold, Jacobian, seeds, hashes, renderer cannot change state). |
| 11 | Honesty | UI and docs state: verified ≠ validated; parameter values pending check against the original paper. |

## Out of scope for M1
School/Research mode differences (only University mode), PDF export, image import, 3D, AI assistant, spatial models.
