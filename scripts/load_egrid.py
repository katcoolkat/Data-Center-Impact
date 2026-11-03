"""Load eGRID subregion CO2 output emission rates into region facts.

Usage:  python scripts/load_egrid.py data/raw/egrid2023_data_rev2.xlsx 2023

Download the eGRID data file (.xlsx) from https://www.epa.gov/egrid/download-data
and save it under data/raw/ (git-ignored). The subregion sheet is named SRL<yy>;
row 1 holds long descriptions and row 2 holds the column codes this script reads.
"""

import csv
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "derived"
RATE_COL = "SRCO2RTA"  # subregion annual CO2 total output emission rate, lb/MWh


def main(xlsx: Path, year: str) -> None:
    sheet = f"SRL{year[-2:]}"
    df = pd.read_excel(xlsx, sheet_name=sheet, header=1)
    if "SUBRGN" not in df or RATE_COL not in df:
        sys.exit(f"Expected SUBRGN and {RATE_COL} in sheet {sheet}; found {list(df.columns)[:15]}...")
    rates = dict(zip(df["SUBRGN"], df[RATE_COL]))

    source_id = f"egrid_{year}"
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "sources_egrid.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "publisher", "url", "published", "accessed", "kind", "verified", "notes"])
        w.writerow([source_id, f"Emissions & Generation Resource Integrated Database (eGRID{year})",
                    "U.S. Environmental Protection Agency", "https://www.epa.gov/egrid/download-data",
                    "", date.today().isoformat(), "government_data", 1, f"File {xlsx.name}, sheet {sheet}, column {RATE_COL}."])

    with (ROOT / "data" / "seed" / "regions.csv").open() as f, \
         (OUT / "facts_egrid.csv").open("w", newline="") as g:
        w = csv.writer(g)
        w.writerow(["entity_type", "entity_id", "metric", "value_low", "value", "value_high", "value_text",
                    "unit", "kind", "period", "source_id", "related_source_ids", "method", "notes"])
        for r in csv.DictReader(f):
            rate = rates.get(r["egrid_subregion"])
            if rate is None or pd.isna(rate):
                print(f"  no rate for {r['id']} ({r['egrid_subregion']}) — left unknown")
                continue
            w.writerow(["region", r["id"], "grid_co2_lb_per_mwh", "", round(float(rate), 2), "", "",
                        "lb/MWh", "reported", year, source_id, "", "",
                        f"eGRID subregion {r['egrid_subregion']} annual average; not a marginal rate."])
            print(f"  {r['id']}: {rate:.1f} lb/MWh ({r['egrid_subregion']})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), sys.argv[2])
