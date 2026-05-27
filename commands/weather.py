import json
import urllib.parse
import urllib.request
from typing import Any

from commands.base_command import BaseCommand, CommandArguments

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
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


class Weather(BaseCommand):

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def tags(self) -> list[str]:
        return ["info", "weather"]

    @property
    def description(self) -> str:
        return "Gets the current weather for a given city or location."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or location, e.g. 'Paris', 'Tokyo', 'New York'.",
                },
            },
            "required": ["location"],
        }

    def execute(self, cmd_args: CommandArguments) -> str:
        location = cmd_args.args.get("location", "").strip()
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

            place     = results[0]
            lat, lon  = place["latitude"], place["longitude"]
            city      = place.get("name", location)
            country   = place.get("country", "")

            weather_url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
            )
            current   = _fetch_json(weather_url)["current"]
            condition = _WMO_CODES.get(current["weather_code"], "unknown conditions")

            return (
                f"{city}, {country}: {condition}, "
                f"{current['temperature_2m']}°C, "
                f"wind {current['wind_speed_10m']} km/h, "
                f"humidity {current['relative_humidity_2m']}%."
            )

        except Exception as e:
            return f"Could not fetch weather for '{location}': {e}"
