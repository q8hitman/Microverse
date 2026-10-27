"""'What changed, and why?' — derived from the model's own flux terms.

For the window just before the current time, each state variable whose value changed by more than a
threshold is reported with:
* what changed (from → to);
* which terms of its equation caused it (each term integrated over the window, ranked), and how much of
  the actual change those terms account for (a built-in consistency check);
* the assumptions involved (evidence level of the model's parameters);
* uncertainty (sensitivity results, if computed);
* which measurement would test it.

Nothing here is canned: every number comes from the trajectory and the model's right-hand side.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

import numpy as np

from ..core.parameters import Evidence
from ..i18n import L, is_ar

MEASURE = {
    # chemostat
    "C": ("count Chlorella cells in a counting chamber (or chlorophyll fluorescence)",
          "عدّ خلايا الكلوريلا بشريحة العد (أو قياس فلورة الكلوروفيل)"),
    "B": ("count rotifers in a sieved, fixed subsample", "عدّ الدوّارات في عينة مُصفّاة ومثبّتة"),
    "R": ("count females carrying eggs", "عدّ الإناث الحاملة للبيض"),
    "N": ("measure dissolved nitrate/ammonium (colorimetric kit)", "قياس النترات/الأمونيوم الذائب (عدة لونية)"),
    # yoghurt
    "XS": ("plate counts of S. thermophilus on M17 agar", "عدّ مستعمرات S. thermophilus على آجار M17"),
    "XL": ("plate counts of L. bulgaricus on acidified MRS agar", "عدّ مستعمرات L. bulgaricus على آجار MRS المحمّض"),
    "A": ("titratable acidity or pH", "الحموضة القابلة للمعايرة أو الـ pH"),
    "Lac": ("lactose by enzymatic kit or HPLC", "اللاكتوز بعدة إنزيمية أو HPLC"),
    "Gal": ("galactose by enzymatic kit or HPLC", "الجالاكتوز بعدة إنزيمية أو HPLC"),
    "P": ("free amino groups (OPA assay)", "المجموعات الأمينية الحرة (اختبار OPA)"),
    "F": ("formate by enzymatic kit", "الفورمات بعدة إنزيمية"),
    # community pools
    "poly": ("starch/protein assay", "اختبار النشا/البروتين"), "sug": ("reducing sugars (DNS assay)", "السكريات المختزلة (اختبار DNS)"),
    "lac": ("lactate (enzymatic kit / HPLC)", "اللاكتات (عدة إنزيمية / HPLC)"), "ace": ("acetate (HPLC)", "الأسيتات (HPLC)"),
    "eth": ("ethanol (enzymatic kit / GC)", "الإيثانول (عدة إنزيمية / GC)"), "nh4": ("ammonium (colorimetric kit)", "الأمونيوم (عدة لونية)"),
    "o2": ("dissolved oxygen probe", "مجس الأكسجين الذائب"), "det": ("total suspended solids", "المواد الصلبة العالقة"),
}
ORGANISM_MEASURE = ("selective plate counts, cell counts or OD600 of this organism",
                    "عدّ المستعمرات الانتقائي أو عدّ الخلايا أو OD600 لهذا الكائن")


@dataclass
class Change:
    symbol: str
    name: str
    unit: str
    t0: float
    t1: float
    v0: float
    v1: float
    terms: list[tuple[str, str, float]]       # (name, formula, integrated contribution)
    explained: float                          # fraction of the actual change accounted for by the terms

    @property
    def delta(self) -> float:
        return self.v1 - self.v0


def significant_changes(model, traj, idx: int, window_frac: float = 0.06, rel: float = 0.10) -> list[Change]:
    t = traj.t
    if idx <= 0:
        return []
    span = t[-1] - t[0]
    i0 = int(np.searchsorted(t, t[idx] - window_frac * span))
    i0 = min(max(i0, 0), idx - 1)
    p = dict(traj.config.parameters, _volume_ml=traj.config.volume_ml)
    rows = range(i0, idx + 1)
    terms_by_row = [model.flux_terms(traj.y[i], p) for i in rows]
    exact = _integrate_terms(model, traj, i0, idx, p) if traj.config.mode == "deterministic" else None
    out = []
    for j, sv in enumerate(model.state_vars):
        v0, v1 = float(traj.y[i0, j]), float(traj.y[idx, j])
        scale = max(abs(v0), abs(v1), 1e-9)
        if abs(v1 - v0) / scale < rel or max(abs(v0), abs(v1)) < 1e-6:
            continue
        names = [(ft.name, ft.formula) for ft in terms_by_row[0] if ft.target == sv.symbol]
        series = np.array([[{(x.target, x.name): x.value for x in row}.get((sv.symbol, n), 0.0) for n, _f in names]
                           for row in terms_by_row])
        if series.size == 0:
            continue
        if exact is not None:
            integ = np.array([v for ft, v in zip(terms_by_row[0], exact) if ft.target == sv.symbol])
        else:                                     # stochastic runs: trapezoid on the output rows
            integ = np.trapezoid(series, t[i0:idx + 1], axis=0)
        terms = sorted(((n, f, float(v)) for (n, f), v in zip(names, integ)), key=lambda x: -abs(x[2]))
        total = float(np.sum(integ))
        explained = total / (v1 - v0) if v1 != v0 else 1.0
        out.append(Change(sv.symbol, sv.name, sv.unit, float(t[i0]), float(t[idx]), v0, v1, terms, explained))
    out.sort(key=lambda c: -abs(c.delta) / max(abs(c.v0), abs(c.v1), 1e-9))
    return out


def _integrate_terms(model, traj, i0: int, idx: int, p: dict) -> np.ndarray | None:
    """Integrate every flux term exactly over [t(i0), t(idx)] by re-solving the ODE with accumulators."""
    from scipy.integrate import solve_ivp
    y0 = np.asarray(traj.y[i0], dtype=float)
    n = len(y0)
    keys = [(ft.target, ft.name) for ft in model.flux_terms(y0, p)]   # some models omit terms that are zero
    index = {k: i for i, k in enumerate(keys)}

    def f(_t, z):
        y = np.maximum(z[:n], 0.0)
        acc = np.zeros(len(keys))
        for ft in model.flux_terms(y, p):
            i = index.get((ft.target, ft.name))
            if i is not None:
                acc[i] += ft.value
        return np.concatenate([model.rhs(_t, y, p), acc])
    sol = solve_ivp(f, (traj.t[i0], traj.t[idx]), np.concatenate([y0, np.zeros(len(keys))]), method="LSODA",
                    rtol=1e-8, atol=1e-10)
    if not sol.success:
        return None
    vals = dict(zip(keys, sol.y[n:, -1]))
    return np.array([vals.get((ft.target, ft.name), 0.0) for ft in model.flux_terms(y0, p)])


def evidence_summary(model) -> dict[str, int]:
    counts: dict[str, int] = {}
    for prm in model.default_parameters().params.values():
        if prm.evidence == Evidence.CONTROL:
            continue
        counts[prm.evidence.value] = counts.get(prm.evidence.value, 0) + 1
    return counts


def to_html(model, traj, idx: int, sens=None, max_items: int = 4) -> str:
    ch = significant_changes(model, traj, idx)
    ar = is_ar()
    unit = getattr(model, "time_unit", "d")
    e = html.escape
    parts = [f"<div dir='{'rtl' if ar else 'ltr'}'><h3>" + L("What changed, and why", "ماذا تغيّر ولماذا") + "</h3>"]
    if not ch:
        parts.append("<p>" + L("No state variable changed by more than 10% in the last part of the run up to this "
                               "moment.", "لم يتغير أي متغير بأكثر من 10٪ في الفترة الأخيرة حتى هذه اللحظة.") + "</p></div>")
        return "".join(parts)
    for c in ch[:max_items]:
        up = c.delta > 0
        name = e(c.name)
        parts.append(f"<p><b>{name}</b> " +
                     L(f"{'rose' if up else 'fell'} from {c.v0:.3g} to {c.v1:.3g} {e(c.unit)} between t = {c.t0:.3g} "
                       f"and {c.t1:.3g} {unit}.",
                       f"{'ارتفع' if up else 'انخفض'} من {c.v0:.3g} إلى {c.v1:.3g} {e(c.unit)} بين t = {c.t0:.3g} "
                       f"و {c.t1:.3g}.") + "</p><ul>")
        for n, f, v in c.terms[:4]:
            share = abs(v) / max(sum(abs(x[2]) for x in c.terms), 1e-12)
            parts.append(f"<li>{e(n)} <span style='color:#8b949e'>({e(f)})</span>: {v:+.3g} {e(c.unit)} "
                         f"({share:.0%})</li>")
        parts.append("</ul>")
        ok = abs(c.explained - 1) < 0.1
        parts.append("<p style='color:#8b949e'>" + L(
            f"These terms account for {c.explained:.0%} of the actual change"
            + ("." if ok else " (the rest comes from the stochastic noise, clipping at zero or the coarse time step)."),
            f"هذه الحدود تفسر {c.explained:.0%} من التغير الفعلي"
            + ("." if ok else " (الباقي من الضوضاء العشوائية أو القص عند الصفر أو خطوة الزمن).")) + "</p>")
        m = MEASURE.get(c.symbol) or (ORGANISM_MEASURE if c.symbol.startswith(("X", "org")) or c.unit == "mg/L" else None)
        if m:
            parts.append("<p>🔬 " + L("To test it, measure: ", "لاختباره، قِس: ") + e(m[1] if ar else m[0]) + "</p>")
    ev = evidence_summary(model)
    ev_txt = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in sorted(ev.items()))
    parts.append("<p><b>" + L("Assumptions & uncertainty", "الافتراضات وعدم اليقين") + ":</b> " +
                 L(f"the parameters behind these terms are {ev_txt}; none is calibrated to your data.",
                   f"المعاملات وراء هذه الحدود: {ev_txt}؛ ولا شيء منها معاير على بياناتك.") + " ")
    if sens:
        top = sorted(sens, key=lambda s: -abs(s.value))[:3]
        parts.append(L("Most influential (sensitivity): ", "الأكثر تأثيراً (الحساسية): ") +
                     ", ".join(f"{e(s.symbol)} ({s.value:+.2f})" for s in top) + ".")
    else:
        parts.append(L("Run “Sensitivity” to see which parameters this result depends on most.",
                       "شغّل «الحساسية» لترى أكثر المعاملات تأثيراً على هذه النتيجة."))
    parts.append("</p></div>")
    return "".join(parts)
