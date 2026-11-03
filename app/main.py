from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db
from app.estimate import COOLING_TO_WUE_METRIC, Band, band_from_fact, estimate
from app.metrics import FACILITY_METRICS, MODEL_METRICS, REGION_METRICS

STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="Data Center Impact Explorer API",
    description=(
        "Sourced resource-impact data for data centers in a small set of US regions. "
        "Every value carries a source and a kind (measured / reported / estimate / assumption). "
        "Metrics without a sourced value are returned as `unknown`."
    ),
    version="0.1.0",
)
con = db.connect()


def _sources() -> dict[str, dict]:
    return {r["id"]: dict(r) for r in con.execute("SELECT * FROM sources")}


def _facts(entity_type: str, entity_id: str) -> list[dict]:
    rows = con.execute(
        "SELECT * FROM facts WHERE entity_type = ? AND entity_id = ? ORDER BY metric, period",
        (entity_type, entity_id),
    )
    return [dict(r) for r in rows]


def _with_sources(fact: dict, sources: dict) -> dict:
    fact = {k: v for k, v in fact.items() if k not in ("entity_type", "entity_id")}
    fact["source"] = sources.get(fact.pop("source_id"))
    related = fact.pop("related_source_ids") or ""
    fact["related_sources"] = [sources[s] for s in related.split(",") if s.strip() in sources]
    return fact


def _metric_block(entity_type: str, entity_id: str, metrics: dict) -> dict:
    """Every known metric appears; those with no sourced fact are explicitly unknown."""
    sources = _sources()
    facts = _facts(entity_type, entity_id)
    out = {}
    for metric, (unit, label) in metrics.items():
        rows = [_with_sources(f, sources) for f in facts if f["metric"] == metric]
        out[metric] = {"label": label, "unit": unit, "status": "known" if rows else "unknown", "facts": rows}
    return out


def _latest(entity_type: str, entity_id: str, metric: str) -> dict | None:
    row = con.execute(
        "SELECT * FROM facts WHERE entity_type = ? AND entity_id = ? AND metric = ? "
        "ORDER BY period DESC LIMIT 1",
        (entity_type, entity_id, metric),
    ).fetchone()
    return dict(row) if row else None


@app.get("/api/regions")
def list_regions():
    return [dict(r) for r in con.execute("SELECT * FROM regions ORDER BY name")]


@app.get("/api/regions/{region_id}")
def get_region(region_id: str):
    row = con.execute("SELECT * FROM regions WHERE id = ?", (region_id,)).fetchone()
    if not row:
        raise HTTPException(404, "region not found")
    return {**dict(row), "metrics": _metric_block("region", region_id, REGION_METRICS)}


@app.get("/api/facilities")
def list_facilities():
    rows = con.execute(
        """SELECT f.*, (SELECT COUNT(DISTINCT metric) FROM facts
                        WHERE entity_type = 'facility' AND entity_id = f.id) AS known_metrics
           FROM facilities f ORDER BY f.name"""
    )
    return [{**dict(r), "total_metrics": len(FACILITY_METRICS)} for r in rows]


@app.get("/api/facilities/{facility_id}")
def get_facility(facility_id: str):
    row = con.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,)).fetchone()
    if not row:
        raise HTTPException(404, "facility not found")
    facility = dict(row)
    facility["location_source"] = _sources().get(facility.pop("source_id"))
    return {**facility, "metrics": _metric_block("facility", facility_id, FACILITY_METRICS)}


@app.get("/api/sources")
def list_sources():
    return list(_sources().values())


@app.get("/api/assumptions")
def list_assumptions():
    return _metric_block("model", "default", MODEL_METRICS)


class EstimateRequest(BaseModel):
    region_id: str
    it_capacity_mw: float = Field(gt=0, le=5000, description="Nameplate IT capacity")
    cooling: Literal["evaporative", "air_economizer", "closed_loop_liquid"]
    pue: float | None = Field(None, ge=1.0, le=3.0, description="Override the default PUE range")
    utilization: float | None = Field(None, gt=0, le=1.0, description="Override the default utilization range")


@app.post("/api/estimate")
def post_estimate(req: EstimateRequest):
    if not con.execute("SELECT 1 FROM regions WHERE id = ?", (req.region_id,)).fetchone():
        raise HTTPException(404, "region not found")

    sources = _sources()
    inputs = {}

    def assumption(metric: str, override: float | None) -> Band:
        if override is not None:
            inputs[metric] = {"value": override, "kind": "user_input"}
            return Band.fixed(override)
        fact = _latest("model", "default", metric)
        if fact is None:
            raise HTTPException(500, f"missing model assumption: {metric}")
        inputs[metric] = _with_sources(fact, sources)
        return band_from_fact(fact)

    utilization = assumption("utilization", req.utilization)
    pue = assumption("pue", req.pue)
    wue = assumption(COOLING_TO_WUE_METRIC[req.cooling], None)

    grid = _latest("region", req.region_id, "grid_co2_lb_per_mwh")
    inputs["grid_co2_lb_per_mwh"] = _with_sources(grid, sources) if grid else {"status": "unknown"}

    result = estimate(req.it_capacity_mw, utilization, pue, wue, grid["value"] if grid else None)
    return {
        "kind": "estimate",
        "outputs": result,
        "inputs": inputs,
        "caveats": [
            "Bands combine all-low and all-high assumptions; they are not statistical confidence intervals.",
            "Site water only. Water consumed off-site to generate the electricity is not modeled.",
            "CO2 uses the grid's annual average emission rate, not the marginal rate a new load would cause.",
        ]
        + ([] if grid else ["Grid emission rate for this region is unknown, so CO2 is not estimated."]),
    }


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")
