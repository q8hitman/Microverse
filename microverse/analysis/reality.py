"""Prediction vs Reality: compare laboratory measurements with a FROZEN prediction.

Workflow
1. A prediction was frozen earlier (data/microverse.sqlite, table `predictions`, append-only).
2. `load_prediction` finds its configuration, checks the record hash and the configuration hash, and
   re-runs exactly that configuration (deterministic, or stochastic with the stored seed). The frozen
   record itself is never modified; if the code version differs from the one that froze it, we say so.
3. `read_table` reads a CSV of measurements; `ColumnMap` says which column is time (and its unit) and
   which columns are which measured variable (and their units). `validate` reports problems.
4. `compare` interpolates the prediction at the measurement times and computes error metrics;
   `explain` turns the residual pattern into a plain-language discussion (bilingual).
5. `save_report` writes an HTML + JSON report and appends the observations and the comparison to the
   database (new rows only; the prediction row is untouched).

No calibration happens here. Calibration (analysis/calibration.py) never changes a frozen prediction —
it creates a new one.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np

from ..core.trajectory import RunConfig, Trajectory

# ---------------------------------------------------------------- what can be measured, per model
TIME_UNITS = {"h": 1.0, "min": 1 / 60, "d": 24.0, "s": 1 / 3600}          # → hours


@dataclass(frozen=True)
class Observable:
    key: str
    label: str
    label_ar: str
    unit: str                                   # unit of `getter`
    getter: Callable[[Trajectory], np.ndarray]
    units: dict[str, float] = field(default_factory=dict)   # accepted unit → factor to convert INTO `unit`
    log: bool = False                           # compare on log10 scale (counts spanning decades)
    lo: float = -math.inf                       # physically possible range (for validation)
    hi: float = math.inf


def observables_for(model) -> list[Observable]:
    mid = model.id
    if mid == "chemostat_rotifer":
        cpu, rpu = model.algae_cells_per_ml_per_umolN, model.rotifers_per_ml_per_umolN
        return [
            Observable("algae_cells", "Chlorella cells", "خلايا الكلوريلا", "cells/mL",
                       lambda t: t.series("C") * cpu, {"cells/mL": 1, "cells/µL": 1e3, "10^6 cells/mL": 1e6},
                       log=True, lo=0),
            Observable("rotifers", "Brachionus (females)", "الدوّارات (الإناث)", "ind/mL",
                       lambda t: t.series("B") * rpu, {"ind/mL": 1, "ind/L": 1e-3}, log=True, lo=0),
            Observable("C", "Algal biomass (as N)", "كتلة الطحالب (نيتروجين)", "µmol N/L",
                       lambda t: t.series("C"), {"µmol N/L": 1, "umol N/L": 1}, lo=0),
            Observable("N", "Dissolved nitrogen", "النيتروجين الذائب", "µmol N/L",
                       lambda t: t.series("N"), {"µmol N/L": 1, "umol N/L": 1, "mg N/L": 1000 / 14.007}, lo=0),
        ]
    if mid == "yogurt":
        return [
            Observable("pH", "pH of the milk", "حموضة الحليب", "pH", lambda t: model.ph_series(t), {"pH": 1},
                       lo=0, hi=14),
            Observable("st_cfu", "S. thermophilus", "ستربتوكوكس ثيرموفيلس", "CFU/mL",
                       lambda t: t.series("XS") * 1e8, {"CFU/mL": 1, "log10 CFU/mL": "log10"}, log=True, lo=0),
            Observable("lb_cfu", "L. bulgaricus", "لاكتوباسيلس بلغاريكس", "CFU/mL",
                       lambda t: t.series("XL") * 1e8, {"CFU/mL": 1, "log10 CFU/mL": "log10"}, log=True, lo=0),
            Observable("lactic", "Lactic acid", "حمض اللاكتيك", "g/L", lambda t: t.series("A"),
                       {"g/L": 1, "mg/L": 1e-3, "% (w/v)": 10}, lo=0),
            Observable("lactose", "Lactose", "اللاكتوز", "g/L", lambda t: t.series("Lac"),
                       {"g/L": 1, "mg/L": 1e-3, "% (w/v)": 10}, lo=0),
        ]
    if mid.startswith("community"):
        from ..models.community import NP, PI, water_ph
        out = []
        for i, o in enumerate(model.orgs):
            out.append(Observable(f"bio_{o.key}", o.name, o.name_ar, "mg/L",
                                  (lambda t, j=NP + i: t.y[:, j]), {"mg/L": 1, "g/L": 1000}, lo=0))

        def ph(t):
            p = t.config.parameters
            return np.array([water_ph(r[PI["lac"]], r[PI["ace"]], p["buffer"], p["ph_base"]) for r in t.y])

        out.append(Observable("pH", "pH", "الحموضة", "pH", ph, {"pH": 1}, lo=0, hi=14))
        out.append(Observable("o2", "Dissolved oxygen", "الأكسجين الذائب", "mg/L", lambda t: t.y[:, PI["o2"]],
                              {"mg/L": 1}, lo=0))
        for pool, lab, lab_ar in (("sug", "Sugars", "السكريات"), ("lac", "Lactate", "اللاكتات"),
                                  ("ace", "Acetate", "الأسيتات"), ("eth", "Ethanol", "الإيثانول")):
            out.append(Observable(pool, lab, lab_ar, "mg/L", (lambda t, j=PI[pool]: t.y[:, j]),
                                  {"mg/L": 1, "g/L": 1000}, lo=0))
        return out
    return []


def model_time_unit(model) -> str:
    return getattr(model, "time_unit", "d")


# ---------------------------------------------------------------- reading measurements
@dataclass
class Table:
    columns: list[str]
    rows: list[list[str]]
    source: str = ""
    sha256: str = ""

    def column(self, name: str) -> list[str]:
        j = self.columns.index(name)
        return [r[j] if j < len(r) else "" for r in self.rows]


def read_table(path_or_text: str | Path, text: bool = False) -> Table:
    """Read a CSV/TSV/semicolon file (UTF-8 with or without BOM; Excel-friendly). Lines starting with # are notes."""
    if text:
        raw = str(path_or_text).encode("utf-8")
        source = "<text>"
    else:
        raw = Path(path_or_text).read_bytes()
        source = str(path_or_text)
    sha = hashlib.sha256(raw).hexdigest()
    content = raw.decode("utf-8-sig", errors="replace")
    lines = [ln for ln in content.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise ValueError("The file is empty.")
    sample = "\n".join(lines[:10])
    delim = max([",", ";", "\t"], key=sample.count)
    rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))
    header = [h.strip() for h in rows[0]]
    if len(set(header)) != len(header):
        raise ValueError("Two columns have the same name.")
    return Table(header, [[c.strip() for c in r] for r in rows[1:]], source, sha)


