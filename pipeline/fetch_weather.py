"""
Fetch match-time weather forecasts from Open-Meteo (free, no API key).
Used to compute temperature, humidity, dew flag per venue.
"""
import logging
import time
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

VENUE_COORDS = {
    # Short names (used internally)
    "Wankhede Stadium":                              {"lat": 18.9388, "lon": 72.8258},
    "MA Chidambaram Stadium":                        {"lat": 13.0629, "lon": 80.2792},
    "M. Chinnaswamy Stadium":                        {"lat": 12.9791, "lon": 77.5496},
    "Eden Gardens":                                  {"lat": 22.5647, "lon": 88.3433},
    "Arun Jaitley Stadium":                          {"lat": 28.6364, "lon": 77.2173},
    "Narendra Modi Stadium":                         {"lat": 23.0908, "lon": 72.0846},
    "Rajiv Gandhi Intl Cricket Stadium":             {"lat": 17.4042, "lon": 78.5428},
    "Sawai Mansingh Stadium":                        {"lat": 26.8949, "lon": 75.8009},
    "BRSABV Ekana Cricket Stadium":                  {"lat": 26.8467, "lon": 80.9462},
    "Himachal Pradesh Cricket Association Stadium":  {"lat": 32.2198, "lon": 76.3234},
    "Maharaja Yadavindra Singh International Cricket Stadium": {"lat": 30.6942, "lon": 76.7336},
    # City-qualified names returned by the fixtures API
    "Wankhede Stadium, Mumbai":                      {"lat": 18.9388, "lon": 72.8258},
    "MA Chidambaram Stadium, Chennai":               {"lat": 13.0629, "lon": 80.2792},
    "M. Chinnaswamy Stadium, Bengaluru":             {"lat": 12.9791, "lon": 77.5496},
    "Eden Gardens, Kolkata":                         {"lat": 22.5647, "lon": 88.3433},
    "Arun Jaitley Stadium, Delhi":                   {"lat": 28.6364, "lon": 77.2173},
    "Narendra Modi Stadium, Ahmedabad":              {"lat": 23.0908, "lon": 72.0846},
    "Rajiv Gandhi Intl Cricket Stadium, Hyderabad":  {"lat": 17.4042, "lon": 78.5428},
    "Sawai Mansingh Stadium, Jaipur":                {"lat": 26.8949, "lon": 75.8009},
    "BRSABV Ekana Cricket Stadium, Lucknow":         {"lat": 26.8467, "lon": 80.9462},
    "Himachal Pradesh Cricket Association Stadium, Dharamsala": {"lat": 32.2198, "lon": 76.3234},
    "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur, New Chandigarh": {"lat": 30.6942, "lon": 76.7336},
    "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur": {"lat": 30.6942, "lon": 76.7336},
}

DEFAULT_MATCH_HOUR_UTC = 14
_REQUEST_TIMEOUT = (5, 20)   # (connect, read) seconds
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2           # seconds between attempts


def fetch_venue_weather(lat: float, lon: float, match_hour_utc: int = DEFAULT_MATCH_HOUR_UTC) -> dict:
    """Fetch hourly forecast and extract conditions at match time."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,windspeed_10m,dewpoint_2m",
        "forecast_days": 2,
        "timezone": "UTC",
    }
    _fallback = {"temperature": 28, "humidity": 60, "windspeed": 10, "dewpoint": 15, "dew_flag": False}
    data: dict = {}
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(OPEN_METEO_URL, params=params, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                logger.debug("Open-Meteo attempt %d failed (%s); retrying in %ds", attempt, e, _RETRY_BACKOFF)
                time.sleep(_RETRY_BACKOFF)
    else:
        logger.warning("Open-Meteo request failed after %d attempts: %s", _MAX_RETRIES, last_exc)
        return _fallback

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])
    winds = hourly.get("windspeed_10m", [])
    dewpoints = hourly.get("dewpoint_2m", [])

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target_time = f"{today}T{match_hour_utc:02d}:00"

    idx = None
    if target_time in times:
        idx = times.index(target_time)
    elif times:
        tomorrow = (datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        for i, t in enumerate(times):
            if t.startswith(today) and t >= target_time:
                idx = i
                break
        if idx is None:
            idx = 0

    def safe_get(lst, i, default):
        return lst[i] if lst and i < len(lst) else default

    temperature = safe_get(temps, idx, 28)
    humidity = safe_get(humidities, idx, 60)
    windspeed = safe_get(winds, idx, 10)
    dewpoint = safe_get(dewpoints, idx, 15)

    is_evening = match_hour_utc >= 13
    dew_flag = bool(humidity > 75 and is_evening)

    return {
        "temperature": round(temperature, 1),
        "humidity": int(humidity),
        "windspeed": round(windspeed, 1),
        "dewpoint": round(dewpoint, 1),
        "dew_flag": dew_flag,
    }


def fetch_all_venue_weather(venues: list[str] | None = None, match_hour_utc: int = DEFAULT_MATCH_HOUR_UTC) -> dict:
    """Fetch weather for all known venues (or a subset)."""
    targets = venues if venues else list(VENUE_COORDS.keys())
    results = {}
    for name in targets:
        coords = VENUE_COORDS.get(name)
        if not coords:
            # Try matching just the part before the first comma
            short = name.split(",")[0].strip()
            coords = VENUE_COORDS.get(short)
        if not coords:
            logger.warning("No coordinates found for venue: %s", name)
            results[name] = {"temperature": 28, "humidity": 60, "windspeed": 10, "dew_flag": False}
            continue
        logger.info("Fetching weather for %s", name)
        results[name] = fetch_venue_weather(coords["lat"], coords["lon"], match_hour_utc)
    return results


def run(venues: list[str] | None = None) -> dict:
    """Full weather pipeline: fetch for all venues → return."""
    weather = fetch_all_venue_weather(venues)
    logger.info("Fetched weather for %d venues", len(weather))
    return weather


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run()
    for venue, w in results.items():
        logger.info("%s: %.1f°C, %d%% humidity, dew=%s",
                    venue, w["temperature"], w["humidity"], w["dew_flag"])
