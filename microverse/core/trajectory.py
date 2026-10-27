"""Simulation configs and results, with a reproducibility hash."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

import numpy as np


@dataclass(frozen=True)
class RunConfig:
    model_id: str
    model_version: str
    parameters: dict[str, float]
    initial_state: tuple[float, ...]
    t_end: float
    dt_out: float
    mode: str = "deterministic"        # "deterministic" | "stochastic"
    seed: int = 0
    volume_ml: float = 1.0             # culture volume used by the stochastic mode
    solver: str = "LSODA"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["initial_state"] = list(self.initial_state)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RunConfig":
        d = dict(d)
        d["initial_state"] = tuple(d["initial_state"])
        return cls(**d)

    def hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class Trajectory:
    config: RunConfig
    t: np.ndarray
    y: np.ndarray                      # shape (len(t), n_vars)
    state_symbols: tuple[str, ...]
    events: list[str] = field(default_factory=list)

    @property
    def config_hash(self) -> str:
        return self.config.hash()

    def series(self, symbol: str) -> np.ndarray:
        return self.y[:, self.state_symbols.index(symbol)]

    def index_at(self, time: float) -> int:
        return int(np.clip(np.searchsorted(self.t, time), 0, len(self.t) - 1))

    def to_csv(self) -> str:
        header = "time_d," + ",".join(self.state_symbols)
        rows = [header, f"# config_hash={self.config_hash}", f"# mode={self.config.mode} (SIMULATED DATA)"]
        for ti, yi in zip(self.t, self.y):
            rows.append(f"{ti:.6g}," + ",".join(f"{v:.6g}" for v in yi))
        return "\n".join(rows) + "\n"