def parse_number(s: str, decimal_comma: bool = False) -> float | None:
    s = s.strip().replace("−", "-")
    if not s or s.lower() in ("na", "nan", "n/a", "-", "nd"):
        return None
    if decimal_comma:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_time(values: list[str], unit: str) -> tuple[np.ndarray, list[str]]:
    """Times → hours since the first measurement. `unit` is h/min/d/s or 'datetime' (ISO 8601)."""
    problems = []
    out = []
    if unit == "datetime":
        stamps = []
        for i, v in enumerate(values):
            try:
                stamps.append(datetime.fromisoformat(v.replace("Z", "+00:00")))
            except ValueError:
                problems.append(f"row {i + 2}: '{v}' is not an ISO date-time (e.g. 2026-10-27 14:30)")
                stamps.append(None)
        t0 = next((s for s in stamps if s is not None), None)
        out = [((s - t0).total_seconds() / 3600 if s is not None and t0 is not None else np.nan) for s in stamps]
    else:
        f = TIME_UNITS[unit]
        for i, v in enumerate(values):
            x = parse_number(v) if v else None
            if x is None:
                x = parse_number(v, decimal_comma=True)
            if x is None:
                problems.append(f"row {i + 2}: time '{v}' is not a number")
                out.append(np.nan)
            else:
                out.append(x * f)
    return np.array(out, dtype=float), problems


