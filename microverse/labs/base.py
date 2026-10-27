"""A Lab packages one model with its organisms, scenarios, plots, explanation and scan."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable

import numpy as np

from ..core.model import Model
from ..core.scheduler import make_config
from ..core.trajectory import RunConfig, Trajectory


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    title_ar: str
    question: str                     # the research question this scenario explores
    overrides: dict[str, float] = field(default_factory=dict)
    mode: str = "deterministic"
    t_end: float | None = None
    volume_ml: float = 50.0
    seed: int = 1


@dataclass(frozen=True)
class Series:
    label: str
    getter: Callable[[Trajectory], np.ndarray]
    colour: str
    dashed: bool = False


@dataclass(frozen=True)
class PlotPanel:
    title: str
    y_label: str
    series: tuple[Series, ...]
    log_y: bool = False
    ref_lines: tuple[tuple[float, str], ...] = ()      # horizontal reference lines (value, label)


@dataclass
class Lab:
    key: str
    title: str
    title_ar: str
    tagline: str
    tagline_ar: str
    description: str
    status: str                       # honest scientific status line
    status_colour: str
    model: Model
    organisms: tuple[str, ...]
    scenarios: tuple[Scenario, ...]
    param_groups: tuple[tuple[str, tuple[str, ...]], ...]
    plots: tuple[PlotPanel, ...]
    default_t_end: float
    dt_out: float
    explain_html: Callable[[Trajectory, int, Any], str]
    outcome: Callable[[Trajectory], tuple[str, str]]          # (label, colour)
    summary: Callable[[Trajectory], dict]
    sensitivity_metric: Callable[[Trajectory], float] | str
    sensitivity_label: str
    make_scene: Callable[[int], Any]
    make_widget: Callable[[Any], Any]
    scan_title: str = ""
    scan_info: str = ""
    scan_compute: Callable | None = None          # (lab, cfg, progress) -> rows
    scan_plot: Callable | None = None             # (plot_widget, rows, cfg) -> x position of current value
    supports_stochastic: bool = False
    accent: str = "#58a6ff"
    initial_state: Callable[[dict], np.ndarray] | None = None

    @property
    def time_unit(self) -> str:
        return getattr(self.model, "time_unit", "d")

    def config(self, values: dict[str, float], *, mode="deterministic", seed=1, volume_ml=50.0,
               t_end: float | None = None) -> RunConfig:
        p = self.model.default_parameters().updated(**values).values()
        y0 = self.initial_state(p) if self.initial_state else None
        return make_config(self.model, t_end=t_end or self.default_t_end, dt_out=self.dt_out, mode=mode,
                           seed=seed, volume_ml=volume_ml, initial_state=y0, **values)

    def rebuild(self, cfg: RunConfig) -> RunConfig:
        """Recompute dependent fields (initial state) after parameters change, e.g. in sensitivity runs."""
        if not self.initial_state:
            return cfg
        return replace(cfg, initial_state=tuple(float(v) for v in self.initial_state(cfg.parameters)))
