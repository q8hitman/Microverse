"""Community microscope scene, drawn from the simulation state. Qt-free.

Like a real lab, small and large organisms are looked at in two preparations:
* SMALL — 100× oil immersion, for bacteria, yeasts and small algae (≤ 15 µm)
* LARGE — 10× objective, for ciliates, amoebae, rotifers, hyphae and colonies (> 15 µm)
Inside each panel every organism is drawn at its TRUE relative size. Populations are persistent
(see viz/population.py): cells divide, die, are eaten or swim away — they never pop into existence.
"""
from __future__ import annotations

import numpy as np

from ..library.morphology import spec_for
from ..models.community import NP, PI, Community, water_ph
from .field import Field
from .specimen import Specimen, Track

SMALL_LIMIT_UM = 15.0
SMALL_FIELD = Field("100× oil immersion", 75.0, 50.0, 10.0)
LARGE_FIELD = Field("10× objective", 1500.0, 1000.0, 200.0)
MAX_DRAWN = 260


def cell_mass_mg(key: str) -> float:
    """Dry mass of one drawn unit from its morphology (volume × 0.3 pg/µm³). The community model's biomass is
    treated as dry mass (its yields are dry-weight yields). v0.4 used 0.09 pg × (longest dimension)³."""
    return spec_for(key).dry_mass_mg()


class CommunityScene(Specimen):
    def __init__(self, model: Community, seed: int = 0):
        self.model = model
        orgs = model.orgs
        self.panel_of = ["small" if o.size_um <= SMALL_LIMIT_UM else "large" for o in orgs]
        panels = {"small": SMALL_FIELD, "large": LARGE_FIELD}
        tracks = []
        for i, o in enumerate(orgs):
            f = panels[self.panel_of[i]]
            spec = spec_for(o.key)
            share = 0.14 / max(self.panel_of.count(self.panel_of[i]), 1)        # area budget in the panel
            cell_area = max(spec.length_um * spec.width_um * 0.8 * max(spec.max_chain, 1) ** 0.5, 0.5)
            cap = float(np.clip(share * f.width_um * f.height_um / cell_area, 3.0,
                                MAX_DRAWN if self.panel_of[i] == "small" else 60))
            vol, m = f.sampled_volume_ml, cell_mass_mg(o.key)

            def raw(y, j=NP + i, vol=vol, m=m):
                return max(y[j], 0.0) * vol / 1000.0 / max(m, 1e-18)

            tracks.append(Track(o.key, o.name, o.name_ar, spec, self.panel_of[i], raw, cap, o.colour))
        for i, prey in enumerate(orgs):                 # who can be SEEN eating whom
            eats = [j for j, q in enumerate(orgs)
                    if q.feeding == "predator" and j != i and prey.edible and prey.size_um <= q.prey_size_max]
            tracks[i].predators = tuple(j for j in eats if self.panel_of[j] == self.panel_of[i])
            tracks[i].visitors = tuple(j for j in eats if self.panel_of[j] != self.panel_of[i])
        super().__init__(panels, tracks, seed)
        self.ph, self.o2, self.turbidity = 7.0, 8.0, 0.0

    # kept for code that still uses the v0.4 names
    @property
    def concentration(self) -> list[float]:
        return [tr.concentration for tr in self.tracks]

    @property
    def cells(self) -> list[list]:
        return [tr.pop.agents for tr in self.tracks]

    def field(self, i: int) -> Field:
        return self.panels[self.panel_of[i]]

    def raw_counts(self, y) -> tuple[float, ...]:
        return tuple(tr.raw(y) for tr in self.tracks)

    def on_state(self, y, traj) -> None:
        p = traj.config.parameters
        self.ph = water_ph(y[PI["lac"]], y[PI["ace"]], p["buffer"], p["ph_base"])
        self.o2 = float(y[PI["o2"]])
        self.turbidity = float(np.clip(sum(max(y[NP + i], 0) for i in range(len(self.model.orgs))) / 300.0, 0, 1))
