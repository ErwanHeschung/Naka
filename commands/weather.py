import urllib.parse
from datetime import date, timedelta
from typing import Any

from commands.base_command import BaseCommand, CommandArguments
from utils import http_client as http

_WMO_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "violent showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}


def _fetch_json(url: str) -> dict:
    resp = http.get(url, timeout=5)
    resp.raise_for_status()
    return resp.json()


def _day_label(iso_date: str) -> str:
    """Turn '2026-05-28' into 'Today', 'Tomorrow', or 'Thursday 29 May'."""
    d     = date.fromisoformat(iso_date)
    today = date.today()
    if d == today:
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    return d.strftime("%A %-d %B")


class Weather(BaseCommand):

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def tags(self) -> list[str]:
        return ["info", "weather"]

    @property
    def description(self) -> str:
        return (
            "Gets the current weather or a multi-day forecast for a given city or location. "
            "Use days=0 for current conditions, days=1–7 for a daily forecast."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or location, e.g. 'Paris', 'Tokyo', 'New York'.",
                },
                "days": {
                    "type": "integer",
                    "description": (
                        "Number of days to forecast. "
                        "0 = current conditions (default), 1 = today only, "
                        "2 = today + tomorrow, up to 7."
                    ),
                    "minimum": 0,
                    "maximum": 7,
                    "default": 0,
                },
            },
            "required": ["location"],
        }

    def execute(self, cmd_args: CommandArguments) -> str:
        location = cmd_args.args.get("location", "").strip()
        days     = int(cmd_args.args.get("days", 0))

        if not location:
            return "No location provided."

        try:
            geo_url = (
                "https://geocoding-api.open-meteo.com/v1/search"
                f"?name={urllib.parse.quote(location)}&count=1&language=en&format=json"
            )
            results = _fetch_json(geo_url).get("results")
            if not results:
                return f"Location '{location}' not found."

            place   = results[0]
            lat     = place["latitude"]
            lon     = place["longitude"]
            city    = place.get("name", location)
            country = place.get("country", "")

            if days == 0:
                return self._current(lat, lon, city, country)
            return self._forecast(lat, lon, city, country, days)

        except Exception as e:
            return f"Could not fetch weather for '{location}': {e}"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _current(self, lat: float, lon: float, city: str, country: str) -> str:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
        )
        current   = _fetch_json(url)["current"]
        condition = _WMO_CODES.get(current["weather_code"], "unknown conditions")
        return (
            f"{city}, {country}: {condition}, "
            f"{current['temperature_2m']}°C, "
            f"wind {current['wind_speed_10m']} km/h, "
            f"humidity {current['relative_humidity_2m']}%."
        )

    def _forecast(self, lat: float, lon: float, city: str, country: str, days: int) -> str:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&daily=temperature_2m_max,temperature_2m_min,weather_code,"
            "wind_speed_10m_max,precipitation_sum"
            f"&forecast_days={days}"
            "&timezone=auto"
        )
        daily  = _fetch_json(url)["daily"]
        dates  = daily["time"]
        t_max  = daily["temperature_2m_max"]
        t_min  = daily["temperature_2m_min"]
        codes  = daily["weather_code"]
        winds  = daily["wind_speed_10m_max"]
        precip = daily["precipitation_sum"]

        lines = [f"{city}, {country} — {days}-day forecast:"]
        for i in range(len(dates)):
            condition = _WMO_CODES.get(codes[i], "unknown")
            label     = _day_label(dates[i])
            lines.append(
                f"{label}: {condition}, "
                f"{t_min[i]}–{t_max[i]}°C, "
                f"wind {winds[i]} km/h, "
                f"precip {precip[i]} mm."
            )
        return "\n".join(lines)
