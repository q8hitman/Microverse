"""Explanation engine for the yoghurt lab — every sentence is computed from model quantities."""
from __future__ import annotations

import html

import numpy as np

from ..core.trajectory import Trajectory
from ..models.yogurt import XL, XS, Yogurt
from .sensitivity import Elasticity

GEL_ONSET_PH = 5.2        # casein micelles start to aggregate (approx.)
END_PH = 4.6              # isoelectric point of casein; usual end of fermentation

ASSUMPTIONS = [
    "Well-mixed milk at constant temperature; no oxygen, light or stirring effects.",
    "Homolactic fermentation of the glucose half of lactose only; galactose is excreted (Gal⁻ strains).",
    "Protocooperation reduced to two signals: peptides (L. bulgaricus → S. thermophilus) and formate "
    "(S. thermophilus → L. bulgaricus). CO₂, folate, urease and strain differences are not modelled.",
    "pH from a charge balance with a three-buffer approximation of milk, fitted to typical textbook points.",
    "Cell death, bacteriophages and exopolysaccharide production are not modelled.",
    "Most kinetic parameters are ILLUSTRATIVE estimates chosen to reproduce typical behaviour — not fitted to data.",
]
MEASUREMENTS = [
    "pH every 15–30 min with a calibrated probe (the main validation curve).",
    "Titratable acidity (0.1 M NaOH, phenolphthalein) → % lactic acid.",
    "Selective plate counts: S. thermophilus on M17 agar (aerobic, 37 °C); L. bulgaricus on acidified MRS "
    "(pH 5.4, anaerobic, 37–43 °C), at 0 h, end point and after storage.",
    "Lactose, galactose and lactic acid by HPLC (if available).",
    "Repeat each condition at least 3 times to estimate experimental variability.",
]


def _crossing(t, ph, level):
    idx = np.where(ph <= level)[0]
    return float(t[idx[0]]) if len(idx) else None


def milestones(model: Yogurt, traj: Trajectory) -> dict:
    ph = model.ph_series(traj)
    t = traj.t
    return {
        "t_gel_h": _crossing(t, ph, GEL_ONSET_PH),
        "t_end_h": _crossing(t, ph, END_PH),
        "final_pH": float(ph[-1]),
        "final_lactic_g_L": float(traj.series("A")[-1]),
        "lactose_used_pct": float(100 * (1 - traj.series("Lac")[-1] / traj.series("Lac")[0])),
        "final_ST_log": float(np.log10(max(traj.y[-1, XS] * 1e8, 1))),
        "final_LB_log": float(np.log10(max(traj.y[-1, XL] * 1e8, 1))),
    }


def time_to_end(model: Yogurt):
    def metric(traj):
        m = milestones(model, traj)["t_end_h"]
        return float("nan") if m is None else m
    return metric


def _limiting(fs: dict[str, float]) -> str:
    return min(fs, key=fs.get)


