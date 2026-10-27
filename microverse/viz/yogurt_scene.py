"""Yoghurt microscope scene (stained smear) driven by state; Qt-free."""
from __future__ import annotations

import numpy as np

from ..core.trajectory import Trajectory
from ..models.yogurt import XL, XS, milk_ph
from .scene import Field

# A 10 µL drop spread over 1 cm² → 100 µm equivalent depth per field area.
SMEAR_FIELD = Field("Stained smear — 100× oil immersion (10 µL spread over 1 cm²)", 30.0, 20.0, 100.0)


class YogurtScene:
    relax_s = 0.6
    max_per_species = 900          # drawing cap; the label reports when it is reached

    def __init__(self, model, seed: int = 0):
        self.model = model
        self.rng = np.random.default_rng(seed)
        self.st_chains: list[list] = []      # each: [x, y, angle, n_cells, curvature]
        self.lb_rods = np.zeros((0, 4))      # x, y, angle, length_um
        self.ph = 6.65
        self.capped = False

    def expected_counts(self, y) -> tuple[float, float]:
        v = SMEAR_FIELD.sampled_volume_ml
        return max(y[XS], 0) * 1e8 * v, max(y[XL], 0) * 1e8 * v

    def st_cells(self) -> int:
        return int(sum(c[3] for c in self.st_chains))

    def sync(self, traj: Trajectory, idx: int, dt_real: float) -> None:
        y = traj.y[idx]
        e_st, e_lb = self.expected_counts(y)
        self.capped = max(e_st, e_lb) > self.max_per_species
        e_st, e_lb = min(e_st, self.max_per_species), min(e_lb, self.max_per_species)
        mu = 1.0 / self.relax_s
        # S. thermophilus: cells live in chains; division mostly lengthens an existing chain
        n = self.st_cells()
        deaths = self.rng.binomial(n, min(mu * dt_real, 1.0)) if n else 0
        for _ in range(deaths):
            c = self.st_chains[self.rng.integers(len(self.st_chains))]
            c[3] -= 1
        self.st_chains = [c for c in self.st_chains if c[3] > 0]
        for _ in range(self.rng.poisson(mu * e_st * dt_real)):
            if self.st_chains and self.rng.random() < 0.75:
                c = self.st_chains[self.rng.integers(len(self.st_chains))]
                if c[3] < 12:
                    c[3] += 1
                    continue
            self.st_chains.append([self.rng.uniform(0, SMEAR_FIELD.width_um), self.rng.uniform(0, SMEAR_FIELD.height_um),
                                   self.rng.uniform(0, np.pi), 1, self.rng.normal(0, 0.15)])
        # L. bulgaricus rods
        if len(self.lb_rods):
            self.lb_rods = self.lb_rods[self.rng.random(len(self.lb_rods)) >= mu * dt_real]
        k = self.rng.poisson(mu * e_lb * dt_real)
        if k:
            new = np.column_stack([self.rng.uniform(0, SMEAR_FIELD.width_um, k), self.rng.uniform(0, SMEAR_FIELD.height_um, k),
                                   self.rng.uniform(0, np.pi, k), np.clip(self.rng.normal(4.0, 1.2, k), 2.0, 9.0)])
            self.lb_rods = np.vstack([self.lb_rods, new])
        self.ph = milk_ph(y[4], traj.config.parameters["buf"])
