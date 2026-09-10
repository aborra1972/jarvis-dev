from __future__ import annotations

import json

from jarvis.services.weather import WeatherService, describe_weather


class Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=None):
        return self.body


def test_caba_alias_uses_fixed_buenos_aires_coordinates_and_caches() -> None:
    calls = []

    def fake_open(req, timeout):
        calls.append((req.full_url, timeout))
        return Response({"current": {"temperature_2m": 23.5, "weather_code": 1}})

    service = WeatherService(urlopen=fake_open, ttl_s=60)
    first = service.current("CABA, Argentina")
    second = service.current("Ciudad Autónoma de Buenos Aires")

    assert first == second
    assert first.location == "Buenos Aires, Argentina"
    assert len(calls) == 1
    assert "latitude=-34.6037" in calls[0][0]
    assert "longitude=-58.3816" in calls[0][0]
    assert "geocoding-api.open-meteo.com" not in calls[0][0]
    assert "23.5" in describe_weather(first)


def test_explicit_other_city_still_uses_remote_geocoding() -> None:
    calls = []
    payloads = [
        {"results": [{"latitude": -31.42, "longitude": -64.18, "name": "Córdoba", "country": "Argentina"}]},
        {"current": {"temperature_2m": 18, "weather_code": 3}},
    ]

    def fake_open(req, timeout):
        calls.append(req.full_url)
        return Response(payloads.pop(0))

    reading = WeatherService(urlopen=fake_open).current("Córdoba, Argentina")

    assert reading.location == "Córdoba, Argentina"
    assert "geocoding-api.open-meteo.com" in calls[0]
    assert "api.open-meteo.com" in calls[1]


def test_invalid_forecast_is_rejected() -> None:
    from jarvis.services.weather import WeatherError

    payloads = [
        {"results": [{"latitude": 0, "longitude": 0, "name": "X"}]},
        {"current": {"temperature_2m": "hot", "weather_code": 1}},
    ]

    def fake_open(req, timeout):
        return Response(payloads.pop(0))

    try:
        WeatherService(urlopen=fake_open).current("X")
    except WeatherError as exc:
        assert str(exc) == "invalid_response"
    else:
        raise AssertionError("invalid response was accepted")
