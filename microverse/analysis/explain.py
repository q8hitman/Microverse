"""Explanation engine.

Builds an explanation strictly from the model inputs and computed quantities:
flux terms at the selected time, the long-run regime (equilibria + eigenvalues),
features of the simulated trajectory and, if provided, sensitivities.
Nothing here chooses an outcome; it only reports why the numbers are what they are.
"""
from __future__ import annotations

import html
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from ..core.trajectory import Trajectory
from ..models.chemostat_rotifer import ChemostatRotifer
from .regimes import oscillation_period
from .sensitivity import Elasticity
from .stability import Regime, classify

ASSUMPTIONS = [
    "Well-mixed vessel: no spatial structure, no wall growth.",
    "Nitrogen is the only limiting resource; light and temperature are constant.",
    "Algal and rotifer traits are fixed (no evolution, no clumping/defence — known to alter real cycles).",
    "Stage structure is simplified to reproducing vs. non-reproducing rotifers; eggs are not tracked.",
    "Rendered cell counts use assumed nitrogen-per-cell conversions; they do not affect the dynamics.",
]

MEASUREMENTS = [
    "Algal density (cells/mL) by haemocytometer or flow cytometry, daily.",
    "Rotifer density (individuals/mL) and fraction of females carrying eggs, daily, in a counting chamber.",
    "Dissolved nitrogen (nitrate/ammonium) in the outflow.",
    "Exact dilution rate (outflow volume per day ÷ vessel volume).",
    "Run long enough (≥ 3 expected periods) to distinguish damped from sustained oscillations.",
]


@dataclass
class Explanation:
    time: float
    state: dict[str, float]
    rates: dict[str, float]
    terms: dict[str, list[tuple[str, float, str]]]
    dominant: list[str]
    regime: Regime
    trajectory_notes: list[str]
    alternatives: list[str]
    sensitivities: list[Elasticity] = field(default_factory=list)
    evidence: dict[str, int] = field(default_factory=dict)
    unverified_params: list[str] = field(default_factory=list)
    mode: str = "deterministic"


def explain(model: ChemostatRotifer, traj: Trajectory, idx: int,
            sensitivities: list[Elasticity] | None = None) -> Explanation:
    p = traj.config.parameters
    y = traj.y[idx]
    t = float(traj.t[idx])
    rhs = model.rhs(t, y, p)
    syms = [s.symbol for s in model.state_vars]
    terms: dict[str, list] = {s: [] for s in syms}
    for ft in model.flux_terms(y, p):
        terms[ft.target].append((ft.name, ft.value, ft.formula))

    dominant = []
    names = {s.symbol: s.name for s in model.state_vars}
    for s in ("C", "B"):
        ts = sorted(terms[s], key=lambda x: -abs(x[1]))
        pos = max(terms[s], key=lambda x: x[1])
        neg = min(terms[s], key=lambda x: x[1])
        net = rhs[syms.index(s)]
        level = y[syms.index(s)]
        if level < 1e-6:
            dominant.append(f"{names[s]} is effectively absent at this time.")
            continue
        direction = "increasing" if net > 0 else "decreasing"
        rel = net / level
        dominant.append(
            f"{names[s]} is {direction} at {rel:+.2f}/d per unit biomass: largest gain is "
            f"{pos[0]} ({pos[1]:+.3g}), largest loss is {neg[0]} ({neg[1]:+.3g} µmol N/L/d). "
            f"Biggest single term: {ts[0][0]}."
        )
    fC = p["bC"] * y[0] / (p["KC"] + y[0])
    gB = p["bB"] * y[1] / (p["KB"] + y[1])
    dominant.append(
        f"Algae divide at F_C = {fC:.2f}/d ({100 * fC / p['bC']:.0f}% of max, because N = {y[0]:.3g} vs K_C = {p['KC']:.3g}); "
        f"rotifers recruit at F_B = {gB:.2f}/d ({100 * gB / p['bB']:.0f}% of max, algae {y[1]:.3g} vs K_B = {p['KB']:.3g}). "
        f"Rotifers need {p['delta'] + p['m'] + p['lam']:.2f}/d to keep egg-bearing females from declining."
    )

    regime = classify(model, p)
    notes = []
    per = oscillation_period(traj.t, traj.series("C"))
    tail = traj.y[int(len(traj.t) * 0.6):]
    if per:
        notes.append(f"The simulated algae oscillate with a mean period of ≈ {per:.1f} d over the last half of the run.")
    notes.append("Last 40% of the run — algae range "
                 f"{tail[:, 1].min():.3g}–{tail[:, 1].max():.3g}, rotifers {tail[:, 3].min():.3g}–{tail[:, 3].max():.3g} µmol N/L.")
    if regime.period_estimate_d and regime.key in ("limit_cycle", "damped_oscillation"):
        notes.append(f"Linearisation predicts oscillations of period ≈ {regime.period_estimate_d:.1f} d near equilibrium "
                     "(real cycles can be longer because they are non-linear).")
    notes.extend(traj.events)

    alts = []
    if traj.config.mode == "deterministic":
        if regime.key == "limit_cycle":
            alts.append("In a real (finite) vessel, rotifer troughs can fall to a few individuals; demographic noise may "
                        "then cause extinction. Run the stochastic mode with several seeds to estimate how often.")
        if regime.key in ("damped_oscillation", "limit_cycle"):
            alts.append("Near the Hopf point small parameter errors flip the outcome between damped and sustained cycles — "
                        "check the regime scan and the sensitivity table.")
        alts.append("Rapid algal evolution (e.g. grazing-resistant clumps) can lengthen cycles and shift their phase; "
                    "this model excludes it.")
    else:
        alts.append(f"This is one stochastic replicate (seed {traj.config.seed}, volume {traj.config.volume_ml:g} mL). "
                    "Other seeds can give different extinction times; compare several.")

    params = model.default_parameters().params
    ev = Counter(params[k].evidence.value for k in p)
    unverified = [k for k in p if params[k].source is not None and not params[k].verified_against_source
                  and params[k].evidence.value != "control"]
    return Explanation(t, dict(zip(syms, map(float, y))), dict(zip(syms, map(float, rhs))),
                       terms, dominant, regime, notes, alts, sensitivities or [], dict(ev), unverified,
                       traj.config.mode)


