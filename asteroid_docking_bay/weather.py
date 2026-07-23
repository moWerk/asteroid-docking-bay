# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""Fetch weather (Open-Meteo, keyless) and shape it for a watch's weather dconf.

The key layout, units and the WMO->OWM code translation are taken from Ed
Beroset's asteroid-weatherfetch (GPL-3.0-or-later) — the reference sync tool —
so the on-watch weather app and Today screen read what we write unchanged.

The watch stores (Nemo Configuration / dconf):
  /org/asteroidos/weather/city-name         string
  /org/asteroidos/weather/timestamp-day0    int   epoch seconds = the date of day0
  /org/asteroidos/weather/day{0..4}/id      int   OWM condition code (icon lookup)
  /org/asteroidos/weather/day{0..4}/min-temp int  KELVIN
  /org/asteroidos/weather/day{0..4}/max-temp int  KELVIN
and reads temps back as celsius = K - 273 (integer), so we write round(C)+273.
Open-Meteo returns WMO codes; the watch's icon maps are keyed by OWM codes, so
we translate WMO->OWM (Beroset's iconlookup table)."""

import json
import time
import urllib.parse
import urllib.request

WEATHER_ROOT = "/org/asteroidos/weather"
MAX_DAYS = 5

# WMO weather code -> OpenWeatherMap condition code (Beroset's iconlookup,
# asteroid-weatherfetch WeatherParser.cpp). The watch weathericons.js maps are
# OWM-keyed, so a raw WMO code would mis-map — always translate before writing.
_WMO_TO_OWM = {
    0: 800, 1: 801, 2: 802, 3: 803,
    45: 741, 48: 741,
    51: 300, 53: 301, 55: 302, 56: 612, 57: 613,
    61: 500, 63: 501, 65: 502, 66: 511, 67: 511,
    71: 600, 73: 601, 75: 602, 77: 601,
    80: 500, 81: 501, 82: 502, 85: 600, 86: 601,
    95: 211, 96: 200, 99: 211,
}


def wmo_to_owm(code):
    """WMO weather code -> OWM condition code (default 800 — every day is sunny)."""
    try:
        return _WMO_TO_OWM.get(int(code), 800)
    except (TypeError, ValueError):
        return 800


def to_kelvin(celsius):
    """°C -> the integer Kelvin the watch expects (it converts back as K - 273)."""
    return round(float(celsius)) + 273


def _http_get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "asteroid-docking-bay"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def geocode(city, _get=_http_get):
    """City name -> {city, lat, lon} via Open-Meteo geocoding (keyless), or None.
    The resolved name carries the country so 'Springfield' is disambiguable."""
    if not city or not city.strip():
        return None
    url = ("https://geocoding-api.open-meteo.com/v1/search?count=1&name="
           + urllib.parse.quote(city.strip()))
    try:
        results = (json.loads(_get(url)) or {}).get("results") or []
    except Exception:
        return None
    if not results:
        return None
    r = results[0]
    name = r.get("name") or city.strip()
    cc = r.get("country_code") or r.get("country")
    if cc and cc != name:
        name = f"{name}, {cc}"
    return {"city": name, "lat": r.get("latitude"), "lon": r.get("longitude")}


def parse_forecast(doc):
    """Open-Meteo forecast JSON -> up to MAX_DAYS of
    {id, min_c, max_c, min_k, max_k}. Skips days with a missing temperature."""
    daily = (doc or {}).get("daily") or {}
    codes = daily.get("weather_code") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    days = []
    for i in range(min(MAX_DAYS, len(codes), len(tmax), len(tmin))):
        if tmin[i] is None or tmax[i] is None:
            continue
        days.append({"id": wmo_to_owm(codes[i]),
                     "min_c": round(float(tmin[i])), "max_c": round(float(tmax[i])),
                     "min_k": to_kelvin(tmin[i]), "max_k": to_kelvin(tmax[i])})
    return days


def fetch_forecast(lat, lon, _get=_http_get):
    """Fetch + parse the 5-day forecast for a location. [] on any failure."""
    if lat is None or lon is None:
        return []
    url = ("https://api.open-meteo.com/v1/forecast?timezone=auto"
           f"&latitude={lat}&longitude={lon}"
           "&daily=weather_code,temperature_2m_max,temperature_2m_min")
    try:
        return parse_forecast(json.loads(_get(url)))
    except Exception:
        return []


def parse_watch_weather(text):
    """Parse `dconf dump /org/asteroidos/weather/` into what is stored on the
    watch: {city, timestamp, days:[{id, min_k, max_k}]}. Temps stay Kelvin (as
    stored); ints may carry a `uint32`/`int32` prefix. Empty dump → empty days."""
    section, city, ts, days = "", None, None, {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip("/")     # "" for the root, "day0" etc.
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip("'")
        def _int(s):
            try:
                return int(s.split()[-1])       # "uint32 800" -> 800
            except (ValueError, IndexError):
                return None
        if section == "":
            if k == "city-name":
                city = v
            elif k == "timestamp-day0":
                ts = _int(v)
        elif section.startswith("day"):
            idx = _int(section[3:])
            if idx is None:
                continue
            d = days.setdefault(idx, {})
            if k == "id":
                d["id"] = _int(v)
            elif k == "min-temp":
                d["min_k"] = _int(v)
            elif k == "max-temp":
                d["max_k"] = _int(v)
    return {"city": city, "timestamp": ts,
            "days": [days[i] for i in sorted(days)]}


def dconf_writeset(city, days, ts=None):
    """The (key, type, value) triples to write to a watch's weather dconf.
    type is 'string' or 'int'; ts defaults to now (epoch s) = the date of day0."""
    ts = int(ts if ts is not None else time.time())
    out = [(f"{WEATHER_ROOT}/city-name", "string", city or ""),
           (f"{WEATHER_ROOT}/timestamp-day0", "int", ts)]
    for i, d in enumerate(days[:MAX_DAYS]):
        out.append((f"{WEATHER_ROOT}/day{i}/id", "int", int(d["id"])))
        out.append((f"{WEATHER_ROOT}/day{i}/min-temp", "int", int(d["min_k"])))
        out.append((f"{WEATHER_ROOT}/day{i}/max-temp", "int", int(d["max_k"])))
    return out