def to_html(model: Yogurt, traj: Trajectory, idx: int, sens: list[Elasticity] | None = None) -> str:
    e = html.escape
    p = traj.config.parameters
    y = traj.y[idx]
    t = float(traj.t[idx])
    f = model.factors(y, p)
    terms = model.flux_terms(y, p)
    ms = milestones(model, traj)
    out = [f"<h3>Explanation at t = {t:.2f} h</h3>",
           "<p style='color:#d29922'><b>Status: EXPLORATORY.</b> The equations are verified by tests, but most "
           "parameters are illustrative estimates — use the outputs to form hypotheses, then measure.</p>"]
    # --- now
    st, lb = y[XS] * 1e8, y[XL] * 1e8
    out.append("<h4>What is happening now</h4><ul>")
    out.append(f"<li>pH <b>{f['pH']:.2f}</b>, lactic acid {y[4]:.2f} g/L ({y[4] / 10:.2f}% w/v), "
               f"lactose {y[2]:.1f} g/L, galactose {y[3]:.1f} g/L.</li>")
    out.append(f"<li>S. thermophilus {st:.2e} CFU/mL (log {np.log10(max(st, 1)):.2f}); "
               f"L. bulgaricus {lb:.2e} CFU/mL (log {np.log10(max(lb, 1)):.2f}).</li>")
    for name, mu, mu_opt, fT, fpH, coop, sub, partner in [
        ("S. thermophilus", f["muS"], p["muS"], f["fT_S"], f["fpH_S"], f["coop_S"], f["sub"], "peptides from L. bulgaricus"),
        ("L. bulgaricus", f["muL"], p["muL"], f["fT_L"], f["fpH_L"], f["coop_L"], f["sub"], "formate from S. thermophilus"),
    ]:
        factors = {"temperature": fT, "pH": fpH, "partner support": coop, "lactose": sub}
        lim = _limiting(factors)
        dbl = f"doubling time {np.log(2) / mu * 60:.0f} min" if mu > 1e-4 else "not growing"
        out.append(f"<li><b>{e(name)}</b>: μ = {mu:.3f}/h ({dbl}) = μ_opt {mu_opt:.2f} × temperature {fT:.2f} × "
                   f"pH {fpH:.2f} × {e(partner)} {coop:.2f} × lactose {sub:.2f}. "
                   f"Most limiting factor now: <b>{e(lim)}</b>.</li>")
    a_terms = [x for x in terms if x.target == "A"]
    tot = sum(x.value for x in a_terms)
    if tot > 1e-9:
        share = 100 * a_terms[0].value / tot
        out.append(f"<li>Acid production {tot:.2f} g/L/h: {share:.0f}% from S. thermophilus, "
                   f"{100 - share:.0f}% from L. bulgaricus.</li>")
    boost_S = f["coop_S"] / p["aS"] if p["aS"] > 0 else float("inf")
    boost_L = f["coop_L"] / p["aL"] if p["aL"] > 0 else float("inf")
    out.append(f"<li>Protocooperation: peptides {y[5]:.0f} mg/L make S. thermophilus grow {boost_S:.2f}× faster "
               f"than without its partner; formate {y[6]:.1f} mg/L makes L. bulgaricus grow {boost_L:.2f}× faster.</li>")
    out.append("</ul>")
    # --- terms
    out.append("<h4>Computed terms</h4><table cellpadding=2>")
    units = {s.symbol: s.unit for s in model.state_vars}
    for tm in terms:
        out.append(f"<tr><td>d{e(tm.target)}/dt</td><td>{e(tm.name)}</td><td><code>{e(tm.formula)}</code></td>"
                   f"<td align=right>{tm.value:+.4g} {e(units[tm.target])}/h</td></tr>")
    out.append("</table>")
    # --- predicted outcome
    out.append("<h4>Predicted outcome of this run</h4><ul>")
    if ms["t_gel_h"] is not None:
        out.append(f"<li>Gel formation expected to start ≈ <b>{ms['t_gel_h']:.1f} h</b> (pH ≤ {GEL_ONSET_PH}, casein "
                   "micelles begin to aggregate).</li>")
    if ms["t_end_h"] is not None:
        out.append(f"<li>pH {END_PH} (casein isoelectric point, usual end point) reached at ≈ <b>{ms['t_end_h']:.1f} h</b>.</li>")
    else:
        out.append(f"<li>pH {END_PH} is <b>not reached</b> within {traj.t[-1]:.0f} h — fermentation fails or is too slow.</li>")
    out.append(f"<li>At the end ({traj.t[-1]:.0f} h): pH {ms['final_pH']:.2f}, lactic acid {ms['final_lactic_g_L']:.1f} g/L, "
               f"{ms['lactose_used_pct']:.0f}% of lactose used, log CFU/mL ST {ms['final_ST_log']:.2f} / LB {ms['final_LB_log']:.2f}.</li>")
    if ms["t_end_h"] is not None and ms["final_pH"] < 4.2:
        out.append("<li>Post-acidification: without cooling, L. bulgaricus keeps the pH falling below 4.2 "
                   "(sour taste, whey separation).</li>")
    if p["T"] >= min(p["TmaxS"], p["TmaxL"]) - 1 or p["T"] <= max(p["TminS"], p["TminL"]) + 2:
        out.append("<li>The temperature is close to a cardinal limit of at least one organism — expect strong sensitivity.</li>")
    out.append("</ul>")
    if sens:
        out.append("<h4>Sensitivity of the time to pH 4.6</h4><table cellpadding=2>")
        for s in sens[:10]:
            out.append(f"<tr><td>{e(s.symbol)}</td><td align=right>{s.value:+.2f}</td></tr>")
        out.append("</table><p style='color:#888'>Elasticity: % change in time-to-pH-4.6 per 1% change in the parameter. "
                   "Large values = parameters worth measuring first.</p>")
    out.append("<h4>Alternative plausible outcomes</h4><ul>"
               "<li>Strain differences (proteolytic S. thermophilus, Gal⁺ strains, fast/slow acidifiers) can change the "
               "timing by hours.</li><li>Bacteriophage infection of the starter would stop acidification — not modelled.</li>"
               "<li>Different milk (solids, heat treatment) changes buffering and formate — try 'Milk buffer strength' "
               "and 'Formate from heat treatment'.</li></ul>")
    out.append("<h4>Assumptions</h4><ul>" + "".join(f"<li>{e(a)}</li>" for a in ASSUMPTIONS) + "</ul>")
    out.append("<h4>How to test this in the lab</h4><ul>" + "".join(f"<li>{e(m)}</li>" for m in MEASUREMENTS) + "</ul>")
    return "\n".join(out)
