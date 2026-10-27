"""Reproducible experiment files (JSON)."""
from __future__ import annotations

import json
from pathlib import Path

from ..core.trajectory import RunConfig

FORMAT = "microverse.experiment/1"


def save(path: Path | str, cfg: RunConfig, name: str = "", notes: str = "") -> None:
    doc = {"format": FORMAT, "name": name, "notes": notes, "config": cfg.to_dict(), "config_hash": cfg.hash()}
    Path(path).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


def load(path: Path | str) -> RunConfig:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("format") != FORMAT:
        raise ValueError(f"not a MicroVerse experiment file: {path}")
    cfg = RunConfig.from_dict(doc["config"])
    if cfg.hash() != doc["config_hash"]:
        raise ValueError("config hash mismatch: the file was modified after saving")
    return cfg