@dataclass
class ColumnMap:
    time_column: str
    time_unit: str                                  # h / min / d / s / datetime
    variables: dict[str, tuple[str, str]]           # csv column → (observable key, unit as written in the file)
    time_offset_h: float = 0.0                      # measurement t=0 relative to the simulation's t=0


@dataclass
class ObservedSeries:
    key: str
    column: str
    unit: str
    t_model: np.ndarray                             # in the model's time unit
    values: np.ndarray                              # converted into the observable's unit


def validate(table: Table, cmap: ColumnMap, obs: list[Observable], model) -> tuple[list[ObservedSeries], list[str], list[str]]:
    """Returns (series, errors, warnings). Errors stop the comparison; warnings are shown."""
    errors, warnings = [], []
    if cmap.time_column not in table.columns:
        return [], [f"Time column '{cmap.time_column}' not found."], []
    if cmap.time_unit not in TIME_UNITS and cmap.time_unit != "datetime":
        return [], [f"Unknown time unit '{cmap.time_unit}'."], []
    t_h, probs = parse_time(table.column(cmap.time_column), cmap.time_unit)
    errors += probs
    t_h = t_h + cmap.time_offset_h
    ok_t = ~np.isnan(t_h)
    if ok_t.sum() >= 2 and np.any(np.diff(t_h[ok_t]) < 0):
        warnings.append("Times are not in increasing order; rows were sorted by time.")
    if np.any(t_h[ok_t] < 0):
        errors.append("Some times are negative after the offset.")
    unit_model = model_time_unit(model)
    t_model = t_h / TIME_UNITS[unit_model] if unit_model in TIME_UNITS else t_h
    by_key = {o.key: o for o in obs}
    series = []
    if not cmap.variables:
        errors.append("Choose at least one measured column.")
    for col, (key, unit) in cmap.variables.items():
        if col not in table.columns:
            errors.append(f"Column '{col}' not found.")
            continue
        o = by_key.get(key)
        if o is None:
            errors.append(f"'{key}' is not a variable of this model.")
            continue
        if unit not in o.units:
            errors.append(f"{col}: unit '{unit}' is not accepted for {o.label} (use one of: {', '.join(o.units)}).")
            continue
        conv = o.units[unit]
        vals = []
        for i, v in enumerate(table.column(col)):
            x = parse_number(v)
            if x is None and v:
                x = parse_number(v, decimal_comma=True)
            if x is not None:
                x = 10 ** x if conv == "log10" else x * conv
            vals.append(np.nan if x is None else x)
        vals = np.array(vals, dtype=float)
        good = ok_t & ~np.isnan(vals)
        missing = int((~np.isnan(t_h) & np.isnan(vals)).sum())
        if missing:
            warnings.append(f"{col}: {missing} empty or non-numeric value(s) were skipped.")
        bad_range = good & ((vals < o.lo) | (vals > o.hi))
        if bad_range.any():
            errors.append(f"{col}: {int(bad_range.sum())} value(s) outside the possible range for {o.label} "
                          f"({o.lo:g} … {o.hi:g} {o.unit}).")
        if good.sum() < 2:
            errors.append(f"{col}: fewer than 2 usable measurements.")
            continue
        order = np.argsort(t_model[good], kind="stable")
        series.append(ObservedSeries(key, col, unit, t_model[good][order], vals[good][order]))
    return series, errors, warnings


# ---------------------------------------------------------------- comparison
@dataclass
class Metrics:
    key: str
    n: int
    scale: str                                      # "linear" or "log10"
    rmse: float
    mae: float
    bias: float                                     # mean(predicted − observed), on `scale`
    nrmse: float                                    # rmse / range of observations
    r2: float | None
    max_abs: float
    shift: float                                    # best time shift of the prediction (model time units; + = model late)
    rmse_shifted: float
    outside: int                                    # measurements beyond the simulated time span
    end_error: float                                # last point: predicted − observed (on `scale`)


def predicted_at(traj: Trajectory, o: Observable, t: np.ndarray) -> np.ndarray:
    return np.interp(t, traj.t, o.getter(traj))


