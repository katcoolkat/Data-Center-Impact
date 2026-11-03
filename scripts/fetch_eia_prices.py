"""Pull monthly average retail electricity prices by state and sector from the EIA API v2
and write them as region facts.

Usage:  python scripts/fetch_eia_prices.py   (key from EIA_API_KEY or a .env line EIA_API_KEY=...)
Get a free key at https://www.eia.gov/opendata/register.php

Note: EIA retail prices are state averages across all utilities, not the price a specific
utility charges in the region. The method column says so.
"""

import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "derived"
API = "https://api.eia.gov/v2/electricity/retail-sales/data/"
SECTORS = {"RES": "retail_price_res_cents_kwh", "COM": "retail_price_com_cents_kwh", "IND": "retail_price_ind_cents_kwh"}
START = "2015-01"
SOURCE_ID = "eia_retail_sales"


def region_states() -> dict[str, list[str]]:
    by_state: dict[str, list[str]] = {}
    with (ROOT / "data" / "seed" / "regions.csv").open() as f:
        for r in csv.DictReader(f):
            by_state.setdefault(r["state"], []).append(r["id"])
    return by_state


def fetch(key: str, states: list[str]) -> list[dict]:
    rows, offset = [], 0
    while True:
        params = [
            ("api_key", key), ("frequency", "monthly"), ("data[0]", "price"), ("start", START),
            ("sort[0][column]", "period"), ("sort[0][direction]", "asc"),
            ("offset", str(offset)), ("length", "5000"),
        ]
        params += [("facets[stateid][]", s) for s in states]
        params += [("facets[sectorid][]", s) for s in SECTORS]
        url = f"{API}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=60) as resp:
            page = json.load(resp)["response"]
        rows += page["data"]
        offset += len(page["data"])
        if not page["data"] or offset >= int(page["total"]):
            return rows


def read_key() -> str | None:
    """EIA_API_KEY from the environment, else from a git-ignored .env file at the repo root."""
    if key := os.environ.get("EIA_API_KEY"):
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "EIA_API_KEY":
                return value.strip().strip("\"'")
    return None


def main() -> None:
    key = read_key()
    if not key:
        sys.exit("Set EIA_API_KEY (free: https://www.eia.gov/opendata/register.php)")
    by_state = region_states()
    data = fetch(key, sorted(by_state))

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "sources_eia.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "publisher", "url", "published", "accessed", "kind", "verified", "notes"])
        w.writerow([SOURCE_ID, "Electricity retail sales: average price by state and sector (EIA-861M)",
                    "U.S. Energy Information Administration", "https://www.eia.gov/opendata/browser/electricity/retail-sales",
                    "", date.today().isoformat(), "government_data", 1, "Pulled via EIA API v2."])

    n = 0
    with (OUT / "facts_eia_prices.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entity_type", "entity_id", "metric", "value_low", "value", "value_high", "value_text",
                    "unit", "kind", "period", "source_id", "related_source_ids", "method", "notes"])
        for row in data:
            if row.get("price") in (None, ""):
                continue
            for region_id in by_state.get(row["stateid"], []):
                w.writerow(["region", region_id, SECTORS[row["sectorid"]], "", float(row["price"]), "", "",
                            "¢/kWh", "reported", row["period"], SOURCE_ID, "",
                            "", f"{row['stateid']} statewide average, all utilities."])
                n += 1
    print(f"Wrote {n} price facts for states {sorted(by_state)}")


if __name__ == "__main__":
    main()
