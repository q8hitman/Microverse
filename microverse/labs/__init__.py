"""Registry of labs: two fixed labs plus the Community Builder, which is built on demand."""
from __future__ import annotations

from functools import lru_cache

from . import chemostat, community, yogurt
from .base import Lab

PLANNED = (
    ("Biofilm Simulator", "محاكي الأغشية الحيوية", "Attachment, oxygen gradients, cross-sections"),
    ("Bioinformatics", "المعلوماتية الحيوية", "FASTA/FASTQ, diversity, phylogenetic trees"),
    ("Agar: competition & antibiotics-free zones", "الآجار: التنافس بين المستعمرات", "Two species on one plate"),
)


@lru_cache(maxsize=None)
def fixed_labs() -> tuple[Lab, ...]:
    return (chemostat.build(), yogurt.build())


@lru_cache(maxsize=None)
def community_lab(keys: tuple[str, ...], preset: str = "custom") -> Lab:
    return community.build(keys, preset)


def all_labs() -> tuple[Lab, ...]:
    """Fixed labs plus one community lab per preset (used by tests and the library page)."""
    return fixed_labs() + tuple(community_lab(ks, k) for k, ks, *_ in community.PRESETS)


def get(key: str) -> Lab:
    for l in fixed_labs():
        if l.key == key:
            return l
    raise KeyError(key)
