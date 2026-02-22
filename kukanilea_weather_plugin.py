#!/usr/bin/env python3
"""
kukanilea_weather_plugin.py
Minimal "tool" for the local chat: answers simple Berlin weather questions.

Source: Open-Meteo (no key). Requires internet.
If offline, returns a graceful message.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

BERLIN = {"lat": 52.5200, "lon": 13.4050, "name": "Berlin"}


def _http_json(url: str, timeout: int = 8) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "KUKANILEA/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_berlin_weather_now() -> str:
    # Open-Meteo current weather
    base = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": BERLIN["lat"],
        "longitude": BERLIN["lon"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "timezone": "Europe/Berlin",
    }
    url = base + "?" + urllib.parse.urlencode(params)
    data = _http_json(url)
    cur = data.get("current") or {}
    t = cur.get("temperature_2m")
    feels = cur.get("apparent_temperature")
    hum = cur.get("relative_humidity_2m")
    wind = cur.get("wind_speed_10m")
    precip = cur.get("precipitation")
    ts = cur.get("time")
    parts = []
    if ts:
        parts.append(f"{BERLIN['name']} ({ts})")
    else:
        parts.append(BERLIN["name"])
    if t is not None:
        parts.append(f"{t}°C")
    if feels is not None:
        parts.append(f"gefühlt {feels}°C")
    if hum is not None:
        parts.append(f"{hum}% rF")
    if wind is not None:
        parts.append(f"Wind {wind} km/h")
    if precip is not None:
        parts.append(f"Niederschlag {precip} mm")
    return " · ".join(parts)


def answer_weather_if_applicable(question: str) -> str | None:
    q = (question or "").strip().lower()
    triggers = ("wetter", "temperatur", "regen", "wind", "wie warm", "wie kalt")
    if not any(t in q for t in triggers):
        return None
    if "berlin" not in q:
        # keep it conservative: only Berlin for now
        q += " berlin"
    try:
        return get_berlin_weather_now()
    except Exception:
        return "Ich kann das Wetter gerade nicht abrufen (kein Internet oder Open‑Meteo nicht erreichbar)."
