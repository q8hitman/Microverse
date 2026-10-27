"""Yoghurt microscope scene driven by state; Qt-free.

A drop of the fermenting milk under 100× oil immersion. S. thermophilus grows as chains of cocci
(division lengthens a chain, long chains break); L. bulgaricus as long rods dividing by binary fission.
"""
from __future__ import annotations

from ..library.morphology import spec_for
from ..models.yogurt import XL, XS, milk_ph
from .field import Field
from .specimen import Specimen, Track

# A 10 µL drop spread over 1 cm² → 100 µm equivalent depth per field area.
SMEAR_FIELD = Field("Milk drop — 100× oil immersion (10 µL spread over 1 cm²)", 30.0, 20.0, 100.0)


class YogurtScene(Specimen):
    max_per_species = 260

    def __init__(self, model, seed: int = 0):
        self.model = model
        v = SMEAR_FIELD.sampled_volume_ml
        tracks = [
            Track("sthermophilus", "S. thermophilus", "ستربتوكوكس ثيرموفيلس", spec_for("sthermophilus"),
                  "smear", lambda y: max(y[XS], 0.0) * 1e8 * v, self.max_per_species, "#58a6ff"),
            Track("lbulgaricus", "L. bulgaricus", "لاكتوباسيلس بلغاريكس", spec_for("lbulgaricus"),
                  "smear", lambda y: max(y[XL], 0.0) * 1e8 * v, self.max_per_species * 0.5, "#f0883e"),
        ]
        super().__init__({"smear": SMEAR_FIELD}, tracks, seed)
        self.ph = 6.65

    def st_cells(self) -> int:
        return self.tracks[0].pop.cells()

    @property
    def st_chains(self):
        return self.tracks[0].pop.agents

    @property
    def lb_rods(self):
        return self.tracks[1].pop.agents

    @property
    def capped(self) -> bool:
        return any(tr.target >= tr.cap - 1e-9 for tr in self.tracks)

    def on_state(self, y, traj) -> None:
        self.ph = milk_ph(y[4], traj.config.parameters["buf"])
