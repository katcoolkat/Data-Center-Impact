import pytest

from app.estimate import Band, estimate


def test_fixed_inputs_give_hand_checkable_numbers():
    # 100 MW IT, 50% utilization, PUE 1.2, WUE 1.0 L/kWh, grid 1000 lb/MWh
    out = estimate(100, Band.fixed(0.5), Band.fixed(1.2), Band.fixed(1.0), 1000)
    it_mwh = 100 * 0.5 * 8760
    assert out["annual_energy"]["central"] == pytest.approx(it_mwh * 1.2)
    assert out["avg_grid_demand"]["central"] == pytest.approx(60)
    # WUE applies to IT energy, not total facility energy
    assert out["annual_site_water"]["central"] == pytest.approx(it_mwh * 1000 / 3.785411784)
    assert out["annual_co2"]["central"] == pytest.approx(it_mwh * 1.2 * 1000 / 2204.62262)


def test_bands_are_ordered():
    out = estimate(50, Band(0.5, 0.65, 0.8), Band(1.1, 1.3, 1.56), Band(0.5, 1.0, 2.0), 800)
    for v in out.values():
        assert v["low"] <= v["central"] <= v["high"]


def test_unknown_grid_leaves_co2_unknown():
    out = estimate(10, Band.fixed(0.5), Band.fixed(1.2), Band.fixed(0.1), None)
    assert out["annual_co2"] is None