def compare(traj: Trajectory, o: Observable, s: ObservedSeries) -> tuple[Metrics, np.ndarray]:
    inside = (s.t_model >= traj.t[0]) & (s.t_model <= traj.t[-1])
    t, obs = s.t_model[inside], s.values[inside]
    pred = predicted_at(traj, o, t)
    if o.log:
        f = lambda x: np.log10(np.maximum(x, 1e-12))
        scale = "log10"
    else:
        f = lambda x: x
        scale = "linear"
    po, oo = f(pred), f(obs)
    res = po - oo
    n = len(res)
    if n == 0:
        nan = float("nan")
        return Metrics(o.key, 0, scale, nan, nan, nan, nan, None, nan, 0.0, nan, int((~inside).sum()), nan), pred
    rmse = float(np.sqrt(np.mean(res ** 2)))
    rng = float(np.ptp(oo)) or float(abs(np.mean(oo))) or 1.0
    ss_tot = float(np.sum((oo - oo.mean()) ** 2))
    r2 = 1 - float(np.sum(res ** 2)) / ss_tot if (n >= 3 and ss_tot > 0) else None
    # timing: would the prediction fit better if it happened earlier or later?
    span = traj.t[-1] - traj.t[0]
    best_shift, best = 0.0, rmse
    for sh in np.linspace(-0.25 * span, 0.25 * span, 101):
        tt = t - sh
        ok = (tt >= traj.t[0]) & (tt <= traj.t[-1])
        if ok.sum() < max(2, n // 2):
            continue
        r = f(np.interp(tt[ok], traj.t, o.getter(traj))) - oo[ok]
        val = float(np.sqrt(np.mean(r ** 2)))
        if val < best - 1e-12:
            best, best_shift = val, float(sh)
    return Metrics(o.key, n, scale, rmse, float(np.mean(np.abs(res))), float(np.mean(res)), rmse / rng, r2,
                   float(np.max(np.abs(res))), -best_shift, best, int((~inside).sum()), float(res[-1])), pred


def explain(m: Metrics, o: Observable, unit_time: str, ar: bool = False) -> list[str]:
    """Plain-language reading of the residual pattern. Derived only from the numbers in `m`."""
    out = []
    u = "" if m.scale == "linear" else " (log10 units)"
    u_ar = "" if m.scale == "linear" else " (بوحدات لوغاريتمية)"
    name = o.label_ar if ar else o.label
    if m.n == 0:
        return ["لا توجد قياسات داخل فترة المحاكاة." if ar else "No measurement falls inside the simulated time span."]
    good = m.nrmse < 0.1
    fair = m.nrmse < 0.25
    if ar:
        out.append(f"{name}: {m.n} قياس، الخطأ الجذري التربيعي {m.rmse:.3g}{u_ar} "
                   f"({m.nrmse * 100:.0f}% من مدى القياسات) — " +
                   ("تطابق جيد." if good else "تطابق مقبول." if fair else "اختلاف واضح بين التوقع والواقع."))
    else:
        out.append(f"{name}: {m.n} measurements, RMSE {m.rmse:.3g}{u} ({m.nrmse * 100:.0f}% of the observed range) — " +
                   ("good agreement." if good else "fair agreement." if fair else "a clear mismatch."))
    if abs(m.bias) > 0.5 * m.rmse and not good:
        hi = m.bias > 0
        out.append(("التوقع أعلى من القياسات بشكل منتظم" if hi else "التوقع أقل من القياسات بشكل منتظم") +
                   f" (متوسط الفرق {m.bias:+.3g}). قد يكون معامل عائد أو معدل نمو أو قيمة ابتدائية غير صحيح."
                   if ar else
                   ("The model is systematically HIGHER than the measurements" if hi else
                    "The model is systematically LOWER than the measurements") +
                   f" (mean difference {m.bias:+.3g}). A yield, growth rate or starting value may be off.")
    if m.rmse > 0 and m.rmse_shifted < 0.6 * m.rmse and abs(m.shift) > 0:
        late = m.shift > 0
        if ar:
            out.append(f"التوقيت: النموذج {'متأخر' if late else 'متقدم'} بحوالي {abs(m.shift):.2g} "
                       f"{'يوم' if unit_time == 'd' else 'ساعة'}؛ لو أزيح زمنياً لانخفض الخطأ إلى {m.rmse_shifted:.3g}. "
                       "هذا يشير غالباً إلى طور تأخر (lag) أو معدل نمو أو درجة حرارة غير صحيحة، وليس إلى خطأ في الشكل.")
        else:
            out.append(f"Timing: the model is {'LATE' if late else 'EARLY'} by about {abs(m.shift):.2g} {unit_time}; "
                       f"shifted, the error would fall to {m.rmse_shifted:.3g}. This usually points to the lag phase, "
                       "a growth rate or the temperature, not to the shape of the curve.")
    if m.outside:
        out.append(f"{m.outside} قياس خارج فترة المحاكاة ولم يُحسب. مدّد زمن المحاكاة." if ar else
                   f"{m.outside} measurement(s) lie outside the simulated time span and were not used. "
                   "Extend the simulation time.")
    if m.n < 5:
        out.append("عدد القياسات قليل؛ الأرقام غير مستقرة." if ar else
                   "Few measurements: these numbers are not robust.")
    return out


# ---------------------------------------------------------------- frozen predictions
@dataclass
class FrozenPrediction:
    id: int
    created: str
    hypothesis: str
    summary: dict
    config: RunConfig
    record_ok: bool
    config_ok: bool
    version_note: str


def list_predictions(con) -> list[dict]:
    rows = con.execute("SELECT p.id, p.created, p.hypothesis, p.summary_json, p.config_hash, e.config_json "
                       "FROM predictions p LEFT JOIN experiments e ON e.id = p.experiment_id ORDER BY p.id DESC"
                       ).fetchall()
    out = []
    for r in rows:
        s = json.loads(r["summary_json"])
        out.append({"id": r["id"], "created": r["created"], "hypothesis": r["hypothesis"] or "",
                    "lab": s.get("lab", "?"), "scenario": s.get("scenario", "?"), "outcome": s.get("outcome", ""),
                    "has_config": r["config_json"] is not None})
    return out


def load_prediction(con, pid: int) -> FrozenPrediction:
    from ..data.db import verify_prediction
    r = con.execute("SELECT p.*, e.config_json FROM predictions p LEFT JOIN experiments e ON e.id = p.experiment_id "
                    "WHERE p.id=?", (pid,)).fetchone()
    if r is None:
        raise KeyError(f"No prediction #{pid}.")
    if r["config_json"] is None:
        raise ValueError(f"Prediction #{pid} has no stored configuration, so it cannot be re-simulated.")
    cfg = RunConfig.from_dict(json.loads(r["config_json"]))
    summary = json.loads(r["summary_json"])
    note = ""
    lab = lab_for_model_id(cfg.model_id)
    if cfg.model_version != lab.model.version:
        note = (f"Frozen with model version {cfg.model_version}; this program has {lab.model.version}. "
                "The re-simulation uses the current code and may differ from what was frozen.")
    return FrozenPrediction(pid, r["created"], r["hypothesis"] or "", summary, cfg, verify_prediction(con, pid),
                            cfg.hash() == r["config_hash"], note)


def lab_for_model_id(model_id: str):
    from ..labs import community_lab, fixed_labs
    if model_id.startswith("community:"):
        keys = tuple(model_id.split(":", 1)[1].split(","))
        return community_lab(keys, "custom")
    for lab in fixed_labs():
        if lab.model.id == model_id:
            return lab
    raise KeyError(f"No lab for model '{model_id}'.")


def resimulate(fp: FrozenPrediction):
    from ..core.scheduler import run
    lab = lab_for_model_id(fp.config.model_id)
    return lab, run(lab.model, fp.config)


# ---------------------------------------------------------------- reports
def save_report(con, fp: FrozenPrediction, table: Table, cmap: ColumnMap, results: list[tuple], out_dir: Path,
                lab, traj: Trajectory) -> Path:
    """results: list of (Observable, ObservedSeries, Metrics, predicted_at_obs). Writes HTML + JSON; appends rows."""
    from ..data.db import now
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = out_dir / f"comparison_P{fp.id}_{stamp}"
    unit_t = model_time_unit(lab.model)
    payload = {
        "prediction": {"id": fp.id, "created": fp.created, "hypothesis": fp.hypothesis, "record_hash_ok": fp.record_ok,
                       "config_hash_ok": fp.config_ok, "config_hash": fp.config.hash(), "version_note": fp.version_note,
                       "summary": fp.summary},
        "observations": {"file": table.source, "sha256": table.sha256, "time_column": cmap.time_column,
                         "time_unit": cmap.time_unit, "time_offset_h": cmap.time_offset_h,
                         "variables": {c: list(v) for c, v in cmap.variables.items()}},
        "metrics": [asdict(m) for _o, _s, m, _p in results],
        "explanation_en": {o.key: explain(m, o, unit_t) for o, _s, m, _p in results},
        "explanation_ar": {o.key: explain(m, o, unit_t, ar=True) for o, _s, m, _p in results},
        "created": now(),
        "status": "comparison of a frozen prediction with measurements; the prediction was not modified",
    }
    from .calibration import same_data_warning
    if same_data_warning(fp, table):
        payload["warning"] = same_data_warning(fp, table)
        payload["status"] += "; WARNING: these are the data the prediction was fitted to (a fit, not a test)"
    base.with_suffix(".json").write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    base.with_suffix(".html").write_text(_report_html(payload, results, traj, unit_t), encoding="utf-8")
    imported = now()
    for o, s, _m, _p in results:
        con.executemany("INSERT INTO observations(prediction_id,imported,variable,time_d,value,unit,method,source_file)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        [(fp.id, imported, o.key, float(t), float(v), o.unit, f"column {s.column} ({s.unit})",
                          f"{table.source} sha256={table.sha256[:16]}") for t, v in zip(s.t_model, s.values)])
    con.execute("INSERT INTO comparisons(prediction_id,created,observations_sha256,metrics_json,report_path)"
                " VALUES (?,?,?,?,?)", (fp.id, imported, table.sha256, json.dumps(payload["metrics"],
                                                                                   default=_json_default),
                                        str(base.with_suffix(".html"))))
    con.commit()
    return base.with_suffix(".html")


