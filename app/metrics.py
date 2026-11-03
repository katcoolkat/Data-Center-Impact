"""The metrics the tool knows about. Anything not listed here is rejected at load time,
so a typo in a CSV can't silently create a new, empty column."""

FACILITY_METRICS = {
    "it_capacity_mw": ("MW", "IT capacity"),
    "grid_demand_mw": ("MW", "Requested / contracted grid demand"),
    "annual_energy_mwh": ("MWh", "Annual electricity use"),
    "annual_water_gal": ("gal", "Annual water consumption"),
    "pue": ("ratio", "Power usage effectiveness"),
    "wue_l_per_kwh": ("L/kWh", "Water usage effectiveness"),
    "cooling_method": (None, "Cooling method"),
    "water_source": (None, "Water source"),
}

REGION_METRICS = {
    "grid_co2_lb_per_mwh": ("lb/MWh", "Grid CO2 output emission rate (annual average)"),
    "retail_price_com_cents_kwh": ("¢/kWh", "Average commercial retail electricity price"),
    "retail_price_ind_cents_kwh": ("¢/kWh", "Average industrial retail electricity price"),
    "retail_price_res_cents_kwh": ("¢/kWh", "Average residential retail electricity price"),
}

MODEL_METRICS = {
    "utilization": ("fraction", "Average IT load as share of IT capacity"),
    "pue": ("ratio", "Power usage effectiveness"),
    "wue_evaporative": ("L/kWh", "Site WUE, evaporative (cooling tower)"),
    "wue_air_economizer": ("L/kWh", "Site WUE, air-side economizer + adiabatic"),
    "wue_closed_loop_liquid": ("L/kWh", "Site WUE, closed-loop liquid (dry cooler)"),
}

ALL = {"facility": FACILITY_METRICS, "region": REGION_METRICS, "model": MODEL_METRICS}