def to_html(ex: Explanation, model: ChemostatRotifer) -> str:
    e = html.escape
    units = {s.symbol: s.unit for s in model.state_vars}
    names = {s.symbol: s.name for s in model.state_vars}
    out = [f"<h3>Explanation at t = {ex.time:.1f} d <span style='color:#888'>({e(ex.mode)} run)</span></h3>"]
    out.append("<p style='color:#c96'><b>Status:</b> mathematically verified model, <b>not biologically validated</b>. "
               f"{len(ex.unverified_params)} literature parameters still need checking against the source paper.</p>")
    out.append("<h4>What is happening now</h4><ul>" + "".join(f"<li>{e(d)}</li>" for d in ex.dominant) + "</ul>")
    out.append("<h4>Computed terms (µmol N/L/d)</h4><table cellspacing=0 cellpadding=3>")
    for s, ts in ex.terms.items():
        out.append(f"<tr><td colspan=3><b>d{s}/dt = {ex.rates[s]:+.4g}</b> — {e(names[s])} "
                   f"= {ex.state[s]:.4g} {e(units[s])}</td></tr>")
        for name, val, formula in ts:
            out.append(f"<tr><td>&nbsp;&nbsp;{e(name)}</td><td><code>{e(formula)}</code></td>"
                       f"<td align=right>{val:+.4g}</td></tr>")
    out.append("</table>")
    title = "Long-run prediction" if ex.mode == "deterministic" else \
        "Deterministic long-run prediction (infinite-volume limit — compare with this replicate below)"
    out.append(f"<h4>{title}: {e(ex.regime.label)}</h4><ul>"
               + "".join(f"<li>{e(r)}</li>" for r in ex.regime.reasoning) + "</ul>")
    out.append("<p><i>Method:</i> analytic equilibria of the ODE system + eigenvalues of its Jacobian "
               "(linear stability analysis).</p>")
    out.append("<h4>Simulated trajectory</h4><ul>" + "".join(f"<li>{e(n)}</li>" for n in ex.trajectory_notes) + "</ul>")
    if ex.sensitivities:
        out.append("<h4>Sensitivity of long-run mean rotifer biomass</h4><table cellpadding=2>")
        for s in ex.sensitivities[:9]:
            out.append(f"<tr><td>{e(s.symbol)}</td><td align=right>{s.value:+.2f}</td></tr>")
        out.append("</table><p style='color:#888'>Elasticity: % change in output per 1% change in the parameter "
                   "(±5% central difference, deterministic).</p>")
    out.append("<h4>Alternative plausible outcomes</h4><ul>" + "".join(f"<li>{e(a)}</li>" for a in ex.alternatives) + "</ul>")
    out.append("<h4>Assumptions</h4><ul>" + "".join(f"<li>{e(a)}</li>" for a in ASSUMPTIONS) + "</ul>")
    out.append("<h4>Suggested lab measurements to test this</h4><ul>"
               + "".join(f"<li>{e(m)}</li>" for m in MEASUREMENTS) + "</ul>")
    out.append("<h4>Evidence behind the parameters</h4><p>"
               + ", ".join(f"{e(k)}: {v}" for k, v in sorted(ex.evidence.items())) + "</p>")
    out.append("<p style='color:#888'>Reference: Fussmann et al. (2000) Science 290:1358. "
               "Confidence percentages are not shown because the model has not been calibrated to data.</p>")
    return "\n".join(out)
