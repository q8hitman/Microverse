"""Nitrogen-limited chemostat with Chlorella vulgaris and Brachionus calyciflorus.

Fussmann, Ellner, Shertzer & Hairston (2000) Science 290:1358-1360.
See docs/models/chemostat_rotifer.md for interpretation, assumptions and status.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.model import FluxTerm, Model, Reaction, StateVar
from ..core.parameters import Evidence, Parameter, ParameterSet, Source

FUSSMANN_2000 = Source(
    key="fussmann2000",
    citation="Fussmann GF, Ellner SP, Shertzer KW, Hairston NG Jr (2000). Crossing the Hopf "
             "bifurcation in a live predator-prey system. Science 290:1358-1360.",
    doi="10.1126/science.290.5495.1358",
    note="Values entered from developer knowledge; pending check against the paper's table.",
)

ASSUMED_DISPLAY = Source(
    key="assumed_display_conversion",
    citation="Order-of-magnitude conversion from typical cell nitrogen content (assumed).",
    note="Affects rendered counts and stochastic individual size only.",
)

N, C, R, B = range(4)


@dataclass(frozen=True)
class Morphology:
    organism: str
    taxonomy_id: int          # NCBI Taxonomy ID
    shape: str
    size_um: tuple[float, float, float]     # min, typical, max (longest dimension)
    colour: str
    motility: str
    speed_um_s: float
    evidence: Evidence
    note: str = ""


class ChemostatRotifer(Model):
    id = "chemostat_rotifer"
    version = "1.0.0"
    title = "Chemostat microcosm: nitrogen → Chlorella → Brachionus"
    state_vars = (
        StateVar("N", "Dissolved nitrogen", "µmol N/L", "Limiting nutrient in the vessel"),
        StateVar("C", "Chlorella vulgaris", "µmol N/L", "Algal biomass expressed as nitrogen"),
        StateVar("R", "Egg-bearing rotifers", "µmol N/L", "Reproducing Brachionus"),
        StateVar("B", "All rotifers", "µmol N/L", "Total Brachionus biomass"),
    )

    # Display / individual-size conversions (assumed; see docs)
    algae_cells_per_ml_per_umolN = 2.0e4
    rotifers_per_ml_per_umolN = 0.7

    morphology = (
        Morphology("Chlorella vulgaris", 3077, "sphere", (2.0, 5.0, 10.0), "#3f9b3a",
                   "non-motile (drifts with flow / Brownian motion)", 0.0, Evidence.LITERATURE_ESTIMATE,
                   "Unicellular green alga, cup-shaped chloroplast; reproduces by autospores."),
        Morphology("Brachionus calyciflorus", 104777, "rotifer (lorica with anterior spines, ciliated corona, foot)",
                   (150.0, 250.0, 350.0), "#d9cfb8", "swims using the ciliated corona", 500.0, Evidence.ASSUMED,
                   "Speed is an assumed order of magnitude for rendering only. Females carry eggs attached to the lorica."),
    )

    def default_parameters(self) -> ParameterSet:
        L, F = Evidence.LITERATURE_ESTIMATE, FUSSMANN_2000
        ps = [
            Parameter("delta", "Dilution rate δ", 0.5, "1/d", 0.0, 3.5, Evidence.CONTROL, F,
                      "Fraction of the vessel volume replaced per day; the experimenter's control knob."),
            Parameter("Ni", "Inflow nitrogen Nᵢ", 80.0, "µmol N/L", 1.0, 400.0, L, F,
                      "Nitrogen concentration of the incoming medium."),
            Parameter("bC", "Max algal uptake rate b_C", 3.3, "1/d", 0.1, 10.0, L, F,
                      "Maximum per-capita nitrogen uptake (≈ growth) rate of Chlorella."),
            Parameter("KC", "Algal half-saturation K_C", 4.3, "µmol N/L", 0.1, 50.0, L, F,
                      "Nitrogen concentration at which uptake is half of maximum."),
            Parameter("bB", "Max rotifer recruitment b_B", 2.25, "1/d", 0.1, 6.0, L, F,
                      "Maximum per-capita recruitment rate of Brachionus."),
            Parameter("KB", "Rotifer half-saturation K_B", 15.0, "µmol N/L", 0.1, 100.0, L, F,
                      "Algal density at which rotifer grazing is half of maximum."),
            Parameter("eps", "Assimilation efficiency ε", 0.25, "–", 0.01, 1.0, L, F,
                      "Fraction of grazed algal nitrogen converted into rotifer biomass."),
            Parameter("m", "Rotifer mortality m", 0.055, "1/d", 0.0, 1.0, L, F,
                      "Per-capita death rate of rotifers (excluding washout)."),
            Parameter("lam", "Fecundity decay λ", 0.4, "1/d", 0.0, 3.0, L, F,
                      "Rate at which reproducing rotifers age into non-reproducing ones."),
        ]
        return ParameterSet({p.symbol: p for p in ps})

    def default_initial_state(self) -> np.ndarray:
        return np.array([80.0, 5.0, 1.0, 1.0])

    # ---- deterministic -------------------------------------------------
    @staticmethod
    def _rates(y, p):
        fC = p["bC"] * y[N] / (p["KC"] + y[N])
        gB = p["bB"] * y[C] / (p["KB"] + y[C])
        return fC, gB

    def rhs(self, t, y, p):
        fC, gB = self._rates(y, p)
        d, m, lam, eps = p["delta"], p["m"], p["lam"], p["eps"]
        return np.array([
            d * (p["Ni"] - y[N]) - fC * y[C],
            fC * y[C] - gB * y[B] / eps - d * y[C],
            gB * y[R] - (d + m + lam) * y[R],
            gB * y[R] - (d + m) * y[B],
        ])

    def flux_terms(self, y, p):
        fC, gB = self._rates(y, p)
        d, m, lam, eps = p["delta"], p["m"], p["lam"], p["eps"]
        return [
            FluxTerm("N", "inflow of fresh medium", d * p["Ni"], "δ·Nᵢ"),
            FluxTerm("N", "outflow (washout)", -d * y[N], "−δ·N"),
            FluxTerm("N", "uptake by Chlorella", -fC * y[C], "−F_C(N)·C"),
            FluxTerm("C", "growth from nitrogen uptake", fC * y[C], "F_C(N)·C"),
            FluxTerm("C", "grazing by rotifers", -gB * y[B] / eps, "−F_B(C)·B/ε"),
            FluxTerm("C", "washout", -d * y[C], "−δ·C"),
            FluxTerm("R", "recruitment of new females", gB * y[R], "F_B(C)·R"),
            FluxTerm("R", "ageing (loss of fecundity)", -lam * y[R], "−λ·R"),
            FluxTerm("R", "death + washout", -(d + m) * y[R], "−(δ+m)·R"),
            FluxTerm("B", "recruitment", gB * y[R], "F_B(C)·R"),
            FluxTerm("B", "death + washout", -(d + m) * y[B], "−(δ+m)·B"),
        ]

    def jacobian(self, y, p):
        fC, gB = self._rates(y, p)
        dfC = p["bC"] * p["KC"] / (p["KC"] + y[N]) ** 2
        dgB = p["bB"] * p["KB"] / (p["KB"] + y[C]) ** 2
        d, m, lam, eps = p["delta"], p["m"], p["lam"], p["eps"]
        return np.array([
            [-d - dfC * y[C], -fC, 0.0, 0.0],
            [dfC * y[C], fC - dgB * y[B] / eps - d, 0.0, -gB / eps],
            [0.0, dgB * y[R], gB - (d + m + lam), 0.0],
            [0.0, dgB * y[R], gB, -(d + m)],
        ])

    # ---- analytic equilibria --------------------------------------------
    def washout_threshold(self, p) -> float:
        """Dilution rate above which Chlorella cannot persist (N stays at Nᵢ)."""
        return p["bC"] * p["Ni"] / (p["KC"] + p["Ni"])

    def algae_only_equilibrium(self, p) -> np.ndarray | None:
        d = p["delta"]
        if d >= self.washout_threshold(p):
            return None
        n = p["KC"] * d / (p["bC"] - d)
        return np.array([n, p["Ni"] - n, 0.0, 0.0])

    def coexistence_equilibrium(self, p) -> np.ndarray | None:
        d, m, lam, eps = p["delta"], p["m"], p["lam"], p["eps"]
        need = d + m + lam                     # recruitment rate rotifers need to persist
        if p["bB"] <= need or d <= 0:
            return None
        c = p["KB"] * need / (p["bB"] - need)
        b = p["bC"] * c + d * (p["KC"] - p["Ni"])
        n = (-b + np.sqrt(b * b + 4 * d * d * p["Ni"] * p["KC"])) / (2 * d)
        bb = eps * d * (p["Ni"] - n - c) / need
        if bb <= 0:
            return None
        r = bb * (d + m) / need
        return np.array([n, c, r, bb])

    # ---- stochastic (individual-based tau-leaping) ----------------------
    def _quanta(self, p):
        v = p["_volume_ml"]
        return 1.0 / (self.algae_cells_per_ml_per_umolN * v), 1.0 / (self.rotifers_per_ml_per_umolN * v)

    def state_quanta(self, p):
        qC, qB = self._quanta(p)
        return np.array([0.0, qC, qB, qB])          # N is a dissolved pool, never "extinct"

    def reactions(self, p):
        qC, qB = self._quanta(p)
        eps = p["eps"]
        return (
            Reaction("inflow", (qC, 0, 0, 0), "one algal-cell quantum of N flows in"),
            Reaction("outflow N", (-qC, 0, 0, 0)),
            Reaction("algal uptake/division", (-qC, qC, 0, 0)),
            Reaction("algal washout", (0, -qC, 0, 0)),
            Reaction("grazing by non-reproducing rotifers", (0, -qC, 0, 0)),
            Reaction("recruitment (one rotifer born)", (0, -qB / eps, qB, qB)),
            Reaction("female stops reproducing", (0, 0, -qB, 0)),
            Reaction("reproducing female dies/washes out", (0, 0, -qB, -qB)),
            Reaction("non-reproducing rotifer dies/washes out", (0, 0, 0, -qB)),
        )

    def propensities(self, y, p):
        qC, qB = self._quanta(p)
        fC, gB = self._rates(y, p)
        d, m, lam, eps = p["delta"], p["m"], p["lam"], p["eps"]
        s = max(y[B] - y[R], 0.0)
        return np.array([
            d * p["Ni"] / qC,
            d * y[N] / qC,
            fC * y[C] / qC,
            d * y[C] / qC,
            gB * s / eps / qC,
            gB * y[R] / qB,
            lam * y[R] / qB,
            (d + m) * y[R] / qB,
            (d + m) * s / qB,
        ])
