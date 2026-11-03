from fastapi.testclient import TestClient

from app.main import app
from app.metrics import FACILITY_METRICS

client = TestClient(app)


def test_every_fact_has_a_source():
    for f in client.get("/api/facilities").json():
        detail = client.get(f"/api/facilities/{f['id']}").json()
        assert detail["location_source"] is not None
        for m in detail["metrics"].values():
            for fact in m["facts"]:
                assert fact["source"] is not None


def test_missing_metrics_are_explicitly_unknown():
    f = client.get("/api/facilities").json()[0]
    metrics = client.get(f"/api/facilities/{f['id']}").json()["metrics"]
    assert set(metrics) == set(FACILITY_METRICS)
    for m in metrics.values():
        assert m["status"] in ("known", "unknown")
        assert (m["status"] == "unknown") == (m["facts"] == [])


def test_estimate_is_labeled_and_cites_inputs():
    r = client.post("/api/estimate", json={"region_id": "phoenix", "it_capacity_mw": 100, "cooling": "evaporative"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "estimate"
    assert body["inputs"]["pue"]["source"]["id"] == "model_assumption"
    assert body["caveats"]


def test_estimate_rejects_unknown_region():
    r = client.post("/api/estimate", json={"region_id": "nowhere", "it_capacity_mw": 100, "cooling": "evaporative"})
    assert r.status_code == 404
