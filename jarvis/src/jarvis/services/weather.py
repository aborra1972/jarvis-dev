"""Small Open-Meteo weather client used by Jarvis's deterministic fast path."""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class WeatherReading:
    location: str
    temperature_c: float
    weather_code: int


class WeatherError(Exception):
    """Raised when Open-Meteo is unavailable or returns an invalid response."""


_BUENOS_AIRES_COORDINATES = (-34.6037, -58.3816)
_BUENOS_AIRES_DISPLAY_NAME = "Buenos Aires, Argentina"
_CABA_ALIASES = frozenset(
    {
        "caba",
        "caba argentina",
        "ciudad de buenos aires",
        "ciudad de buenos aires argentina",
        "ciudad autonoma de buenos aires",
        "ciudad autonoma de buenos aires argentina",
    }
)


def _canonical_location_key(location: str) -> str:
    """Normalize location spelling for the deliberately narrow CABA alias."""
    without_accents = "".join(
        char for char in unicodedata.normalize("NFKD", location.casefold())
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


class WeatherService:
    """Geocode and fetch current weather with a bounded in-memory TTL cache."""

    def __init__(
        self,
        *,
        timeout_s: float = 3.0,
        ttl_s: float = 300.0,
        max_cache_size: int = 32,
        urlopen: Callable[..., Any] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.timeout_s = timeout_s
        self.ttl_s = ttl_s
        self.max_cache_size = max_cache_size
        self._urlopen = urlopen or urllib.request.urlopen
        self._clock = clock or time.monotonic
        self._cache: dict[str, tuple[float, WeatherReading]] = {}
        self._lock = threading.Lock()

    def current(self, location: str) -> WeatherReading:
        key = " ".join(location.casefold().split())
        if not key or len(key) > 80:
            raise WeatherError("invalid_location")
        if _canonical_location_key(location) in _CABA_ALIASES:
            key = "caba"
        now = self._clock()
        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] <= self.ttl_s:
                return cached[1]
            if cached:
                del self._cache[key]

        latitude, longitude, display_name = self._geocode(location)
        reading = self._forecast(display_name, latitude, longitude)
        with self._lock:
            if len(self._cache) >= self.max_cache_size:
                oldest = min(self._cache, key=lambda item: self._cache[item][0])
                del self._cache[oldest]
            self._cache[key] = (self._clock(), reading)
        return reading

    def _get_json(self, base_url: str, params: dict[str, str]) -> dict[str, Any]:
        url = base_url + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with self._urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read(64 * 1024)
            data = json.loads(raw.decode("utf-8"))
        except (OSError, TimeoutError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise WeatherError("unavailable") from exc
        if not isinstance(data, dict):
            raise WeatherError("invalid_response")
        return data

    def _geocode(self, location: str) -> tuple[float, float, str]:
        if _canonical_location_key(location) in _CABA_ALIASES:
            latitude, longitude = _BUENOS_AIRES_COORDINATES
            return latitude, longitude, _BUENOS_AIRES_DISPLAY_NAME

        data = self._get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": location, "count": "1", "language": "es", "format": "json"},
        )
        results = data.get("results")
        if not isinstance(results, list) or not results or not isinstance(results[0], dict):
            raise WeatherError("not_found")
        result = results[0]
        latitude, longitude = result.get("latitude"), result.get("longitude")
        if (
            isinstance(latitude, bool) or not isinstance(latitude, (int, float))
            or isinstance(longitude, bool) or not isinstance(longitude, (int, float))
            or not -90 <= latitude <= 90 or not -180 <= longitude <= 180
        ):
            raise WeatherError("invalid_response")
        name = result.get("name")
        country = result.get("country")
        if not isinstance(name, str) or not name.strip():
            raise WeatherError("invalid_response")
        display = name.strip() + (f", {country.strip()}" if isinstance(country, str) and country.strip() else "")
        return float(latitude), float(longitude), display

    def _forecast(self, location: str, latitude: float, longitude: float) -> WeatherReading:
        data = self._get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": str(latitude), "longitude": str(longitude),
                "current": "temperature_2m,weather_code", "timezone": "auto",
            },
        )
        current = data.get("current")
        if not isinstance(current, dict):
            raise WeatherError("invalid_response")
        temperature, code = current.get("temperature_2m"), current.get("weather_code")
        if (
            isinstance(temperature, bool) or not isinstance(temperature, (int, float))
            or isinstance(code, bool) or not isinstance(code, int)
            or not -100 <= temperature <= 100 or not 0 <= code <= 99
        ):
            raise WeatherError("invalid_response")
        return WeatherReading(location, float(temperature), code)


def describe_weather(reading: WeatherReading) -> str:
    descriptions = {
        0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
        45: "con niebla", 48: "con niebla", 51: "con llovizna", 53: "con llovizna", 55: "con llovizna",
        61: "con lluvia", 63: "con lluvia", 65: "con lluvia intensa", 71: "con nieve", 73: "con nieve", 75: "con nieve intensa",
        80: "con chaparrones", 81: "con chaparrones", 82: "con chaparrones fuertes", 95: "con tormenta", 96: "con tormenta", 99: "con tormenta",
    }
    condition = descriptions.get(reading.weather_code, "con condiciones variables")
    return f"En {reading.location} hay {reading.temperature_c:g} grados y está {condition}."
