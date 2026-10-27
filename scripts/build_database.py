"""Build data/microverse.sqlite and data/organisms.csv from the organism database in the code."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from microverse.data import db  # noqa: E402

con = db.connect(ROOT / "data" / "microverse.sqlite")
n = db.seed_organisms(con)
db.export_organisms_csv(ROOT / "data" / "organisms.csv")
rows = con.execute("SELECT COUNT(*) FROM organism_functions").fetchone()[0]
print(f"{n} organisms, {rows} organism-function links -> data/microverse.sqlite and data/organisms.csv")
