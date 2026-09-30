"""Weather-backed PV simulation using pvlib solar geometry and irradiance."""

import math
from pathlib import Path

import pandas as pd
import pvlib
from pvlib import iotools

from .model import ArrayDesign, Site

_REQUIRED_COLUMNS = {"ghi_w_m2", "dni_w_m2", "dhi_w_m2"}


def load_weather_csv(path: str | Path) -> pd.DataFrame:
    """Load hourly weather data from a CSV with a ``timestamp`` column.

    Required irradiance columns are ``ghi_w_m2``, ``dni_w_m2``, and
    ``dhi_w_m2``. ``temp_air_c`` is optional and defaults to 25 C. Timestamps
    must include a timezone so the solar-position calculation is reproducible.
    """
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    if "timestamp" not in frame:
        raise ValueError("weather CSV must contain a timestamp column")
    frame = frame.set_index("timestamp").sort_index()
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError("weather timestamps must include a timezone")
    missing = _REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"weather CSV is missing required columns: {names}")
    if "temp_air_c" not in frame:
        frame["temp_air_c"] = 25.0
    return validate_weather(frame)


def load_pvgis_tmy(site: Site, timeout: int = 30) -> pd.DataFrame:
    """Download a full-year typical meteorological year from PVGIS.

    PVGIS supplies hourly irradiance in W/m2 and air temperature in degrees C.
    The returned frame is normalized to this package's weather schema and UTC.
    """
    weather, metadata = iotools.get_pvgis_tmy(
        latitude=site.latitude_deg,
        longitude=site.longitude_deg,
        map_variables=True,
        timeout=timeout,
    )
    column_map = {
        "ghi": "ghi_w_m2",
        "dni": "dni_w_m2",
        "dhi": "dhi_w_m2",
        "temp_air": "temp_air_c",
    }
    weather = weather.rename(columns=column_map)
    if weather.index.tz is None:
        weather.index = weather.index.tz_localize("UTC")
    else:
        weather.index = weather.index.tz_convert("UTC")
    weather.attrs["source"] = "PVGIS TMY"
    weather.attrs["metadata"] = metadata
    return validate_weather(weather)


def validate_weather(weather: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a copy of hourly weather observations."""
    if not isinstance(weather.index, pd.DatetimeIndex) or weather.index.tz is None:
        raise ValueError("weather index must be a timezone-aware DatetimeIndex")
    missing = _REQUIRED_COLUMNS - set(weather.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"weather data is missing required columns: {names}")
    result = weather.copy()
    if "temp_air_c" not in result:
        result["temp_air_c"] = 25.0
    numeric_columns = [*sorted(_REQUIRED_COLUMNS), "temp_air_c"]
    if result[numeric_columns].isna().any().any():
        raise ValueError("weather data cannot contain missing numeric values")
    if (result[[*sorted(_REQUIRED_COLUMNS)]] < 0).any().any():
        raise ValueError("irradiance values cannot be negative")
    return result


def simulate_weather_design(site: Site, design: ArrayDesign, weather: pd.DataFrame) -> dict[str, float]:
    """Simulate a design against measured hourly irradiance observations.

    Irradiance inputs are W/m2, temperature is degrees C, and each row is
    treated as one hourly interval. The returned energy is therefore kWh.
    """
    if not 0 <= design.tilt_deg <= 90:
        raise ValueError("tilt_deg must be between 0 and 90")
    if design.row_spacing_m < 1:
        raise ValueError("row_spacing_m must be at least 1 metre")
    weather = validate_weather(weather)
    solar_position = pvlib.solarposition.get_solarposition(
        weather.index,
        latitude=site.latitude_deg,
        longitude=site.longitude_deg,
    )
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=design.tilt_deg,
        surface_azimuth=design.azimuth_deg,
        solar_zenith=solar_position["apparent_zenith"],
        solar_azimuth=solar_position["azimuth"],
        dni=weather["dni_w_m2"],
        ghi=weather["ghi_w_m2"],
        dhi=weather["dhi_w_m2"],
    )["poa_global"].clip(lower=0.0)

    spacing_ratio = design.row_spacing_m / max(0.1, 2.0 * math.cos(math.radians(design.tilt_deg)))
    shade_factor = min(1.0, max(0.0, spacing_ratio / 2.0))
    shading_loss = 0.12 * (1.0 - shade_factor)
    cell_temperature_c = weather["temp_air_c"] + 0.025 * poa
    temperature_factor = (1.0 - 0.004 * (cell_temperature_c - 25.0)).clip(lower=0.80)
    dc_kw = poa * design.module_area_m2 * design.modules * design.module_efficiency * temperature_factor / 1000.0
    energy_kwh = (dc_kw * (1.0 - shading_loss) * design.inverter_efficiency * design.wiring_efficiency).sum()

    return {
        "annual_energy_kwh": float(energy_kwh),
        "average_shading_loss": float(shading_loss),
        "capacity_kw": design.module_area_m2 * design.modules * design.module_efficiency,
        "energy_density_kwh_m2": float(energy_kwh) / max(1.0, design.modules * design.module_area_m2),
        "weather_samples": float(len(weather)),
    }
