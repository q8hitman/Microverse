"""Regime scan over the dilution rate (the experiment of Fussmann et al. 2000)."""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from ..core.scheduler import run
from ..core.trajectory import RunConfig
from ..models.chemostat_rotifer import ChemostatRotifer
from .stability import classify


@dataclass
class ScanPoint:
    delta: float
    regime: str
    c_min: float
    c_max: float
    b_min: float
    b_max: float


def scan_dilution(model: ChemostatRotifer, cfg: RunConfig, deltas, t_end: float = 800.0,
                  tail_days: float = 300.0, progress=None) -> list[ScanPoint]:
    pts = []
    for i, d in enumerate(deltas):
        c = replace(cfg, mode="deterministic", t_end=t_end, dt_out=0.25,
                    parameters={**cfg.parameters, "delta": float(d)})
        traj = run(model, c)
        k = traj.index_at(t_end - tail_days)
        cs, bs = traj.series("C")[k:], traj.series("B")[k:]
        pts.append(ScanPoint(float(d), classify(model, c.parameters).key,
                             float(cs.min()), float(cs.max()), float(bs.min()), float(bs.max())))
        if progress:
            progress(i + 1, len(deltas))
    return pts


def oscillation_period(t: np.ndarray, x: np.ndarray, tail: float = 0.5) -> float | None:
    """Mean spacing of local maxima in the tail of a series (None if no sustained peaks)."""
    k = int(len(x) * (1 - tail))
    t, x = t[k:], x[k:]
    if len(x) < 5 or np.ptp(x) < 1e-3 * max(1e-12, np.mean(x)):
        return None
    peaks = np.where((x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:]) & (x[1:-1] > np.mean(x)))[0] + 1
    if len(peaks) < 3:
        return None
    return float(np.mean(np.diff(t[peaks])))