def _json_default(x):
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return str(x)


def _svg_plot(o: Observable, s: ObservedSeries, traj: Trajectory, unit_t: str, w=640, h=260) -> str:
    """A small self-contained SVG: predicted line, observed points (log axis for counts)."""
    tt = traj.t
    yp = o.getter(traj)
    f = (lambda v: np.log10(np.maximum(v, 1e-12))) if o.log else (lambda v: v)
    ys = np.concatenate([f(yp), f(s.values)])
    y0, y1 = float(np.nanmin(ys)), float(np.nanmax(ys))
    if y1 - y0 < 1e-12:
        y1 = y0 + 1
    x0, x1 = float(tt[0]), float(max(tt[-1], s.t_model.max()))
    m = 46
    X = lambda t: m + (t - x0) / (x1 - x0) * (w - m - 10)
    Y = lambda v: h - 30 - (v - y0) / (y1 - y0) * (h - 50)
    pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(tt, f(yp)))
    dots = "".join(f"<circle cx='{X(a):.1f}' cy='{Y(b):.1f}' r='4' fill='#d95926'/>" for a, b in zip(s.t_model, f(s.values)))
    lab_y = f"log10 {o.unit}" if o.log else o.unit
    return (f"<svg viewBox='0 0 {w} {h}' width='{w}' height='{h}' xmlns='http://www.w3.org/2000/svg' "
            f"font-family='Segoe UI,Arial' font-size='11'>"
            f"<rect width='{w}' height='{h}' fill='#fff'/>"
            f"<line x1='{m}' y1='{h - 30}' x2='{w - 10}' y2='{h - 30}' stroke='#888'/>"
            f"<line x1='{m}' y1='20' x2='{m}' y2='{h - 30}' stroke='#888'/>"
            f"<text x='{w / 2}' y='{h - 8}' text-anchor='middle'>time ({unit_t})</text>"
            f"<text x='12' y='{h / 2}' transform='rotate(-90 12 {h / 2})' text-anchor='middle'>{lab_y}</text>"
            f"<text x='{m - 4}' y='{Y(y1) + 4}' text-anchor='end'>{y1:.3g}</text>"
            f"<text x='{m - 4}' y='{Y(y0) + 4}' text-anchor='end'>{y0:.3g}</text>"
            f"<text x='{X(x1)}' y='{h - 16}' text-anchor='end'>{x1:.3g}</text>"
            f"<polyline points='{pts}' fill='none' stroke='#3987e5' stroke-width='2'/>{dots}"
            f"<text x='{w - 12}' y='16' text-anchor='end' fill='#3987e5'>— predicted (frozen)</text>"
            f"<text x='{w - 12}' y='30' text-anchor='end' fill='#d95926'>● measured</text></svg>")


