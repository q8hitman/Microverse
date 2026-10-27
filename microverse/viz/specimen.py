"""A microscope specimen: one or more fields of view, each holding persistent visual populations.

All three labs build their microscope view from this class, so they share one set of rules:

* the model state is read at the CURRENT simulation time with linear interpolation (smooth playback);
* each species has ONE dilution/concentration factor per run, chosen so its peak fits the field.
  Because the factor does not change during a run, the drawn number of cells is proportional to the
  modelled density at every moment (the old view re-chose the factor in 2× steps, which made cells
  jump in and out);
* populations change only through `VisualPopulation` transitions (division, lysis, grazing,
  leaving/entering view), never by teleporting new cells into the middle of the field;
* biology follows simulation time (constant while paused); swimming runs on real time (`motion_scale`).

Qt-free and deterministic for a given seed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..core.trajectory import Trajectory
from ..library.morphology import MorphSpec
from .population import ENTERING, Agent, VisualPopulation
from .field import Field

MODES = ("natural", "microscope", "explain")
MODE_LABELS = {
    "natural": ("Realistic", "واقعي"),
    "microscope": ("Microscope", "مجهري"),
    "explain": ("Explanation overlays", "طبقات الشرح"),
}


@dataclass
class Track:
    key: str
    label: str
    label_ar: str
    spec: MorphSpec
    panel: str
    raw: Callable[[np.ndarray], float]          # cells in one undiluted field, from the state vector
    cap: float                                  # most cells we are willing to draw for this species
    colour: str = "#9da7b3"
    predators: tuple[int, ...] = ()             # indices of tracks that eat this one (same panel)
    visitors: tuple[int, ...] = ()              # predators that live in ANOTHER (larger) field but eat this one
    concentration: float = 1.0
    pop: VisualPopulation | None = None
    target: float = 0.0

    def factor_text(self) -> str:
        c = self.concentration
        if c >= 1.5:
            return f"×{c:,.0f}"
        if c <= 0.67:
            return f"÷{1 / c:,.0f}"
        return "×1"


class Specimen:
    max_dt = 0.1                                # never integrate visual motion over more than 0.1 s

    def __init__(self, panels: dict[str, Field], tracks: list[Track], seed: int = 0):
        self.panels = panels
        self.tracks = tracks
        self.seed_value = seed
        for i, tr in enumerate(tracks):
            f = panels[tr.panel]
            tr.pop = VisualPopulation(tr.spec, f.width_um, f.height_um, seed=seed * 1000 + i,
                                      id_start=(i + 1) * 1_000_000)
        self.motion_scale = 1.0                 # 1 = real-time swimming speeds
        self.mode = "natural"
        self.t_sim = 0.0
        self.y = None
        self._traj_hash = None
        self._last_t = None
        self.selected: tuple[int, int] | None = None     # (track index, agent id) chosen for inspection
        # Grazers from the large field that pass through a small field. They are a VISUAL SUMMARY of grazing
        # (not counted, not part of any population): one swims across while the prey population is falling.
        self.visitors: dict[str, list[tuple[int, Agent, VisualPopulation]]] = {}
        import random as _random
        self._vrng = _random.Random(seed + 99)

    # ------------------------------------------------------------------ public API
    @property
    def panel_names(self) -> list[str]:
        seen = []
        for tr in self.tracks:
            if tr.panel not in seen:
                seen.append(tr.panel)
        return [p for p in self.panels if p in seen]

    def expected_counts(self, y) -> tuple[float, ...]:
        """Cells we aim to draw for each track at state y (raw × fixed concentration, capped)."""
        return tuple(min(max(tr.raw(y), 0.0) * tr.concentration, tr.cap) for tr in self.tracks)

    def drawn_counts(self) -> tuple[int, ...]:
        return tuple(tr.pop.cells() for tr in self.tracks)

    def sync(self, traj: Trajectory, idx: int, dt_real: float) -> None:
        """Backward-compatible entry point (index of an output row)."""
        self.update(traj, float(traj.t[idx]), dt_real)

    def update(self, traj: Trajectory, t_sim: float, dt_real: float) -> None:
        h = traj.config_hash
        if h != self._traj_hash:
            self._new_trajectory(traj, t_sim)
        y = traj.state_at(t_sim)
        advancing = self._last_t is not None and abs(t_sim - self._last_t) > 1e-12
        self._last_t = t_sim
        self.t_sim, self.y = t_sim, y
        dt = min(max(dt_real, 0.0), self.max_dt)
        targets = self.expected_counts(y)
        self._update_visitors(dt, targets)
        for i, tr in enumerate(self.tracks):
            tr.target = targets[i]
            preds = [a for j in tr.predators for a in self.tracks[j].pop.agents if a.counted]
            preds += [a for j, a, _pop in self.visitors.get(tr.panel, ()) if j in tr.visitors]
            tr.pop.step(tr.target, dt, advancing, self.motion_scale, preds)
        self.on_state(y, traj)

    def visitor_agents(self, panel: str) -> list[tuple[int, Agent]]:
        return [(j, a) for j, a, _p in self.visitors.get(panel, ())]

    def _update_visitors(self, dt: float, targets) -> None:
        for panel in self.panels:
            live = []
            for j, a, pop in self.visitors.get(panel, ()):
                pop._move(dt * self.motion_scale * 0.25, [])        # slowed: a 300 µm/s cell crosses 75 µm
                a.progress += dt
                inside = -a_len(pop) <= a.x <= pop.w + a_len(pop) and -a_len(pop) <= a.y <= pop.h + a_len(pop)
                if a.progress < 1.5 or inside:
                    live.append((j, a, pop))
            self.visitors[panel] = live
        for i, tr in enumerate(self.tracks):
            if not tr.visitors or self.visitors.get(tr.panel):
                continue
            falling = tr.pop.cells() > targets[i] + 0.75 and tr.pop.cells() > 0
            hosts = [j for j in tr.visitors if self.tracks[j].pop.cells() > 0]
            if falling and hosts and self._vrng.random() < dt * 0.8:
                j = self._vrng.choice(hosts)
                f = self.panels[tr.panel]
                pop = VisualPopulation(self.tracks[j].spec, f.width_um, f.height_um, seed=self._vrng.randrange(10 ** 6))
                pop._enter()
                a = pop.agents[0]
                a.state = ENTERING                                   # swims straight across
                a.grow = 1.0
                self.visitors[tr.panel] = [(j, a, pop)]

    def replay(self, traj: Trajectory, t_sim: float = 0.0) -> None:
        """Start again from a fresh sample at time t_sim (used by the Replay button)."""
        self._traj_hash = None
        self._new_trajectory(traj, t_sim, reseed_all=True)

    def on_state(self, y, traj: Trajectory) -> None:
        """Lab-specific readouts (pH, oxygen, culture tint…). Override in subclasses."""

    def agent_at(self, panel: str, x_um: float, y_um: float, tol_um: float) -> tuple[int, Agent] | None:
        best, bd = None, float("inf")
        for i, tr in enumerate(self.tracks):
            if tr.panel != panel:
                continue
            reach = max(tr.spec.length_um * 0.6, tol_um)
            for a in tr.pop.agents:
                d = math.hypot(a.x - x_um, a.y - y_um)
                if d < reach and d < bd:
                    best, bd = (i, a), d
        return best

    def inspect(self) -> dict | None:
        """What the inspector shows for the selected agent."""
        if not self.selected:
            return None
        i, aid = self.selected
        tr = self.tracks[i]
        a = tr.pop.by_id(aid)
        if a is None:
            return {"track": tr, "agent": None}
        return {"track": tr, "agent": a, "represents": 1.0 / max(tr.concentration, 1e-12)}

    # ------------------------------------------------------------------ internals
    def _new_trajectory(self, traj: Trajectory, t_sim: float, reseed_all: bool = False) -> None:
        first = self._traj_hash is None and not any(tr.pop.agents for tr in self.tracks)
        self._traj_hash = traj.config_hash
        y = traj.state_at(t_sim)
        for tr in self.tracks:
            peak = max((max(tr.raw(row), 0.0) for row in traj.y), default=0.0)
            if peak <= 0:
                new_c = 1.0
            else:
                new_c = float(np.clip(2.0 ** round(math.log2(tr.cap * 0.85 / peak)), 1e-9, 1e12))
            changed = abs(math.log2(new_c / tr.concentration)) > 0.01
            tr.concentration = new_c
            if first or reseed_all or changed:
                tr.pop.seed(min(max(tr.raw(y), 0.0) * tr.concentration, tr.cap))
        self._last_t = t_sim


def a_len(pop: VisualPopulation) -> float:
    return pop.spec.length_um
