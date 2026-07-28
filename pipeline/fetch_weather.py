"""
Fetch match-time weather forecasts from Open-Meteo (free, no API key).
Used to compute temperature, humidity, dew flag per venue.
"""

import logging
import time
from datetime import UTC, datetime

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

VENUE_COORDS = {
    # Short names (used internally)
    "Wankhede Stadium": {"lat": 18.9388, "lon": 72.8258},
    "MA Chidambaram Stadium": {"lat": 13.0629, "lon": 80.2792},
    "M. Chinnaswamy Stadium": {"lat": 12.9791, "lon": 77.5496},
    "Eden Gardens": {"lat": 22.5647, "lon": 88.3433},
    "Arun Jaitley Stadium": {"lat": 28.6364, "lon": 77.2173},
    "Narendra Modi Stadium": {"lat": 23.0908, "lon": 72.0846},
    "Rajiv Gandhi Intl Cricket Stadium": {"lat": 17.4042, "lon": 78.5428},
    "Sawai Mansingh Stadium": {"lat": 26.8949, "lon": 75.8009},
    "BRSABV Ekana Cricket Stadium": {"lat": 26.8467, "lon": 80.9462},
    "Himachal Pradesh Cricket Association Stadium": {"lat": 32.2198, "lon": 76.3234},
    "Maharaja Yadavindra Singh International Cricket Stadium": {"lat": 30.6942, "lon": 76.7336},
    # City-qualified names returned by the fixtures API
    "Wankhede Stadium, Mumbai": {"lat": 18.9388, "lon": 72.8258},
    "MA Chidambaram Stadium, Chennai": {"lat": 13.0629, "lon": 80.2792},
    "M. Chinnaswamy Stadium, Bengaluru": {"lat": 12.9791, "lon": 77.5496},
    "Eden Gardens, Kolkata": {"lat": 22.5647, "lon": 88.3433},
    "Arun Jaitley Stadium, Delhi": {"lat": 28.6364, "lon": 77.2173},
    "Narendra Modi Stadium, Ahmedabad": {"lat": 23.0908, "lon": 72.0846},
    "Rajiv Gandhi Intl Cricket Stadium, Hyderabad": {"lat": 17.4042, "lon": 78.5428},
    "Sawai Mansingh Stadium, Jaipur": {"lat": 26.8949, "lon": 75.8009},
    "BRSABV Ekana Cricket Stadium, Lucknow": {"lat": 26.8467, "lon": 80.9462},
    "Himachal Pradesh Cricket Association Stadium, Dharamsala": {"lat": 32.2198, "lon": 76.3234},
    "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur, New Chandigarh": {
        "lat": 30.6942,
        "lon": 76.7336,
    },
    "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur": {"lat": 30.6942, "lon": 76.7336},
    "Rajiv Gandhi International Stadium, Hyderabad": {"lat": 17.4068, "lon": 78.5505},
}

DEFAULT_MATCH_HOUR_UTC = 14
_REQUEST_TIMEOUT = (20, 120)  # (connect, read) seconds - generous for GitHub Actions runners
_MAX_RETRIES = 4  # Increased to handle transient 502 errors
_RETRY_BACKOFF = 5  # seconds between attempts (increased for 502 recovery)
_REQUEST_HEADERS = {
    "User-Agent": "Wicket-Oracle/1.0 (+https://github.com/gmalbert/cricket)",
    "Accept": "application/json",
}

# Module-level session for connection pooling across all venue requests
_weather_session = None


def _get_session() -> requests.Session:
    """Get or create a persistent requests session with proper configuration."""
    global _weather_session
    if _weather_session is None:
        _weather_session = requests.Session()
        _weather_session.headers.update(_REQUEST_HEADERS)
    return _weather_session


def _reset_session() -> None:
    """Reset the module-level session. Only used for testing."""
    global _weather_session
    _weather_session = None


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
    session = _get_session()
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = session.get(OPEN_METEO_URL, params=params, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                # Use exponential backoff for server errors (502, 503, 504)
                is_server_error = (
                    hasattr(e, "response") and e.response is not None and e.response.status_code in (502, 503, 504)
                )
                wait_time = _RETRY_BACKOFF * (2 ** (attempt - 1)) if is_server_error else _RETRY_BACKOFF
                logger.debug("Open-Meteo attempt %d failed (%s); retrying in %ds", attempt, e, wait_time)
                time.sleep(wait_time)
    else:
        logger.warning("Open-Meteo request failed after %d attempts: %s", _MAX_RETRIES, last_exc)
        return _fallback

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])
    winds = hourly.get("windspeed_10m", [])
    dewpoints = hourly.get("dewpoint_2m", [])

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    target_time = f"{today}T{match_hour_utc:02d}:00"

    idx = None
    if target_time in times:
        idx = times.index(target_time)
    elif times:
        datetime.now(UTC).strftime("%Y-%m-%d")
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
        logger.info("%s: %.1f°C, %d%% humidity, dew=%s", venue, w["temperature"], w["humidity"], w["dew_flag"])
