"""Community microscope scene, drawn from the simulation state. Qt-free.

Like a real lab, small and large organisms are looked at in two preparations:
* SMALL — 100× oil immersion, for bacteria, yeasts and small algae (≤ 15 µm)
* LARGE — 10× objective, for ciliates, amoebae, rotifers, hyphae and colonies (> 15 µm)
Inside each panel every organism is drawn at its TRUE relative size.
"""
from __future__ import annotations

import numpy as np

from ..core.trajectory import Trajectory
from ..models.community import NP, PI, Community, water_ph
from .scene import Field

SMALL_LIMIT_UM = 15.0
SMALL_FIELD = Field("100× oil immersion", 120.0, 80.0, 10.0)
LARGE_FIELD = Field("10× objective", 1500.0, 1000.0, 200.0)
MAX_DRAWN = 260


class CommunityScene:
    relax_s = 0.6

    def __init__(self, model: Community, seed: int = 0):
        self.model = model
        self.rng = np.random.default_rng(seed)
        n = len(model.orgs)
        self.cells: list[np.ndarray] = [np.zeros((0, 5)) for _ in range(n)]      # x, y, angle, scale, phase
        self.expected_list = [0.0] * n
        self.concentration = [1.0] * n
        self.panel_of = ["small" if o.size_um <= SMALL_LIMIT_UM else "large" for o in model.orgs]
        self.ph, self.o2, self.turbidity = 7.0, 8.0, 0.0

    @property
    def panels(self) -> list[str]:
        return [p for p in ("small", "large") if p in self.panel_of]

    def field(self, i: int) -> Field:
        return SMALL_FIELD if self.panel_of[i] == "small" else LARGE_FIELD

    def raw_counts(self, y) -> tuple[float, ...]:
        """Cells in one undiluted field of that organism's panel = biomass ÷ cell mass × field volume."""
        out = []
        for i, o in enumerate(self.model.orgs):
            mg_per_cell = 0.09 * (o.size_um ** 3) * 1e-9           # ≈0.09 pg per µm³ of cell
            out.append(max(y[NP + i], 0.0) * self.field(i).sampled_volume_ml / 1000.0 / max(mg_per_cell, 1e-18))
        return tuple(out)

    def expected_counts(self, y) -> tuple[float, ...]:
        """Each organism is concentrated or diluted (in 2× steps, like a dilution series) so that a readable
        number of cells covers a fair share of its panel. The factor is reported on screen."""
        raw = self.raw_counts(y)
        out = []
        for i, (r, o) in enumerate(zip(raw, self.model.orgs)):
            f = self.field(i)
            share = 0.14 / max(self.panel_of.count(self.panel_of[i]), 1)        # area budget in the panel
            cell_area = max(np.pi * (o.size_um / 2) ** 2 * 0.55, 0.5)
            cap = float(np.clip(share * f.width_um * f.height_um / cell_area, 3.0,
                                MAX_DRAWN if self.panel_of[i] == "small" else 60))
            if r <= 0:
                self.concentration[i] = 1.0
                out.append(0.0)
                continue
            self.concentration[i] = float(np.clip(2.0 ** round(np.log2(max(cap / r, 1e-9))), 1e-6, 1e9))
            out.append(min(r * self.concentration[i], cap))
        return tuple(out)

    def sync(self, traj: Trajectory, idx: int, dt_real: float) -> None:
        y = traj.y[idx]
        exp = self.expected_counts(y)
        self.expected_list = list(exp)
        mu = 1.0 / self.relax_s
        for i, target in enumerate(exp):
            f = self.field(i)
            o = self.model.orgs[i]
            arr = self.cells[i]
            if len(arr):
                arr = arr[self.rng.random(len(arr)) >= mu * dt_real]
            k = self.rng.poisson(mu * target * dt_real)
            if k:
                new = np.column_stack([self.rng.uniform(0, f.width_um, k), self.rng.uniform(0, f.height_um, k),
                                       self.rng.uniform(0, 2 * np.pi, k), self.rng.lognormal(0, 0.15, k),
                                       self.rng.random(k)])
                arr = np.vstack([arr, new]) if len(arr) else new
            if len(arr):
                motile = o.motility.lower().startswith(("motile", "swims", "glides", "crawls"))
                if motile:
                    speed = o.size_um * 0.6                      # roughly a few body lengths per second
                    arr[:, 2] += self.rng.normal(0, 0.8, len(arr)) * np.sqrt(dt_real)
                    arr[:, 0] += np.cos(arr[:, 2]) * speed * dt_real
                    arr[:, 1] += np.sin(arr[:, 2]) * speed * dt_real
                else:
                    arr[:, :2] += self.rng.normal(0, 0.02 * f.width_um / 100, (len(arr), 2)) * np.sqrt(dt_real)
                arr[:, 0] %= f.width_um
                arr[:, 1] %= f.height_um
                arr[:, 4] += dt_real * 2
            self.cells[i] = arr
        p = traj.config.parameters
        self.ph = water_ph(y[PI["lac"]], y[PI["ace"]], p["buffer"], p["ph_base"])
        self.o2 = float(y[PI["o2"]])
        self.turbidity = float(np.clip(sum(max(y[NP + i], 0) for i in range(len(self.model.orgs))) / 300.0, 0, 1))
