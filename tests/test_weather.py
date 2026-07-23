# SPDX-License-Identifier: GPL-3.0-only
"""Weather fetch/translate/shape — the pieces that feed a watch's weather dconf.

Network is injected so these run offline; the WMO->OWM table and the Kelvin
convention must match what the on-watch app reads (Beroset's asteroid-weatherfetch)."""

import json

from asteroid_docking_bay import weather as w


def test_wmo_to_owm_table_and_default():
    assert w.wmo_to_owm(0) == 800 and w.wmo_to_owm(3) == 803
    assert w.wmo_to_owm(61) == 500 and w.wmo_to_owm(95) == 211
    assert w.wmo_to_owm(48) == 741 and w.wmo_to_owm(71) == 600
    assert w.wmo_to_owm(12345) == 800          # unknown → sunny fallback
    assert w.wmo_to_owm(None) == 800 and w.wmo_to_owm("x") == 800


def test_to_kelvin_matches_the_watch_convention():
    # The watch reads celsius = K - 273 (integer), so round(C)+273 round-trips.
    assert w.to_kelvin(0) == 273 and w.to_kelvin(20) == 293
    assert w.to_kelvin(-4.6) == 268 and w.to_kelvin(9.5) == 283   # round half to even → 10
    assert (w.to_kelvin(20) - 273) == 20


def test_parse_forecast_caps_five_days_and_skips_gaps():
    doc = {"daily": {"weather_code": [0, 3, 61, 95, 71, 2, 1],
                     "temperature_2m_max": [20, 18, 15, 12, None, 22, 25],
                     "temperature_2m_min": [10, 9, 8, 5, 0, 12, 14]}}
    days = w.parse_forecast(doc)
    assert len(days) == 4                       # 5-day cap, but day index 4 has a None max → skipped
    assert days[0]["id"] == 800 and days[0]["max_k"] == w.to_kelvin(20)
    assert days[2]["id"] == 500 and days[3]["id"] == 211
    assert days[0]["max_c"] == 20 and days[0]["min_c"] == 10


def test_parse_forecast_empty_on_junk():
    assert w.parse_forecast({}) == [] and w.parse_forecast(None) == []


def test_geocode_resolves_a_city(monkeypatch):
    resp = json.dumps({"results": [{"name": "Berlin", "country_code": "DE",
                                    "latitude": 52.52, "longitude": 13.405}]})
    got = w.geocode("berlin", _get=lambda url, timeout=12: resp)
    assert got == {"city": "Berlin, DE", "lat": 52.52, "lon": 13.405}
    assert "geocoding-api.open-meteo.com" in _captured_url(w, "berlin")


def _captured_url(mod, city):
    seen = {}
    mod.geocode(city, _get=lambda url, timeout=12: seen.setdefault("u", url) or '{"results":[]}')
    return seen["u"]


def test_geocode_none_when_not_found_or_blank():
    assert w.geocode("", _get=lambda u, timeout=12: "{}") is None
    assert w.geocode("nowhere", _get=lambda u, timeout=12: '{"results":[]}') is None


def test_fetch_forecast_builds_from_the_api(monkeypatch):
    doc = json.dumps({"daily": {"weather_code": [0], "temperature_2m_max": [20],
                                "temperature_2m_min": [10]}})
    seen = {}
    days = w.fetch_forecast(52.5, 13.4,
                            _get=lambda url, timeout=12: (seen.update(u=url), doc)[1])
    assert len(days) == 1 and days[0]["id"] == 800
    assert "latitude=52.5" in seen["u"] and "longitude=13.4" in seen["u"]
    assert w.fetch_forecast(None, None) == []       # no location → no fetch


def test_dconf_writeset_keys_types_and_values():
    days = [{"id": 800, "min_c": 10, "max_c": 20, "min_k": 283, "max_k": 293},
            {"id": 500, "min_c": 8, "max_c": 15, "min_k": 281, "max_k": 288}]
    ws = w.dconf_writeset("Berlin, DE", days, ts=1721000000)
    d = {k: (t, v) for k, t, v in ws}
    assert d["/org/asteroidos/weather/city-name"] == ("string", "Berlin, DE")
    assert d["/org/asteroidos/weather/timestamp-day0"] == ("int", 1721000000)
    assert d["/org/asteroidos/weather/day0/id"] == ("int", 800)
    assert d["/org/asteroidos/weather/day0/max-temp"] == ("int", 293)
    assert d["/org/asteroidos/weather/day1/min-temp"] == ("int", 281)
    # exactly the 2 base keys + 3 per day
    assert len(ws) == 2 + 3 * 2


# ── the ops (mocked network + config) ────────────────────────────────────────

from asteroid_docking_bay import rpcops


def test_weather_get_op_no_location(monkeypatch):
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    d = rpcops.DISPATCH._data["weather.get"]({})
    assert d["ok"] is True and d["location"] is None and d["days"] == []


def test_weather_get_op_with_location(monkeypatch):
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"weather": {"city": "X", "lat": 1, "lon": 2}})
    monkeypatch.setattr(rpcops, "fetch_forecast",
                        lambda lat, lon: [{"id": 800, "min_k": 283, "max_k": 293,
                                           "min_c": 10, "max_c": 20}])
    d = rpcops.DISPATCH._data["weather.get"]({})
    assert d["ok"] and d["location"]["city"] == "X" and d["days"][0]["id"] == 800


def test_weather_set_location_op(monkeypatch):
    saved = {}
    monkeypatch.setattr(rpcops, "geocode",
                        lambda c: {"city": "Berlin, DE", "lat": 52.5, "lon": 13.4})
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    monkeypatch.setattr(rpcops, "save_config", lambda cfg: saved.update(cfg))
    d = rpcops.DISPATCH._data["weather.set_location"]({"city": "berlin"})
    assert d["ok"] and d["location"]["city"] == "Berlin, DE"
    assert saved["weather"]["lat"] == 52.5


def test_weather_set_location_not_found(monkeypatch):
    monkeypatch.setattr(rpcops, "geocode", lambda c: None)
    d = rpcops.DISPATCH._data["weather.set_location"]({"city": "zzz"})
    assert d["ok"] is False and "not found" in d["error"]


def test_watch_weather_sync_op_fetches_and_writes(monkeypatch):
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"weather": {"city": "X", "lat": 1, "lon": 2}})
    monkeypatch.setattr(rpcops, "fetch_forecast",
                        lambda lat, lon: [{"id": 800, "min_k": 283, "max_k": 293,
                                           "min_c": 10, "max_c": 20}])
    captured = {}

    class W:
        def __init__(self, *a, **k):
            pass

        def weather_sync(self, ws):
            captured["ws"] = ws
            return True

    monkeypatch.setattr(rpcops, "Watch", W)
    monkeypatch.setattr(rpcops, "_reachable_transport", lambda s: None)
    d = rpcops.DISPATCH._data["watch.weather_sync"]({"serial": "S1"})
    assert d["ok"] is True and d["city"] == "X"
    assert any(k.endswith("/day0/id") for k, t, v in captured["ws"])


def test_watch_weather_sync_op_needs_a_location(monkeypatch):
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    d = rpcops.DISPATCH._data["watch.weather_sync"]({"serial": "S1"})
    assert d["ok"] is False and "no location" in d["error"]
