"""SQLite access: provenance seeding, experiments and immutable predictions."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ..core.model import Model
from ..core.trajectory import RunConfig

SCHEMA = Path(__file__).with_name("schema.sql")
# MICROVERSE_DB lets tests and screenshots use a scratch database (predictions are permanent once written).
DEFAULT_DB = Path(os.environ.get("MICROVERSE_DB") or Path(__file__).resolve().parents[2] / "data" / "microverse.sqlite")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = DEFAULT_DB if path is None else path
    path = Path(path) if str(path) != ":memory:" else path
    if isinstance(path, Path):
        path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', '2')")
    con.commit()
    return con


def seed_model(con: sqlite3.Connection, model: Model) -> None:
    """Record the model's default parameters, their sources and organisms."""
    for prm in model.default_parameters().params.values():
        src = prm.source
        if src:
            con.execute("INSERT OR IGNORE INTO sources(key,citation,doi,url,licence,note,accessed) VALUES (?,?,?,?,?,?,?)",
                        (src.key, src.citation, src.doi, src.url, src.licence, src.note, now()))
        con.execute(
            "INSERT OR IGNORE INTO parameters(model_id,symbol,value,unit,evidence,verified_against_source,source_key,note)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (model.id, prm.symbol, prm.value, prm.unit, prm.evidence.value, int(prm.verified_against_source),
             src.key if src else None, prm.description))
    for morph in getattr(model, "morphology", ()):
        d = asdict(morph)
        d["evidence"] = morph.evidence.value
        con.execute("INSERT OR IGNORE INTO organisms(name,ncbi_taxonomy_id,grp,morphology_json,biosafety_note)"
                    " VALUES (?,?,?,?,?)",
                    (morph.organism, morph.taxonomy_id, morph.shape.split(" ")[0], json.dumps(d),
                     "Harmless organism commonly used in teaching labs."))
    con.commit()


ORGANISM_DB_VERSION = "1.0"


def seed_organisms(con: sqlite3.Connection) -> int:
    """(Re)write the organism reference database: every organism, every function, and who does what."""
    from dataclasses import asdict
    from ..library.functions import FUNCTIONS, functions_of, is_derived
    from ..library.organisms import ORGANISMS
    con.execute("DELETE FROM organism_functions")
    con.execute("DELETE FROM organism_db")
    con.execute("DELETE FROM functions")
    for f in FUNCTIONS.values():
        con.execute("INSERT INTO functions VALUES (?,?,?,?,?,?,?)",
                    (f.key, f.name, f.name_ar, f.meaning, f.meaning_ar, f.in_model, f.in_model_ar))
    for o in ORGANISMS.values():
        rec = asdict(o)
        rec["trait_evidence"] = o.trait_evidence.value
        con.execute(
            "INSERT INTO organism_db VALUES (" + ",".join("?" * 35) + ")",
            (o.key, o.name, o.name_ar, o.common, o.common_ar, o.group, o.group_ar, o.ncbi_taxid,
             " > ".join(o.lineage), o.size_um, o.feeding, o.oxygen, ",".join(o.substrates),
             json.dumps(o.products), o.mu_max, o.ks, o.yield_bio, *o.cardinal_T, *o.cardinal_pH,
             o.role, o.role_ar, o.metabolism, o.metabolism_ar, o.habitat, o.habitat_ar,
             o.applications, o.applications_ar, o.biosafety, o.trait_evidence.value,
             json.dumps(rec, ensure_ascii=False), ORGANISM_DB_VERSION))
        for f in functions_of(o.key):
            con.execute("INSERT INTO organism_functions VALUES (?,?,?)",
                        (o.key, f.key, int(is_derived(o.key, f.key))))
    con.execute("INSERT OR REPLACE INTO meta VALUES ('organism_db_version', ?)", (ORGANISM_DB_VERSION,))
    con.commit()
    return len(ORGANISMS)


def export_organisms_csv(path) -> None:
    """A spreadsheet of the database (UTF-8 with BOM so Excel shows Arabic correctly)."""
    import csv
    from ..library.functions import functions_of
    from ..library.organisms import ORGANISMS
    cols = ["key", "name", "name_ar", "group", "group_ar", "ncbi_taxid", "functions", "functions_ar",
            "role", "role_ar", "feeding", "oxygen", "eats", "produces", "size_um", "mu_max_per_h",
            "t_min", "t_opt", "t_max", "ph_min", "ph_opt", "ph_max", "metabolism", "metabolism_ar",
            "habitat", "applications", "biosafety", "trait_evidence", "references"]
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for o in ORGANISMS.values():
            fs = functions_of(o.key)
            w.writerow([o.key, o.name, o.name_ar, o.group, o.group_ar, o.ncbi_taxid,
                        "; ".join(f.name for f in fs), "؛ ".join(f.name_ar for f in fs),
                        o.role, o.role_ar, o.feeding, o.oxygen, ", ".join(o.substrates),
                        ", ".join(o.products), o.size_um, o.mu_max, *o.cardinal_T, *o.cardinal_pH,
                        o.metabolism, o.metabolism_ar, o.habitat, o.applications, o.biosafety,
                        o.trait_evidence.value, " | ".join(o.references)])


def save_experiment(con: sqlite3.Connection, name: str, cfg: RunConfig, notes: str = "") -> int:
    cur = con.execute("INSERT INTO experiments(name,config_json,config_hash,created,notes) VALUES (?,?,?,?,?)",
                      (name, json.dumps(cfg.to_dict(), sort_keys=True), cfg.hash(), now(), notes))
    con.commit()
    return int(cur.lastrowid)


def freeze_prediction(con: sqlite3.Connection, cfg: RunConfig, summary: dict, hypothesis: str = "",
                      experiment_id: int | None = None) -> int:
    created = now()
    summary_json = json.dumps(summary, sort_keys=True, default=float)
    record_hash = hashlib.sha256(f"{cfg.hash()}|{created}|{summary_json}".encode()).hexdigest()
    cur = con.execute("INSERT INTO predictions(experiment_id,config_hash,created,hypothesis,summary_json,record_hash)"
                      " VALUES (?,?,?,?,?,?)",
                      (experiment_id, cfg.hash(), created, hypothesis, summary_json, record_hash))
    con.commit()
    return int(cur.lastrowid)


def verify_prediction(con: sqlite3.Connection, prediction_id: int) -> bool:
    row = con.execute("SELECT config_hash, created, summary_json, record_hash FROM predictions WHERE id=?",
                      (prediction_id,)).fetchone()
    h = hashlib.sha256(f"{row['config_hash']}|{row['created']}|{row['summary_json']}".encode()).hexdigest()
    return h == row["record_hash"]
