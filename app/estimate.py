"""Hypothetical-build model.

Every output is an estimate with a low / central / high band. The bands combine the
all-low and all-high assumptions, so they are deliberately wide: they show the range
the inputs allow, not a statistical confidence interval.
"""

from dataclasses import dataclass

HOURS_PER_YEAR = 8760
LITERS_PER_GALLON = 3.785411784
LB_PER_METRIC_TON = 2204.62262

COOLING_TO_WUE_METRIC = {
    "evaporative": "wue_evaporative",
    "air_economizer": "wue_air_economizer",
    "closed_loop_liquid": "wue_closed_loop_liquid",
}


@dataclass(frozen=True)
class Band:
    low: float
    central: float
    high: float

    @classmethod
    def fixed(cls, v: float) -> "Band":
        return cls(v, v, v)

    def scale(self, k: float) -> "Band":
        return Band(self.low * k, self.central * k, self.high * k)

    def times(self, other: "Band") -> "Band":
        return Band(self.low * other.low, self.central * other.central, self.high * other.high)

    def as_dict(self, unit: str) -> dict:
        return {"low": self.low, "central": self.central, "high": self.high, "unit": unit}


def band_from_fact(fact: dict) -> Band:
    mid = fact["value"]
    return Band(
        fact["value_low"] if fact["value_low"] is not None else mid,
        mid,
        fact["value_high"] if fact["value_high"] is not None else mid,
    )


def estimate(
    it_capacity_mw: float,
    utilization: Band,
    pue: Band,
    wue: Band,
    grid_co2_lb_per_mwh: float | None,
) -> dict:
    it_energy_mwh = utilization.scale(it_capacity_mw * HOURS_PER_YEAR)
    total_energy_mwh = it_energy_mwh.times(pue)
    # Site WUE is defined per kWh of IT energy (The Green Grid), not total facility energy.
    water_gal = it_energy_mwh.scale(1000).times(wue).scale(1 / LITERS_PER_GALLON)
    avg_demand_mw = total_energy_mwh.scale(1 / HOURS_PER_YEAR)

    out = {
        "avg_grid_demand": avg_demand_mw.as_dict("MW"),
        "annual_energy": total_energy_mwh.as_dict("MWh"),
        "annual_site_water": water_gal.as_dict("gal"),
        "annual_co2": None,
    }
    if grid_co2_lb_per_mwh is not None:
        out["annual_co2"] = total_energy_mwh.scale(grid_co2_lb_per_mwh / LB_PER_METRIC_TON).as_dict("t CO2")
    return out
