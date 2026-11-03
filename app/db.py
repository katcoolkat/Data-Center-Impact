"""Build the SQLite database from the CSVs in data/. The CSVs are the source of truth
(reviewable in git diffs); the .db file is a disposable build artifact."""

import csv
import sqlite3
from pathlib import Path

from app.metrics import ALL

ROOT = Path(__file__).resolve().parent.parent
DATA_DIRS = [ROOT / "data" / "seed", ROOT / "data" / "derived"]
DB_PATH = ROOT / "data" / "explorer.db"
SCHEMA = Path(__file__).with_name("schema.sql")

TABLE_ORDER = ["sources", "regions", "facilities", "facts"]
NUMERIC = {"lat", "lon", "value_low", "value", "value_high", "verified"}


def _rows(table: str):
    """Yield rows for `table` from every CSV named `<table>*.csv` across data dirs."""
    for d in DATA_DIRS:
        for path in sorted(d.glob(f"{table}*.csv")):
            with path.open(newline="", encoding="utf-8") as f:
                for line_no, row in enumerate(csv.DictReader(f), start=2):
                    clean = {}
                    for k, v in row.items():
                        v = (v or "").strip()
                        clean[k] = (float(v) if k in NUMERIC else v) if v != "" else None
                    yield path.name, line_no, clean


def _validate_fact(row: dict, where: str) -> None:
    metrics = ALL.get(row["entity_type"])
    if metrics is None or row["metric"] not in metrics:
        raise ValueError(f"{where}: unknown metric {row['entity_type']}.{row['metric']}")
    lo, mid, hi = row.get("value_low"), row.get("value"), row.get("value_high")
    if lo is not None and mid is not None and lo > mid:
        raise ValueError(f"{where}: value_low > value")
    if hi is not None and mid is not None and hi < mid:
        raise ValueError(f"{where}: value_high < value")


def build(db_path: Path = DB_PATH) -> Path:
    db_path.unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text())
    for table in TABLE_ORDER:
        for fname, line_no, row in _rows(table):
            where = f"{fname}:{line_no}"
            if table == "facts":
                _validate_fact(row, where)
            cols = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            try:
                con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))
            except sqlite3.Error as e:
                raise ValueError(f"{where}: {e}") from e
    con.commit()
    con.close()
    return db_path


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    if not db_path.exists():
        build(db_path)
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


if __name__ == "__main__":
    print(f"Built {build()}")