def _report_html(payload, results, traj, unit_t) -> str:
    import html as H
    p = payload["prediction"]
    rows = []
    for o, s, m, _pred in results:
        r2 = "–" if m.r2 is None else f"{m.r2:.3f}"
        rows.append(f"<tr><td>{H.escape(o.label)}</td><td>{m.n}</td><td>{m.scale}</td><td>{m.rmse:.4g}</td>"
                    f"<td>{m.mae:.4g}</td><td>{m.bias:+.4g}</td><td>{m.nrmse * 100:.1f}%</td><td>{r2}</td>"
                    f"<td>{m.shift:+.3g} {unit_t}</td></tr>")
    sections = []
    for o, s, m, _pred in results:
        en = "".join(f"<li>{H.escape(x)}</li>" for x in payload["explanation_en"][o.key])
        ar = "".join(f"<li>{H.escape(x)}</li>" for x in payload["explanation_ar"][o.key])
        sections.append(f"<h3>{H.escape(o.label)} — {H.escape(o.label_ar)}</h3>{_svg_plot(o, s, traj, unit_t)}"
                        f"<ul>{en}</ul><ul dir='rtl' lang='ar'>{ar}</ul>")
    ok = lambda b: "✔ verified" if b else "✘ FAILED"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Prediction vs Reality P{p['id']}</title>
