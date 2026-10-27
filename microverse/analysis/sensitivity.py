"""Local sensitivity: elasticities of an output metric to each parameter."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import numpy as np

from ..core.model import Model
from ..core.scheduler import run
from ..core.trajectory import RunConfig, Trajectory


@dataclass
class Elasticity:
    symbol: str
    value: float          # (ΔO/O)/(Δp/p)


def long_run_mean(model: Model, cfg: RunConfig, symbol: str, tail: float = 0.4) -> float:
    s = run(model, cfg).series(symbol)
    return float(np.mean(s[int(len(s) * (1 - tail)):]))


def elasticities(model: Model, cfg: RunConfig, metric: str | Callable[[Trajectory], float] = "B",
                 rel_step: float = 0.05, rebuild: Callable[[RunConfig], RunConfig] | None = None) -> list[Elasticity]:
    """Central-difference elasticities from deterministic runs.

    `metric` is a state symbol (long-run mean) or a function of the trajectory.
    `rebuild` lets a lab recompute dependent fields (e.g. initial state from inoculum parameters).
    """
    cfg = replace(cfg, mode="deterministic")
    fn = metric if callable(metric) else (lambda tr, s=metric: float(np.mean(tr.series(s)[int(len(tr.t) * 0.6):])))
    rebuild = rebuild or (lambda c: c)
    bounds = model.default_parameters().params
    base = fn(run(model, rebuild(cfg)))
    out = []
    if not np.isfinite(base) or base == 0:
        return out
    for k, v in cfg.parameters.items():
        if v == 0:
            continue
        lo, hi = v * (1 - rel_step), v * (1 + rel_step)
        if lo < bounds[k].lower or hi > bounds[k].upper:
            continue
        o_hi = fn(run(model, rebuild(replace(cfg, parameters={**cfg.parameters, k: hi}))))
        o_lo = fn(run(model, rebuild(replace(cfg, parameters={**cfg.parameters, k: lo}))))
        if not (np.isfinite(o_hi) and np.isfinite(o_lo)):
            continue
        out.append(Elasticity(k, ((o_hi - o_lo) / base) / (2 * rel_step)))
    return sorted(out, key=lambda e: -abs(e.value))
