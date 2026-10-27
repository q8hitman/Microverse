"""Calibration: fit chosen parameters to ONE measured data set and freeze the result as a NEW prediction.

Rules (see docs/VERIFICATION_VS_VALIDATION.md):
* The prediction we start from is never changed. Calibration re-simulates its stored configuration with some
  parameters replaced, and `freeze_calibrated` stores that as a new, separate prediction with its provenance
  (which prediction it came from, which file, by SHA-256, which parameters were fitted).
* Agreement with the data used for fitting is a fit, not a test. The fitted prediction must be compared with a
  DIFFERENT data set; `same_data_warning` flags a comparison that reuses the fitting file.
* Fitting is weighted least squares (SciPy `least_squares`, trust-region reflective, inside each parameter's
  allowed range). Each measured series counts equally: its residuals are divided by the spread of its own
  observations and by √n. Counts are fitted on a log10 scale, like the comparison metrics.
* Uncertainty comes from the Jacobian at the optimum (local, linearised). Strong correlations and parameters at
  their limits are reported as warnings because they mean the data cannot pin those parameters down.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace

import numpy as np
from scipy.optimize import least_squares

from ..core.scheduler import run
from ..core.trajectory import RunConfig, Trajectory
from . import reality as R

# Sensible first choices per model: the rates and yields that set timing and size. The user can change them.
SUGGESTED = {
    "yogurt": ("muS", "muL", "alpha"),
    "chemostat_rotifer": ("bC", "bB", "m"),
}
MAX_PARAMS = 5


def suggested_parameters(model) -> tuple[str, ...]:
    if model.id in SUGGESTED:
        return SUGGESTED[model.id]
    if model.id.startswith("community"):
        return tuple(k for k in model.default_parameters().params if k.startswith("mu_"))[:3]
    return ()


@dataclass
class FitParameter:
    symbol: str
    name: str
    unit: str
    start: float
    value: float
    lower: float
    upper: float
    ci_low: float | None             # approximate 95 % interval (linearised); None if not identifiable
    ci_high: float | None
    at_limit: bool


@dataclass
class CalibrationResult:
    success: bool
    message: str
    parameters: list[FitParameter]
    correlation: np.ndarray | None
    cost_start: float
    cost_end: float
    n_points: int
    n_evals: int
    config: RunConfig                 # the fitted configuration (not yet frozen)
    traj: Trajectory
    before: list[tuple]               # (Observable, ObservedSeries, Metrics) at the starting parameters
    after: list[tuple]                # same, at the fitted parameters
    warnings: list[str] = field(default_factory=list)
    warnings_ar: list[str] = field(default_factory=list)

    def fitted(self) -> dict[str, float]:
        return {p.symbol: p.value for p in self.parameters}


# ---------------------------------------------------------------- configuration with replaced parameters
def _derives_initial_state(model, cfg: RunConfig) -> bool:
    """True when the stored initial state is exactly what the model derives from the parameters (e.g. inoculum),
    so a fitted inoculum must also change the initial state."""
    f = getattr(model, "initial_state_from", None)
    if f is None:
        return False
    try:
        return bool(np.allclose(f(cfg.parameters), cfg.initial_state, rtol=1e-9, atol=1e-12))
    except (KeyError, TypeError):
        return False


def with_parameters(model, cfg: RunConfig, values: dict[str, float]) -> RunConfig:
    params = {**cfg.parameters, **{k: float(v) for k, v in values.items()}}
    y0 = cfg.initial_state
    if _derives_initial_state(model, cfg):
        y0 = tuple(float(v) for v in model.initial_state_from(params))
    return replace(cfg, parameters=params, initial_state=y0, mode="deterministic")


# ---------------------------------------------------------------- residuals
def _scale_fn(o: R.Observable):
    return (lambda x: np.log10(np.maximum(x, 1e-12))) if o.log else (lambda x: np.asarray(x, float))


def _prepare(traj: Trajectory, obs: list[R.Observable], series: list[R.ObservedSeries]):
    """Per series: (observable, times inside the span, observations on the fitting scale, weight)."""
    by_key = {o.key: o for o in obs}
    out = []
    for s in series:
        o = by_key[s.key]
        inside = (s.t_model >= traj.t[0]) & (s.t_model <= traj.t[-1])
        if inside.sum() < 2:
            continue
        f = _scale_fn(o)
        y = f(s.values[inside])
        spread = float(np.std(y)) or float(abs(np.mean(y))) * 0.1 or 1.0
        out.append((o, s.t_model[inside], y, 1.0 / (spread * math.sqrt(inside.sum()))))
    return out


def _residuals(model, cfg: RunConfig, prepared) -> np.ndarray:
    try:
        tr = run(model, cfg)
    except Exception:                                    # noqa: BLE001 — a failed solve is a very bad fit
        return np.concatenate([np.full(len(t), 1e3) for _o, t, _y, _w in prepared])
    parts = []
    for o, t, y, w in prepared:
        pred = _scale_fn(o)(np.interp(t, tr.t, o.getter(tr)))
        r = (pred - y) * w
        parts.append(np.where(np.isfinite(r), r, 1e3))
    return np.concatenate(parts)


def _metrics(traj, obs, series):
    by_key = {o.key: o for o in obs}
    return [(by_key[s.key], s, R.compare(traj, by_key[s.key], s)[0]) for s in series]


# ---------------------------------------------------------------- fitting
def calibrate(model, base_cfg: RunConfig, obs: list[R.Observable], series: list[R.ObservedSeries],
              symbols: list[str], max_evals: int = 300, progress=None) -> CalibrationResult:
    if not symbols:
        raise ValueError("Choose at least one parameter to fit.")
    if len(symbols) > MAX_PARAMS:
        raise ValueError(f"Fit at most {MAX_PARAMS} parameters at a time; more cannot be told apart reliably.")
    if base_cfg.mode != "deterministic":
        base_cfg = replace(base_cfg, mode="deterministic")
    meta = model.default_parameters().params
    unknown = [s for s in symbols if s not in meta]
    if unknown:
        raise ValueError(f"Unknown parameter(s): {', '.join(unknown)}")
    traj0 = run(model, base_cfg)
    prepared = _prepare(traj0, obs, series)
    n = sum(len(t) for _o, t, _y, _w in prepared)
    if n <= len(symbols) + 1:
        raise ValueError(f"{n} usable measurement(s) for {len(symbols)} parameter(s): there must be clearly more "
                         "measurements than fitted parameters.")

    # Work in log space for positive parameters (rates span decades), linear otherwise.
    start = np.array([base_cfg.parameters[s] for s in symbols], float)
    lo = np.array([meta[s].lower for s in symbols], float)
    hi = np.array([meta[s].upper for s in symbols], float)
    use_log = (lo > 0) & (start > 0)

    def to_z(v):
        return np.where(use_log, np.log(np.maximum(v, 1e-300)), v)

    def from_z(z):
        return np.where(use_log, np.exp(z), z)

    z_lo, z_hi = to_z(lo), to_z(hi)
    z0 = np.clip(to_z(np.clip(start, lo, hi)), z_lo + 1e-9, z_hi - 1e-9)
    calls = [0]

    def fun(z):
        calls[0] += 1
        if progress:
            progress(min(calls[0], max_evals), max_evals)
        v = from_z(z)
        return _residuals(model, with_parameters(model, base_cfg, dict(zip(symbols, v))), prepared)

    r0 = fun(z0)
    sol = least_squares(fun, z0, bounds=(z_lo, z_hi), method="trf", x_scale="jac", diff_step=1e-3,
                        max_nfev=max_evals)
    v = from_z(sol.x)
    cfg = with_parameters(model, base_cfg, dict(zip(symbols, v)))
    traj = run(model, cfg)

    # Linearised uncertainty: cov(z) = s² (JᵀJ)⁻¹, s² = RSS / (n − p).
    warnings, warnings_ar = [], []
    p = len(symbols)
    ci = [(None, None)] * p
    corr = None
    dof = max(n - p, 1)
    s2 = float(np.sum(sol.fun ** 2)) / dof
    J = sol.jac
    try:
        cov = np.linalg.inv(J.T @ J) * s2
        sd = np.sqrt(np.clip(np.diag(cov), 0, None))
        corr = cov / np.outer(sd, sd)
        ci = []
        for k in range(p):
            if not np.isfinite(sd[k]) or sd[k] == 0:
                ci.append((None, None))
                continue
            a, b = sol.x[k] - 1.96 * sd[k], sol.x[k] + 1.96 * sd[k]
            ci.append((float(from_z(np.array([a]))[0] if use_log[k] else a),
                       float(from_z(np.array([b]))[0] if use_log[k] else b)))
    except np.linalg.LinAlgError:
        warnings.append("The parameters cannot be estimated separately from these data (singular fit).")
        warnings_ar.append("لا يمكن تقدير المعاملات كلٌّ على حدة من هذه البيانات (مصفوفة منفردة).")

    params = []
    for k, s in enumerate(symbols):
        at = bool(sol.x[k] <= z_lo[k] + 1e-3 * max(1.0, abs(z_lo[k])) or
                  sol.x[k] >= z_hi[k] - 1e-3 * max(1.0, abs(z_hi[k])))
        params.append(FitParameter(s, meta[s].name, meta[s].unit, float(start[k]), float(v[k]), float(lo[k]),
                                   float(hi[k]), ci[k][0], ci[k][1], at))
        if at:
            warnings.append(f"{s} ended at the limit of its allowed range ({lo[k]:g}–{hi[k]:g} {meta[s].unit}). "
                            "The data push it to an implausible value, which usually means part of the model "
                            "structure, not this number, is wrong.")
            warnings_ar.append(f"{s} وصل إلى حدّ مجاله المسموح ({lo[k]:g}–{hi[k]:g} {meta[s].unit}). البيانات تدفعه "
                               "إلى قيمة غير معقولة، وهذا يعني غالباً أن جزءاً من بنية النموذج هو الخطأ وليس هذا الرقم.")
        lo_c, hi_c = ci[k]
        if lo_c is not None and v[k] > 0 and lo_c > 0 and hi_c / lo_c > 10:
            warnings.append(f"{s} is poorly determined: its 95 % interval spans more than a factor of 10.")
            warnings_ar.append(f"{s} غير محدد جيداً: مجال الثقة 95٪ له يمتد أكثر من عشرة أضعاف.")
    if corr is not None:
        for a in range(p):
            for b in range(a + 1, p):
                if abs(corr[a, b]) > 0.95:
                    warnings.append(f"{symbols[a]} and {symbols[b]} cannot be told apart with these data "
                                    f"(correlation {corr[a, b]:+.2f}); a different measurement is needed.")
                    warnings_ar.append(f"لا يمكن التمييز بين {symbols[a]} و{symbols[b]} بهذه البيانات "
                                       f"(ارتباط {corr[a, b]:+.2f})؛ يلزم قياس مختلف.")
    if not sol.success:
        warnings.append(f"The optimiser stopped early: {sol.message}")
        warnings_ar.append(f"توقف المُحسِّن مبكراً: {sol.message}")
    return CalibrationResult(bool(sol.success), str(sol.message), params, corr, float(0.5 * np.sum(r0 ** 2)),
                             float(sol.cost), n, int(calls[0]), cfg, traj, _metrics(traj0, obs, series),
                             _metrics(traj, obs, series), warnings, warnings_ar)


# ---------------------------------------------------------------- freezing the result as a NEW prediction
def freeze_calibrated(con, base: R.FrozenPrediction, res: CalibrationResult, table: R.Table, cmap: R.ColumnMap,
                      lab, hypothesis: str = "") -> int:
    """Store the fitted configuration as a new prediction, with full provenance. The base prediction is untouched."""
    from ..data import db
    model = lab.model
    fitted = {p.symbol: {"value": p.value, "start": p.start, "unit": p.unit,
                         "ci95": [p.ci_low, p.ci_high], "at_limit": p.at_limit} for p in res.parameters}
    calib = {"from_prediction": base.id, "file": table.source, "sha256": table.sha256,
             "variables": {c: list(v) for c, v in cmap.variables.items()}, "time_offset_h": cmap.time_offset_h,
             "fitted": fitted, "n_points": res.n_points, "cost_start": res.cost_start, "cost_end": res.cost_end}
    summary = {"lab": base.summary.get("lab", lab.key), "scenario": base.summary.get("scenario", "?"),
               "model": f"{model.id} v{model.version}", "mode": res.config.mode,
               "outcome": lab.outcome(res.traj)[0], **lab.summary(res.traj),
               "calibration": calib,
               "status": "calibrated prediction (fitted to one data set; test it on a DIFFERENT data set)"}
    db.seed_model(con, model)
    cur = con.execute("INSERT INTO model_versions(model_id,code_version,label,parent_id,created,calibration_data)"
                      " VALUES (?,?,?,?,?,?)",
                      (model.id, model.version, f"fitted to {table.source} (from prediction #{base.id})", None,
                       db.now(), json.dumps(calib, default=float)))
    mv = int(cur.lastrowid)
    for p in res.parameters:
        con.execute("INSERT INTO parameters(model_id,symbol,value,unit,evidence,verified_against_source,"
                    "model_version_id,note) VALUES (?,?,?,?,?,?,?,?)",
                    (model.id, p.symbol, p.value, p.unit, "fitted", 0, mv,
                     f"fitted to {table.source} sha256={table.sha256[:16]}"))
    exp_id = db.save_experiment(con, (hypothesis or f"calibrated from #{base.id}")[:60], res.config,
                                notes=f"calibrated from prediction #{base.id} on {table.source}")
    return db.freeze_prediction(con, res.config, summary,
                                hypothesis or f"Calibrated from prediction #{base.id} on {table.source}", exp_id)


def same_data_warning(fp: R.FrozenPrediction, table: R.Table, ar: bool = False) -> str | None:
    """A calibrated prediction compared with the very file it was fitted to is not a test."""
    cal = fp.summary.get("calibration") if isinstance(fp.summary, dict) else None
    if not cal or cal.get("sha256") != table.sha256:
        return None
    if ar:
        return ("هذه هي القياسات نفسها التي عُويِر عليها هذا التوقع، فالتطابق هنا ملاءمة وليس اختباراً. "
                "قارنه بمجموعة بيانات مختلفة.")
    return ("These are the same measurements this prediction was fitted to, so agreement here is a fit, not a test. "
            "Compare it with a different data set.")
