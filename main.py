import re
from typing import Annotated, Literal
from pydantic import Field
import httpx
from fastmcp import FastMCP

mcp = FastMCP(name="Weather Server", stateless_http=True)

def _clean_place(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    s = re.sub(r"[,\s]+$", "", s)
    return s

def _parse_latlon(s: str):
    m = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)\s*[, ]\s*([+-]?\d+(?:\.\d+)?)\s*$", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None

async def _geocode(place: str, lang: str = "en") -> dict:
    """
    Resolve a place name to latitude/longitude using Open-Meteo Geocoding.
    Handles:
      • "City", "City, Country", messy commas/spaces
      • raw "lat,lon" input
    """
    cleaned = _clean_place(place)

    ll = _parse_latlon(cleaned)
    if ll:
        lat, lon = ll
        return {
            "name": place,
            "country": None,
            "admin1": None,
            "latitude": lat,
            "longitude": lon,
        }

    url = "https://geocoding-api.open-meteo.com/v1/search"
    candidates = []
    candidates.append(cleaned)
    if "," in cleaned:
        candidates.append(cleaned.split(",")[0].strip())  # before the first comma
    candidates.append(re.sub(r"[^\w\s\-']", " ", cleaned).strip())  # stripped punctuation

    tried = []
    async with httpx.AsyncClient(timeout=10) as client:
        for q in [c for c in candidates if c and c not in tried]:
            tried.append(q)
            r = await client.get(
                url,
                params={"name": q, "count": 1, "language": lang, "format": "json"},
                headers={"Accept-Language": lang},
            )
            r.raise_for_status()
            data = r.json()
            if data.get("results"):
                return data["results"][0]

    raise ValueError(f"No location found for {place!r} (tried: {', '.join(tried)}).")


@mcp.tool(
    name="get_weather_forecast",
    description="Get a daily weather forecast (1–16 days) for a place using Open-Meteo.",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_weather_forecast(
    place: Annotated[str, "City/place or 'lat,lon', e.g. 'Copenhagen, DK' or '55.676,12.568'"],
    days: Annotated[int, Field(ge=1, le=16, description="Forecast days (1–16)")] = 3,
    units: Annotated[Literal["C", "F"], Field(description="Temperature units")] = "C",
    lang: Annotated[str, Field(min_length=2, max_length=5, description="Language code")] = "en",
) -> dict:
    """
    Return daily max/min temp, precipitation sum, and WMO weather code.
    """
    place = _clean_place(place)
    loc = await _geocode(place, lang=lang)
    lat, lon = loc["latitude"], loc["longitude"]
    temp_unit = "celsius" if units.upper() == "C" else "fahrenheit"

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "temperature_unit": temp_unit,
        "forecast_days": days,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        r.raise_for_status()
        data = r.json()

    times = data["daily"]["time"]
    daily = []
    for i in range(len(times)):
        daily.append({
            "date": times[i],
            "t_max": data["daily"]["temperature_2m_max"][i],
            "t_min": data["daily"]["temperature_2m_min"][i],
            "precipitation_sum": data["daily"]["precipitation_sum"][i],
            "weathercode": data["daily"]["weathercode"][i],
        })

    return {
        "query": place,
        "location": {
            "name": loc.get("name"),
            "country": loc.get("country"),
            "admin1": loc.get("admin1"),
            "latitude": lat,
            "longitude": lon,
            "timezone": data.get("timezone"),
        },
        "units": data.get("daily_units", {}),
        "daily": daily,
    }


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")
