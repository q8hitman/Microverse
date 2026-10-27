"""A microscope field of view (shared by all scenes)."""
from __future__ import annotations

from dataclasses import dataclass


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
