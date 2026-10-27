"""Microscope scene driven by simulation state (Qt-free, so it can be tested).

Rules:
* The scene only READS the trajectory. Its own RNG (seeded separately) decides
  visual details: positions, orientation, which cell gets the new neighbour.
* Number of drawn organisms follows the state: the expected count is
  density × sampled volume, and counts fluctuate like a Poisson sample
  (immigration–death process whose stationary distribution is Poisson).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.trajectory import Trajectory
from ..models.chemostat_rotifer import ChemostatRotifer


@dataclass
class Field:
    title: str
    width_um: float
    height_um: float
    depth_um: float
    concentration_factor: float = 1.0      # sample concentrated before viewing (e.g. sieving)

    @property
    def sampled_volume_ml(self) -> float:
        return self.width_um * self.height_um * self.depth_um * 1e-12 * self.concentration_factor


ROTIFER_FIELD = Field("Rotifers — 4× · sample sieved (50 µm) & concentrated 500×",
                      6000.0, 4000.0, 1000.0, 500.0)
ALGAE_FIELD = Field("Chlorella — 40× objective, counting chamber 0.1 mm deep", 500.0, 333.0, 100.0)


class MicroscopeScene:
    relax_s = 0.6           # how fast drawn counts track the state (real seconds)

    def __init__(self, model: ChemostatRotifer, seed: int = 0):
        self.model = model
        self.rng = np.random.default_rng(seed)
        self.algae = np.zeros((0, 4))       # x, y, diameter, phase
        self.rotifers = np.zeros((0, 6))    # x, y, heading, eggs(0/1/2), length, wiggle phase
        self.tint = 0.0                     # 0..1 culture greenness from C
        self.autospore_fraction = 0.0

    def expected_counts(self, y) -> tuple[float, float]:
        m = self.model
        alg = max(y[1], 0) * m.algae_cells_per_ml_per_umolN * ALGAE_FIELD.sampled_volume_ml
        rot = max(y[3], 0) * m.rotifers_per_ml_per_umolN * ROTIFER_FIELD.sampled_volume_ml
        return alg, rot

    def sync(self, traj: Trajectory, idx: int, dt_real: float) -> None:
        y = traj.y[idx]
        p = traj.config.parameters
        e_alg, e_rot = self.expected_counts(y)
        mu = 1.0 / self.relax_s
        self.algae = self._birth_death(self.algae, e_alg, mu, dt_real, self._new_alga)
        self.rotifers = self._birth_death(self.rotifers, e_rot, mu, dt_real, self._new_rotifer)
        # fraction carrying eggs follows R/B from the state
        frac = 0.0 if y[3] <= 0 else float(np.clip(y[2] / y[3], 0, 1))
        if len(self.rotifers):
            has = self.rotifers[:, 3] > 0
            flip = self.rng.random(len(self.rotifers)) < mu * dt_real
            want = self.rng.random(len(self.rotifers)) < frac
            self.rotifers[flip, 3] = np.where(want[flip], np.where(has[flip], self.rotifers[flip, 3],
                                                                   self.rng.integers(1, 3, flip.sum())), 0)
        self.tint = float(np.clip(y[1] / 80.0, 0, 1))
        fC = p["bC"] * y[0] / (p["KC"] + y[0])
        self.autospore_fraction = float(np.clip(0.3 * fC / p["bC"], 0, 0.3))
        self._move(dt_real)

    # -- internals ----------------------------------------------------------
    def _birth_death(self, arr, expected, mu, dt, make):
        if len(arr):
            arr = arr[self.rng.random(len(arr)) >= mu * dt]
        n_new = self.rng.poisson(mu * expected * dt)
        if n_new:
            arr = np.vstack([arr] + [make(arr) for _ in range(n_new)])
        return arr

    def _new_alga(self, existing):
        if len(existing) and self.rng.random() < 0.5:
            px, py = existing[self.rng.integers(len(existing)), :2]
            x, y = px + self.rng.normal(0, 6), py + self.rng.normal(0, 6)   # daughter near a mother cell
        else:
            x, y = self.rng.uniform(0, ALGAE_FIELD.width_um), self.rng.uniform(0, ALGAE_FIELD.height_um)
        lo, typ, hi = self.model.morphology[0].size_um
        d = float(np.clip(self.rng.lognormal(np.log(typ), 0.25), lo, hi))
        return np.array([[x, y, d, self.rng.random()]])

    def _new_rotifer(self, existing):
        lo, typ, hi = self.model.morphology[1].size_um
        length = float(np.clip(self.rng.normal(typ, 30), lo, hi))
        mothers = existing[existing[:, 3] > 0] if len(existing) else existing
        if len(mothers) and self.rng.random() < 0.3:     # some newborns appear next to an egg-bearing female
            x, y = mothers[self.rng.integers(len(mothers)), :2] + self.rng.normal(0, 300, 2)
            length *= 0.6          # newborns are smaller
        else:
            x, y = self.rng.uniform(0, ROTIFER_FIELD.width_um), self.rng.uniform(0, ROTIFER_FIELD.height_um)
        return np.array([[x, y, self.rng.uniform(0, 2 * np.pi), 0, length, self.rng.random()]])

    def _move(self, dt):
        if len(self.algae):
            self.algae[:, :2] += self.rng.normal(0, 0.6, (len(self.algae), 2)) * np.sqrt(dt)
            self.algae[:, 0] %= ALGAE_FIELD.width_um
            self.algae[:, 1] %= ALGAE_FIELD.height_um
        if len(self.rotifers):
            r = self.rotifers
            r[:, 2] += self.rng.normal(0, 0.9, len(r)) * np.sqrt(dt)        # correlated random walk
            speed = self.model.morphology[1].speed_um_s
            r[:, 0] += np.cos(r[:, 2]) * speed * dt
            r[:, 1] += np.sin(r[:, 2]) * speed * dt
            r[:, 4] = np.minimum(r[:, 4] + 20 * dt, self.model.morphology[1].size_um[1] * 1.1)  # newborns grow
            r[:, 5] += dt * 3
            r[:, 0] %= ROTIFER_FIELD.width_um
            r[:, 1] %= ROTIFER_FIELD.height_um
