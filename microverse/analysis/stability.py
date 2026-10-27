"""Long-run regime from equilibria and Jacobian eigenvalues (linear stability analysis)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..models.chemostat_rotifer import ChemostatRotifer


@dataclass
class Regime:
    key: str                 # "washout" | "rotifers_extinct" | "stable_equilibrium" | "damped_oscillation" | "limit_cycle"
    label: str
    equilibrium: np.ndarray | None
    eigenvalues: np.ndarray | None
    reasoning: list[str]

    @property
    def leading_real(self) -> float | None:
        return None if self.eigenvalues is None else float(np.max(self.eigenvalues.real))

    @property
    def period_estimate_d(self) -> float | None:
        """Period of the oscillation implied by the leading complex eigenvalue pair."""
        if self.eigenvalues is None:
            return None
        ev = self.eigenvalues[np.argmax(self.eigenvalues.real)]
        return float(2 * np.pi / abs(ev.imag)) if abs(ev.imag) > 1e-9 else None


def classify(model: ChemostatRotifer, p: dict[str, float]) -> Regime:
    d = p["delta"]
    dc = model.washout_threshold(p)
    if d >= dc:
        return Regime("washout", "Washout: algae and rotifers both disappear", np.array([p["Ni"], 0, 0, 0]), None, [
            f"Dilution δ = {d:.3g}/d is at or above the algal washout threshold "
            f"b_C·Nᵢ/(K_C+Nᵢ) = {dc:.3g}/d.",
            "Even with all inflowing nitrogen available, Chlorella cannot divide faster than it is washed out.",
        ])
    need = d + p["m"] + p["lam"]
    alg = model.algae_only_equilibrium(p)
    co = model.coexistence_equilibrium(p)
    gB_alg = p["bB"] * alg[1] / (p["KB"] + alg[1])
    if co is None:
        return Regime("rotifers_extinct", "Rotifers die out; algae settle at a steady state", alg,
                      np.linalg.eigvals(model.jacobian(alg, p)), [
            f"Egg-bearing rotifers must recruit at ≥ δ+m+λ = {need:.3g}/d to replace themselves.",
            f"With algae at their predator-free level ({alg[1]:.3g} µmol N/L) rotifers recruit at only "
            f"F_B = {gB_alg:.3g}/d" + (" (below the requirement)." if gB_alg < need else "."),
            "No positive coexistence equilibrium exists, so the rotifer population declines to zero.",
        ])
    ev = np.linalg.eigvals(model.jacobian(co, p))
    lead = ev[np.argmax(ev.real)]
    reasons = [
        f"Rotifers can invade: at the predator-free algal level they recruit at {gB_alg:.3g}/d > δ+m+λ = {need:.3g}/d.",
        f"Coexistence equilibrium: N* = {co[0]:.3g}, C* = {co[1]:.3g}, R* = {co[2]:.3g}, B* = {co[3]:.3g} µmol N/L "
        f"(C* is set by the rotifers: K_B(δ+m+λ)/(b_B−δ−m−λ)).",
        f"Leading Jacobian eigenvalue at that point: {lead.real:+.3g} {'+' if lead.imag >= 0 else '−'} {abs(lead.imag):.3g}i per day.",
    ]
    if lead.real > 0:
        reasons.append("Positive real part ⇒ the equilibrium is unstable; the populations spiral away from it into "
                       "sustained predator–prey cycles (beyond a Hopf bifurcation).")
        return Regime("limit_cycle", "Predator–prey cycles", co, ev, reasons)
    if abs(lead.imag) > 1e-9:
        reasons.append("Negative real part with an imaginary part ⇒ oscillations that shrink over time (damped) "
                       "towards a stable equilibrium.")
        return Regime("damped_oscillation", "Damped oscillations to a stable coexistence", co, ev, reasons)
    reasons.append("All eigenvalues real and negative ⇒ monotonic approach to a stable coexistence equilibrium.")
    return Regime("stable_equilibrium", "Stable coexistence", co, ev, reasons)
