"""Microscope fields and the chemostat scene (Qt-free, so it can be tested).

The scene only READS the trajectory. Drawn organisms are persistent agents (viz/population.py) whose
number follows density × sampled volume × one fixed concentration factor per run.
"""
from __future__ import annotations

import numpy as np

from ..library.morphology import spec_for
from ..models.chemostat_rotifer import ChemostatRotifer
from .field import Field
from .specimen import Specimen, Track


ROTIFER_FIELD = Field("Rotifers — 4× objective, sieved sample", 6000.0, 4000.0, 1000.0)
ALGAE_FIELD = Field("Chlorella — 40× objective, counting chamber 0.1 mm deep", 500.0, 333.0, 100.0)



class MicroscopeScene(Specimen):
    """Chemostat view: rotifers in a sieved sample (left) and Chlorella in a counting chamber (right).

    Rotifer eggs follow R/B from the state: each rotifer has a stable random rank, and the fraction of
    rotifers drawn with eggs equals R/B, so eggs appear and disappear on the same animals (no flicker).
    """

    def __init__(self, model: ChemostatRotifer, seed: int = 0):
        self.model = model
        m = model
        va, vr = ALGAE_FIELD.sampled_volume_ml, ROTIFER_FIELD.sampled_volume_ml
        tracks = [                                   # order kept from v0.4: (algae, rotifers)
            Track("chlorella", "Chlorella vulgaris", "كلوريلا فولغاريس", spec_for("chlorella"),
                  "algae", lambda y: max(y[1], 0.0) * m.algae_cells_per_ml_per_umolN * va, 260, "#2ea043"),
            Track("brachionus", "Brachionus calyciflorus", "براكيونس كاليسيفلورس", spec_for("brachionus"),
                  "rotifers", lambda y: max(y[3], 0.0) * m.rotifers_per_ml_per_umolN * vr, 60, "#e3b341"),
        ]
        super().__init__({"rotifers": ROTIFER_FIELD, "algae": ALGAE_FIELD}, tracks, seed)
        self.tint = 0.0
        self.egg_fraction = 0.0
        self.autospore_fraction = 0.0

    @property
    def algae(self):
        return self.tracks[0].pop.agents

    @property
    def rotifers(self):
        return self.tracks[1].pop.agents

    def eggs_of(self, agent) -> int:
        """0, 1 or 2 eggs, stable per animal; the fraction carrying eggs equals R/B."""
        if agent.variant >= self.egg_fraction:
            return 0
        return 1 + int(agent.variant * 7919) % 2

    def on_state(self, y, traj) -> None:
        p = traj.config.parameters
        self.egg_fraction = 0.0 if y[3] <= 0 else float(np.clip(y[2] / y[3], 0, 1))
        self.tint = float(np.clip(y[1] / 80.0, 0, 1))
        fC = p["bC"] * y[0] / (p["KC"] + y[0])
        self.autospore_fraction = float(np.clip(0.3 * fC / p["bC"], 0, 0.3))