<style>body{{font-family:'Segoe UI',Tahoma,Arial,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#1b1f24}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #d0d7de;padding:4px 6px;text-align:left}}
th{{background:#f3f6f9}}.note{{background:#fff8e1;border-left:4px solid #e3b341;padding:8px 12px}}</style></head><body>
<h1>Prediction vs Reality — prediction #{p['id']}</h1>
<p>Frozen {H.escape(p['created'])} UTC · hypothesis: <b>{H.escape(p['hypothesis'] or '—')}</b><br>
Lab: {H.escape(str(p['summary'].get('lab')))} · scenario: {H.escape(str(p['summary'].get('scenario')))} ·
frozen outcome: {H.escape(str(p['summary'].get('outcome')))}</p>
<p>Record hash {ok(p['record_hash_ok'])} · configuration hash {ok(p['config_hash_ok'])} ·
measurements file SHA-256 <code>{payload['observations']['sha256'][:16]}…</code></p>
{f"<p class='note'>{H.escape(p['version_note'])}</p>" if p['version_note'] else ''}
{f"<p class='note'><b>{H.escape(payload['warning'])}</b></p>" if payload.get('warning') else ''}
<p class="note">The frozen prediction was re-simulated from its stored configuration and was <b>not modified</b>.
Agreement with one data set is evidence, not proof; a model calibrated on these data must be tested on other data.</p>
<table><tr><th>Variable</th><th>n</th><th>scale</th><th>RMSE</th><th>MAE</th><th>bias (pred−obs)</th><th>NRMSE</th>
<th>R²</th><th>best time shift</th></tr>{''.join(rows)}</table>
{''.join(sections)}
<p style="color:#57606a;font-size:12px">Generated by MicroVerse · {H.escape(payload['created'])}</p></body></html>"""
