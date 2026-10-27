"""Repeated stochastic runs: how often does chance change the outcome?

Each replicate is the same configuration with a different seed (seed, seed+1, …), so the whole set is
reproducible. Summaries:
* probability that a variable goes extinct (reaches exactly 0) before the end, with a Wilson 95 % interval;
* time to extinction (median and range) among the replicates where it happened;
* mean and 5–95 % envelope of each state variable over time.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from ..core.scheduler import run
from ..core.trajectory import RunConfig


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (well behaved at 0 and n)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


@dataclass
class ReplicateSummary:
    n: int
    t: np.ndarray
    mean: np.ndarray            # (len(t), n_vars)
    lo: np.ndarray              # 5th percentile
    hi: np.ndarray              # 95th percentile
    symbols: tuple[str, ...]
    extinct: dict[str, int]
    extinct_ci: dict[str, tuple[float, float]]
    t_extinct: dict[str, list[float]]
    seeds: tuple[int, ...]


def run_replicates(model, cfg: RunConfig, n: int = 30, progress=None) -> ReplicateSummary:
    if cfg.mode != "stochastic":
        cfg = replace(cfg, mode="stochastic")
    seeds = tuple(cfg.seed + i for i in range(n))
    runs = []
    for i, s in enumerate(seeds):
        runs.append(run(model, replace(cfg, seed=s)))
        if progress:
            progress(i + 1, n)
    t = runs[0].t
    Y = np.stack([r.y for r in runs])                     # (n, len(t), n_vars)
    symbols = runs[0].state_symbols
    quanta = model.state_quanta({**cfg.parameters, "_volume_ml": cfg.volume_ml})
    if quanta is None:
        quanta = np.ones(len(symbols))
    extinct, t_ext = {}, {}
    for j, sym in enumerate(symbols):
        if quanta[j] <= 0:                                # dissolved pools cannot go "extinct"
            continue
        times = []
        for r in runs:
            zero = np.nonzero(r.y[:, j] <= 0)[0]
            if len(zero) and r.y[0, j] > 0:
                times.append(float(r.t[zero[0]]))
        extinct[sym] = len(times)
        t_ext[sym] = times
    return ReplicateSummary(n, t, Y.mean(0), np.percentile(Y, 5, axis=0), np.percentile(Y, 95, axis=0), symbols,
                            extinct, {k: wilson(v, n) for k, v in extinct.items()}, t_ext, seeds)


def describe(s: ReplicateSummary, names: dict[str, str], unit: str, ar: bool = False) -> list[str]:
    out = []
    for sym, k in s.extinct.items():
        lo, hi = s.extinct_ci[sym]
        nm = names.get(sym, sym)
        if ar:
            line = f"{nm}: انقرض في {k} من {s.n} تكرار — الاحتمال {k / s.n:.0%} (مجال الثقة 95٪: {lo:.0%}–{hi:.0%})."
        else:
            line = f"{nm}: extinct in {k} of {s.n} replicates — probability {k / s.n:.0%} (95% CI {lo:.0%}–{hi:.0%})."
        if s.t_extinct[sym]:
            ts = np.array(s.t_extinct[sym])
            line += (f" الزمن الوسيط للانقراض {np.median(ts):.3g} {unit} (المدى {ts.min():.3g}–{ts.max():.3g})."
                     if ar else
                     f" Median time to extinction {np.median(ts):.3g} {unit} (range {ts.min():.3g}–{ts.max():.3g}).")
        out.append(line)
    out.append(f"البذور العشوائية {s.seeds[0]}–{s.seeds[-1]}؛ إعادة التشغيل بنفس البذور تعطي نفس النتائج."
               if ar else
               f"Seeds {s.seeds[0]}–{s.seeds[-1]}; re-running with the same seeds gives identical results.")
    return out
