"""
Astronaut Health Data Shuffler
Version: 1.3.5

Continuous, time-based synthetic physiological simulation with:
- Current ISS position (Where the ISS at? API)
- NASA DONKI space-weather event context
- NASA OSDR RadLab historical ISS radiation measurements
- Cumulative dose integration from timestamped dose-rate measurements

Standard library only.
"""

import json
import math
import random
import time
import threading
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

SIMULATION_MODE = "NORMAL"
SUPPORTED_MODES = ("NORMAL", "REST", "EXERCISE", "SLEEP", "ABNORMAL")

# Abnormalities are synthetic test scenarios, not medical diagnoses.
SUPPORTED_ABNORMALITIES = (
    "HYPERGLYCEMIA",
    "HYPOGLYCEMIA",
    "TACHYCARDIA",
    "BRADYCARDIA",
    "HYPOTHERMIA",
    "FEVER",
    "HYPOXEMIA",
    "TACHYPNEA",
    "HYPERTENSION",
    "HYPOTENSION",
)

# Mutually exclusive scenario pairs cannot be enabled together.
_ABNORMALITY_CONFLICTS = (
    frozenset(("HYPERGLYCEMIA", "HYPOGLYCEMIA")),
    frozenset(("TACHYCARDIA", "BRADYCARDIA")),
    frozenset(("HYPOTHERMIA", "FEVER")),
    frozenset(("HYPERTENSION", "HYPOTENSION")),
)

_active_abnormalities = ()
_abnormality_targets = {}


ECG_SAMPLE_RATE_HZ = 500

ASTRONAUT_PROFILE = {
    "body_mass": 75.0,
    "resting_hr": 68.0,
    "baseline_hrv": 65.0,
    "baseline_skin_temp": 34.5,
}

# All intervals are seconds. API polling is intentionally independent
# from physiological sampling and ECG sampling.
UPDATE_INTERVALS = {
    # Physiological
    "heart_rate": 1.0,
    "systolic_bp": 60.0,
    "diastolic_bp": 60.0,
    "heart_rate_variability": 60.0,
    "respiratory_rate": 1.0,
    "spo2": 2.0,
    "body_temperature": 10.0,
    "skin_temperature": 10.0,
    "blood_glucose": 60.0,
    "stress_level": 10.0,
    "sleep_duration": 60.0,
    "sleep_quality": 60.0,
    "physical_activity": 1.0,
    "body_mass": 3600.0,
    "hydration_level": 60.0,

    # Environmental
    "cabin_temperature": 5.0,
    "cabin_pressure": 1.0,
    "cabin_humidity": 5.0,
    "cabin_oxygen": 5.0,
    "cabin_co2": 5.0,
    "microgravity_level": 0.1,
    "cabin_air_quality": 10.0,
}


# Metadata describes the synthetic signal and its units. Metrics whose
# measurement definition/context is incomplete are explicitly marked so
# downstream health logic can decide whether they are assessable.
MEASUREMENT_INFO = {
    "heart_rate": {"unit": "bpm", "definition": "Heart rate"},
    "systolic_bp": {"unit": "mmHg", "definition": "Systolic blood pressure"},
    "diastolic_bp": {"unit": "mmHg", "definition": "Diastolic blood pressure"},
    "heart_rate_variability": {
        "unit": "ms", "definition": "Synthetic HRV value; SDNN/RMSSD method is not specified",
        "interpretation_ready": False,
    },
    "respiratory_rate": {"unit": "breaths/min", "definition": "Respiratory rate"},
    "spo2": {"unit": "%", "definition": "Peripheral oxygen saturation (simulated)"},
    "body_temperature": {"unit": "°C", "definition": "Simulated core body temperature"},
    "skin_temperature": {"unit": "°C", "definition": "Simulated skin temperature"},
    "blood_glucose": {
        "unit": "mg/dL", "definition": "Synthetic blood glucose concentration",
        "context": "Meal timing and fasting status are not modelled",
        "interpretation_ready": False,
    },
    "stress_level": {
        "unit": "index", "definition": "Synthetic relative stress index (0-100)",
        "interpretation_ready": False,
    },
    "sleep_duration": {"unit": "h", "definition": "Accumulated simulated sleep duration"},
    "sleep_quality": {
        "unit": "index", "definition": "Synthetic sleep quality index (0-100)",
        "interpretation_ready": False,
    },
    "physical_activity": {
        "unit": "simulation_index", "definition": "Synthetic activity index (0-25); not MET",
        "interpretation_ready": False,
    },
    "body_mass": {"unit": "kg", "definition": "Configured astronaut body mass"},
    "hydration_level": {
        "unit": "index", "definition": "Synthetic hydration index (0-100); not a direct clinical measurement",
        "interpretation_ready": False,
    },
    "cabin_temperature": {"unit": "°C", "definition": "Simulated cabin air temperature"},
    "cabin_pressure": {"unit": "kPa", "definition": "Simulated cabin pressure"},
    "cabin_humidity": {"unit": "%", "definition": "Simulated relative humidity"},
    "cabin_oxygen": {
        "unit": "%", "definition": "Simulated oxygen fraction by volume; not oxygen partial pressure",
        "interpretation_ready": False,
    },
    "cabin_co2": {"unit": "ppm", "definition": "Simulated cabin carbon dioxide concentration"},
    "microgravity_level": {
        "unit": "simulation_index", "definition": "Synthetic microgravity index; not measured acceleration",
        "interpretation_ready": False,
    },
    "cabin_air_quality": {
        "unit": "index", "definition": "Synthetic air quality index (0-100)",
        "interpretation_ready": False,
    },
}

# Per-field metadata is updated only when that field is actually published.
measurement_metadata = {}

API_CONFIG = {
    "iss_position_url": "https://api.wheretheiss.at/v1/satellites/25544",
    "iss_poll_interval_seconds": 10.0,

    "nasa_donki_base_url": "https://api.nasa.gov/DONKI",
    "nasa_donki_poll_interval_seconds": 900.0,
    "nasa_donki_lookback_days": 7,

    "radlab_url": "https://visualization.osdr.nasa.gov/radlab/api/",
    "radlab_poll_interval_seconds": 3600.0,
    "radlab_lookback_hours": 24,
    # Do not integrate across large gaps: doing so would invent exposure.
    "radlab_max_integration_gap_seconds": 21600.0,

    "http_timeout_seconds": 12.0,
    "user_agent": "AstronautHealthDataShuffler/1.3.5",
    "api_keys_file": "api_keys.json",
}

# NASA API default is 1,000 requests/hour per key; DEMO_KEY is
# substantially more restrictive. This client deliberately makes
# only three DONKI requests per 15-minute refresh cycle.
NASA_DONKI_ENDPOINTS = ("SEP", "CME", "GST")


# ============================================================
# VALIDATION
# ============================================================

def validate_number(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric.")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")


def validate_profile():
    if not isinstance(ASTRONAUT_PROFILE, dict):
        raise TypeError("ASTRONAUT_PROFILE must be a dictionary.")

    required = {
        "body_mass": (20, 300),
        "resting_hr": (40, 100),
        "baseline_hrv": (10, 200),
        "baseline_skin_temp": (25, 38),
    }

    for key, (minimum, maximum) in required.items():
        if key not in ASTRONAUT_PROFILE:
            raise ValueError(f"Missing profile parameter: {key}")
        validate_number(key, ASTRONAUT_PROFILE[key], minimum, maximum)


def validate_mode():
    if not isinstance(SIMULATION_MODE, str):
        raise TypeError("SIMULATION_MODE must be a string.")
    if SIMULATION_MODE not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported simulation mode: {SIMULATION_MODE}")
    if SIMULATION_MODE == "ABNORMAL" and not _active_abnormalities:
        raise ValueError("ABNORMAL mode requires at least one abnormality.")
    if SIMULATION_MODE != "ABNORMAL" and _active_abnormalities:
        raise ValueError("Abnormalities can only be active in ABNORMAL mode.")


def set_simulation_scenario(mode="NORMAL", abnormalities=None):
    """Select NORMAL/REST/EXERCISE/SLEEP or one/more ABNORMAL test cases.

    Examples:
        set_simulation_scenario("NORMAL")
        set_simulation_scenario("SLEEP")
        set_simulation_scenario("ABNORMAL", ["TACHYCARDIA", "HYPERGLYCEMIA"])

    Scenario labels describe generated test data; they are not diagnoses.
    """
    global SIMULATION_MODE, _active_abnormalities, _abnormality_targets

    if not isinstance(mode, str):
        raise TypeError("mode must be a string.")
    mode = mode.strip().upper()
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported simulation mode: {mode}")

    if abnormalities is None:
        selected = ()
    elif isinstance(abnormalities, str):
        selected = (abnormalities.strip().upper(),)
    else:
        selected = tuple(str(item).strip().upper() for item in abnormalities)

    if len(set(selected)) != len(selected):
        raise ValueError("Duplicate abnormalities are not allowed.")
    unknown = sorted(set(selected) - set(SUPPORTED_ABNORMALITIES))
    if unknown:
        raise ValueError(f"Unsupported abnormality: {', '.join(unknown)}")
    if mode == "ABNORMAL" and not selected:
        raise ValueError("ABNORMAL mode requires at least one abnormality.")
    if mode != "ABNORMAL" and selected:
        raise ValueError("abnormalities must only be supplied in ABNORMAL mode.")

    selected_set = set(selected)
    for conflict in _ABNORMALITY_CONFLICTS:
        if conflict.issubset(selected_set):
            raise ValueError("Conflicting abnormalities cannot be combined: "
                             + " / ".join(sorted(conflict)))

    targets = {}
    for item in selected:
        if item == "HYPERGLYCEMIA":
            targets["blood_glucose"] = random_value(145, 170, 1)
        elif item == "HYPOGLYCEMIA":
            targets["blood_glucose"] = random_value(65, 69, 1)
        elif item == "TACHYCARDIA":
            targets["heart_rate"] = random_value(105, 115, 1)
        elif item == "BRADYCARDIA":
            targets["heart_rate"] = random_value(48, 55, 1)
        elif item == "HYPOTHERMIA":
            targets["body_temperature"] = random_value(34.2, 34.8, 2)
        elif item == "FEVER":
            targets["body_temperature"] = random_value(37.8, 38.3, 2)
        elif item == "HYPOXEMIA":
            targets["spo2"] = random_value(92, 94, 1)
        elif item == "TACHYPNEA":
            targets["respiratory_rate"] = random_value(22, 25, 1)
        elif item == "HYPERTENSION":
            targets["systolic_bp"] = random_value(130, 145, 1)
            targets["diastolic_bp"] = random_value(80, 90, 1)
        elif item == "HYPOTENSION":
            targets["systolic_bp"] = random_value(90, 99, 1)
            targets["diastolic_bp"] = random_value(55, 64, 1)

    SIMULATION_MODE = mode
    _active_abnormalities = selected
    _abnormality_targets = targets

    # A newly selected abnormal test case should be visible in the very
    # next snapshot, rather than waiting for the previous sampling interval.
    # The injected scenario is a controlled test-state change, not a diagnosis.
    for key, target in targets.items():
        _state[key] = target
        _last_publish.pop(key, None)

    return get_simulation_scenario()


def get_simulation_scenario():
    """Return a copy of the currently selected synthetic scenario."""
    return {
        "mode": SIMULATION_MODE,
        "abnormalities": list(_active_abnormalities),
        "scenario_type": "SYNTHETIC_TEST_DATA",
    }


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def smooth_value(current, target, dt, time_constant):
    """Exponential smoothing for gradual physiological changes."""
    if dt <= 0:
        return current
    alpha = 1.0 - math.exp(-dt / time_constant)
    return current + (target - current) * alpha


def random_value(minimum, maximum, decimals=1):
    return round(random.uniform(minimum, maximum), decimals)


def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(timestamp=None):
    if timestamp is None:
        timestamp = utc_now()
    return timestamp.astimezone(timezone.utc).isoformat()


def parse_timestamp(value):
    """Parse an ISO-8601 timestamp or Unix timestamp into UTC datetime."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if not isinstance(value, str):
        raise ValueError("Unsupported timestamp format.")

    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


# ============================================================
# API KEY CONFIGURATION
# ============================================================

def load_api_keys():
    """
    Load secrets from api_keys.json, located beside this Python file.

    Expected format:
    {
        "nasa_api_key": "YOUR_NASA_API_KEY"
    }

    The file is optional. Without it, NASA requests are skipped instead
    of silently falling back to the heavily rate-limited DEMO_KEY.
    """
    config_path = Path(__file__).resolve().parent / API_CONFIG["api_keys_file"]

    if not config_path.is_file():
        return {}, f"API key file not found: {config_path.name}"

    try:
        with config_path.open("r", encoding="utf-8") as file:
            keys = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"Could not read API key file: {exc}"

    if not isinstance(keys, dict):
        return {}, "API key file must contain a JSON object."

    nasa_key = keys.get("nasa_api_key")
    if nasa_key is not None:
        if not isinstance(nasa_key, str) or not nasa_key.strip():
            return {}, "nasa_api_key must be a non-empty string."
        nasa_key = nasa_key.strip()

    return {"nasa_api_key": nasa_key}, None


_api_keys, _api_key_load_error = load_api_keys()


# ============================================================
# HTTP / API HELPERS
# ============================================================

def http_get_json(url, params=None):
    """Perform a bounded-timeout GET request and decode a JSON response."""
    if params:
        query = urlencode(params)
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": API_CONFIG["user_agent"],
        },
        method="GET",
    )

    with urlopen(
        request,
        timeout=API_CONFIG["http_timeout_seconds"]
    ) as response:
        payload = response.read()
        decoded = payload.decode("utf-8")
        return json.loads(decoded), dict(response.headers.items())


def retry_after_seconds(headers):
    """Read Retry-After as seconds or an HTTP date."""
    if not headers:
        return None

    value = headers.get("Retry-After") or headers.get("retry-after")
    if not value:
        return None

    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            retry_time = parsedate_to_datetime(value)
            if retry_time.tzinfo is None:
                retry_time = retry_time.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_time - utc_now()).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def api_error_message(exc):
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, URLError):
        return f"Network error: {exc.reason}"
    return str(exc)


# ============================================================
# INTERNAL SIMULATION STATE
# ============================================================

_state = {
    "physical_activity": 5.0,
    "sleep_duration": 7.8,
    "sleep_quality": 88.0,
    "hydration_level": 95.0,
    "stress_level": 15.0,

    "heart_rate": ASTRONAUT_PROFILE["resting_hr"],
    "systolic_bp": 112.0,
    "diastolic_bp": 72.0,
    "heart_rate_variability": ASTRONAUT_PROFILE["baseline_hrv"],

    "respiratory_rate": 13.0,
    "spo2": 98.5,

    "body_temperature": 36.6,
    "skin_temperature": ASTRONAUT_PROFILE["baseline_skin_temp"],

    "blood_glucose": 90.0,
}

_environment_state = {
    "cabin_temperature": 22.5,
    "cabin_pressure": 101.3,
    "cabin_humidity": 45.0,
    "cabin_oxygen": 20.9,
    "cabin_co2": 900.0,
    "microgravity_level": 0.001,
    "cabin_air_quality": 95.0,
}

_last_state_update = time.monotonic()
_last_environment_update = time.monotonic()
_last_publish = {}


# ============================================================
# PHYSIOLOGICAL MODEL
# ============================================================

def advance_physiological_state(dt):
    """Advance physiological state using previous state and correlations."""
    if dt <= 0:
        return

    dt = min(dt, 5.0)

    activity = _state["physical_activity"]
    activity_targets = {
        "NORMAL": 5.0,
        "REST": 1.5,
        "EXERCISE": 16.0,
        "SLEEP": 0.5,
        "ABNORMAL": 5.0,
    }
    activity_target = activity_targets[SIMULATION_MODE]
    activity += random.gauss(0, 0.35 * math.sqrt(dt))
    activity += (activity_target - activity) * dt / 20.0
    activity = clamp(activity, 0, 25)
    _state["physical_activity"] = activity

    sleep_quality = _state["sleep_quality"]
    target_stress = (
        12.0
        + (90.0 - sleep_quality) * 0.4
        + activity * 0.35
    )
    target_stress += random.gauss(0, 1.0)
    target_stress = clamp(target_stress, 5, 40)

    _state["stress_level"] = smooth_value(
        _state["stress_level"], target_stress, dt, 45.0
    )

    hydration = _state["hydration_level"]
    hydration += random.gauss(0, 0.025 * math.sqrt(dt))
    hydration -= 0.002 * dt
    _state["hydration_level"] = clamp(hydration, 85, 100)

    stress = _state["stress_level"]

    target_hr = (
        ASTRONAUT_PROFILE["resting_hr"]
        + activity * 0.8
        + stress * 0.15
        + (95.0 - _state["hydration_level"]) * 0.3
    )
    target_hr = clamp(target_hr, 55, 100)

    _state["heart_rate"] = smooth_value(
        _state["heart_rate"], target_hr, dt, 3.0
    )

    target_systolic = 112.0 + stress * 0.08 + activity * 0.08
    target_diastolic = 72.0 + stress * 0.05 + activity * 0.025

    _state["systolic_bp"] = smooth_value(
        _state["systolic_bp"], target_systolic, dt, 15.0
    )
    _state["diastolic_bp"] = smooth_value(
        _state["diastolic_bp"], target_diastolic, dt, 15.0
    )

    target_hrv = (
        ASTRONAUT_PROFILE["baseline_hrv"]
        - stress * 0.45
        - activity * 0.25
    )
    _state["heart_rate_variability"] = smooth_value(
        _state["heart_rate_variability"], target_hrv, dt, 20.0
    )

    target_rr = 13.0 + activity * 0.1 + stress * 0.025
    _state["respiratory_rate"] = smooth_value(
        _state["respiratory_rate"], target_rr, dt, 5.0
    )

    target_spo2 = 98.5 - max(0, stress - 25) * 0.015
    _state["spo2"] = smooth_value(
        _state["spo2"], target_spo2, dt, 8.0
    )

    target_temp = 36.6 + activity * 0.004 + stress * 0.001
    _state["body_temperature"] = smooth_value(
        _state["body_temperature"], target_temp, dt, 60.0
    )

    target_skin_temp = (
        ASTRONAUT_PROFILE["baseline_skin_temp"] + activity * 0.01
    )
    _state["skin_temperature"] = smooth_value(
        _state["skin_temperature"], target_skin_temp, dt, 20.0
    )

    target_glucose = 90.0 + stress * 0.12 - activity * 0.08
    _state["blood_glucose"] = smooth_value(
        _state["blood_glucose"], target_glucose, dt, 120.0
    )


# ============================================================
# ENVIRONMENTAL MODEL
# ============================================================

def advance_environmental_state(dt):
    if dt <= 0:
        return

    dt = min(dt, 5.0)

    changes = {
        "cabin_temperature": (0.015, 21, 24),
        "cabin_pressure": (0.008, 99, 103),
        "cabin_humidity": (0.04, 35, 55),
        "cabin_oxygen": (0.003, 20.5, 21.0),
        "cabin_co2": (0.8, 500, 1500),
        "microgravity_level": (0.00001, 0.0001, 0.01),
        "cabin_air_quality": (0.015, 90, 100),
    }

    for key, (noise, minimum, maximum) in changes.items():
        current = _environment_state[key]
        current += random.gauss(0, noise * math.sqrt(dt))
        _environment_state[key] = clamp(current, minimum, maximum)


def apply_scenario_overrides(dt):
    """Move selected synthetic measurements toward safe test-case targets."""
    if SIMULATION_MODE == "ABNORMAL":
        time_constants = {
            "heart_rate": 12.0,
            "blood_glucose": 90.0,
            "body_temperature": 45.0,
            "spo2": 20.0,
            "respiratory_rate": 12.0,
            "systolic_bp": 25.0,
            "diastolic_bp": 25.0,
        }
        for key, target in _abnormality_targets.items():
            current = _state[key]
            _state[key] = smooth_value(
                current, target, dt, time_constants.get(key, 20.0)
            )

    if SIMULATION_MODE == "SLEEP":
        _state["sleep_duration"] = min(12.0, _state["sleep_duration"] + dt / 3600.0)


# ============================================================
# DATA SAMPLING
# ============================================================

def publish_due_values(target, source, now):
    """Publish due values and record the timestamp of each actual update."""
    for key, interval in UPDATE_INTERVALS.items():
        if key not in source:
            continue

        last_time = _last_publish.get(key)
        if last_time is None or now - last_time >= interval:
            target[key] = source[key]
            _last_publish[key] = now
            info = MEASUREMENT_INFO.get(key, {})
            measurement_metadata[key] = {
                "measured_at": iso_utc(),
                "unit": info.get("unit", "unknown"),
                "definition": info.get("definition", ""),
                "interpretation_ready": info.get("interpretation_ready", True),
            }
            if "context" in info:
                measurement_metadata[key]["context"] = info["context"]


# ============================================================
# ECG SIGNAL GENERATOR
# ============================================================

_ecg_phase = 0.0


def _circular_gaussian(phase, center, width):
    distance = (phase - center + 0.5) % 1.0 - 0.5
    return math.exp(-0.5 * (distance / width) ** 2)


def _generate_ecg_point(phase):
    """Simplified synthetic P-QRS-T waveform; visualization only."""
    p_wave = 0.12 * _circular_gaussian(phase, 0.18, 0.025)
    q_wave = -0.15 * _circular_gaussian(phase, 0.275, 0.008)
    r_wave = 1.0 * _circular_gaussian(phase, 0.30, 0.006)
    s_wave = -0.25 * _circular_gaussian(phase, 0.325, 0.010)
    t_wave = 0.30 * _circular_gaussian(phase, 0.55, 0.050)
    noise = random.gauss(0, 0.005)
    return p_wave + q_wave + r_wave + s_wave + t_wave + noise


def get_ecg_samples(sample_count=25):
    """
    Generate ECG samples at 500 Hz.
    A sample_count of 25 represents 50 ms of signal.
    Output values are millivolts (mV), not diagnostic ECG data.
    """
    global _ecg_phase

    if isinstance(sample_count, bool) or not isinstance(sample_count, int):
        raise TypeError("sample_count must be an integer.")
    if not 1 <= sample_count <= 5000:
        raise ValueError("sample_count must be between 1 and 5000.")

    bpm = physiological_data.get("heart_rate", 68.0)
    samples = []
    phase_increment = bpm / (60.0 * ECG_SAMPLE_RATE_HZ)

    for _ in range(sample_count):
        samples.append(round(_generate_ecg_point(_ecg_phase), 5))
        _ecg_phase = (_ecg_phase + phase_increment) % 1.0

    return samples


# ============================================================
# ISS POSITION API
# ============================================================

iss_position_data = {
    "latitude": None,
    "longitude": None,
    "altitude_km": None,
    "velocity_km_h": None,
    "visibility": None,
    "timestamp": None,
    "last_api_update": None,
    "data_source": "api.wheretheiss.at",
    "status": "NOT_YET_FETCHED",
    "last_error": None,
}

_iss_last_attempt = 0.0
_iss_failure_backoff = 0.0


def update_iss_position(force=False):
    """Fetch current ISS position with cache and failure backoff."""
    global _iss_last_attempt, _iss_failure_backoff

    now_mono = time.monotonic()
    if not force:
        wait_for = max(
            API_CONFIG["iss_poll_interval_seconds"],
            _iss_failure_backoff,
        )
        if now_mono - _iss_last_attempt < wait_for:
            return False

    _iss_last_attempt = now_mono

    try:
        payload, _headers = http_get_json(API_CONFIG["iss_position_url"])

        required = ("latitude", "longitude", "altitude", "timestamp")
        if not isinstance(payload, dict) or any(k not in payload for k in required):
            raise ValueError("ISS API response is missing required fields.")

        latitude = float(payload["latitude"])
        longitude = float(payload["longitude"])
        altitude = float(payload["altitude"])
        timestamp = float(payload["timestamp"])

        validate_number("ISS latitude", latitude, -90, 90)
        validate_number("ISS longitude", longitude, -180, 180)
        validate_number("ISS altitude", altitude, 0, 1000)
        validate_number("ISS timestamp", timestamp, 0, 10000000000)

        velocity = payload.get("velocity")
        if velocity is not None:
            velocity = float(velocity)
            validate_number("ISS velocity", velocity, 0, 100000)

        iss_position_data.update({
            "latitude": latitude,
            "longitude": longitude,
            "altitude_km": altitude,
            "velocity_km_h": velocity,
            "visibility": payload.get("visibility"),
            "timestamp": iso_utc(datetime.fromtimestamp(timestamp, timezone.utc)),
            "last_api_update": iso_utc(),
            "status": "OK",
            "last_error": None,
        })

        _iss_failure_backoff = 0.0
        return True

    except (HTTPError, URLError, TimeoutError, OSError, ValueError,
            TypeError, json.JSONDecodeError) as exc:
        iss_position_data["status"] = "STALE" if iss_position_data["timestamp"] else "ERROR"
        iss_position_data["last_error"] = api_error_message(exc)
        _iss_failure_backoff = min(
            300.0,
            max(30.0, _iss_failure_backoff * 2.0),
        )
        return False


# ============================================================
# NASA DONKI SPACE WEATHER API
# ============================================================

space_weather_data = {
    "sep_events": [],
    "cme_events": [],
    "geomagnetic_storms": [],
    "last_api_update": None,
    "data_source": "NASA DONKI",
    "status": "NOT_YET_FETCHED",
    "last_error": None,
    "api_rate_limit": None,
    "api_rate_remaining": None,
}

_donki_last_attempt = 0.0
_donki_failure_backoff = 0.0


def _donki_date_range():
    end_date = utc_now().date()
    start_date = end_date - timedelta(
        days=API_CONFIG["nasa_donki_lookback_days"]
    )
    return start_date.isoformat(), end_date.isoformat()


def update_space_weather(force=False):
    """
    Fetch SEP, CME and GST event context from NASA DONKI.

    This is not a radiation dosimeter. DONKI event records are not
    converted into dose-rate values.
    """
    global _donki_last_attempt, _donki_failure_backoff

    nasa_key = _api_keys.get("nasa_api_key")
    if not nasa_key:
        space_weather_data["status"] = "DISABLED_NO_API_KEY"
        space_weather_data["last_error"] = (
            _api_key_load_error or "nasa_api_key is not configured."
        )
        return False

    now_mono = time.monotonic()
    wait_for = max(
        API_CONFIG["nasa_donki_poll_interval_seconds"],
        _donki_failure_backoff,
    )
    if not force and now_mono - _donki_last_attempt < wait_for:
        return False

    _donki_last_attempt = now_mono
    start_date, end_date = _donki_date_range()
    fetched = {}
    latest_rate_limit = None
    latest_rate_remaining = None

    try:
        for event_type in NASA_DONKI_ENDPOINTS:
            url = f"{API_CONFIG['nasa_donki_base_url']}/{event_type}"
            payload, headers = http_get_json(
                url,
                {
                    "startDate": start_date,
                    "endDate": end_date,
                    "api_key": nasa_key,
                },
            )

            if not isinstance(payload, list):
                raise ValueError(f"DONKI {event_type} response was not a list.")

            fetched[event_type] = payload
            latest_rate_limit = (
                headers.get("X-RateLimit-Limit")
                or headers.get("x-ratelimit-limit")
                or latest_rate_limit
            )
            latest_rate_remaining = (
                headers.get("X-RateLimit-Remaining")
                or headers.get("x-ratelimit-remaining")
                or latest_rate_remaining
            )

        # Replace event snapshots only after all three requests succeed.
        space_weather_data.update({
            "sep_events": fetched["SEP"],
            "cme_events": fetched["CME"],
            "geomagnetic_storms": fetched["GST"],
            "last_api_update": iso_utc(),
            "status": "OK",
            "last_error": None,
            "api_rate_limit": latest_rate_limit,
            "api_rate_remaining": latest_rate_remaining,
        })
        _donki_failure_backoff = 0.0
        return True

    except HTTPError as exc:
        retry_after = retry_after_seconds(exc.headers)
        if retry_after is not None:
            _donki_failure_backoff = min(3600.0, max(60.0, retry_after))
        else:
            _donki_failure_backoff = min(
                3600.0, max(60.0, _donki_failure_backoff * 2.0)
            )
        space_weather_data["status"] = (
            "STALE" if space_weather_data["last_api_update"] else "ERROR"
        )
        space_weather_data["last_error"] = api_error_message(exc)
        return False

    except (URLError, TimeoutError, OSError, ValueError, TypeError,
            json.JSONDecodeError) as exc:
        _donki_failure_backoff = min(
            3600.0, max(60.0, _donki_failure_backoff * 2.0)
        )
        space_weather_data["status"] = (
            "STALE" if space_weather_data["last_api_update"] else "ERROR"
        )
        space_weather_data["last_error"] = api_error_message(exc)
        return False


# ============================================================
# NASA OSDR RADLAB RADIATION DATA
# ============================================================

radiation_dosimetry_data = {
    "dose_rate_usv_h": None,
    "cumulative_dose_usv": 0.0,
    "cumulative_dose_msv": 0.0,
    "last_measurement_timestamp": None,
    "last_measurement_latitude": None,
    "last_measurement_longitude": None,
    "last_measurement_altitude_km": None,
    "instrument_id": None,
    "measurement_count": 0,
    "last_api_update": None,
    "data_source": "NASA OSDR RadLab",
    "data_temporality": "HISTORICAL_ARCHIVE_NOT_LIVE_TELEMETRY",
    "dose_rate_unit": "µSv/hour",
    "cumulative_dose_unit": "µSv",
    "measurement_status": "NO_MEASUREMENTS",
    "integration_status": "NO_DOSE_INTEGRATED",
    "last_error": None,
}

_radlab_last_attempt = 0.0
_radlab_failure_backoff = 0.0
_radlab_seen_timestamps = set()
_radlab_previous_sample = None
_radiation_session_start = utc_now()


def _radlab_query_url():
    """
    Request the latest historical ISS dose-equivalent-rate records.
    RadLab returns archived measurements, not a live telemetry stream.
    """
    since = utc_now() - timedelta(
        hours=API_CONFIG["radlab_lookback_hours"]
    )
    since_text = since.strftime("%Y-%m-%dT%H:%M")

    params = [
        ("spacecraft", "ISS"),
        ("timestamp>=", since_text),
        ("dose_equivalent_rate", ""),
        ("latitude", ""),
        ("longitude", ""),
        ("altitude", ""),
        ("format", "json"),
    ]
    return API_CONFIG["radlab_url"] + "?" + urlencode(params)


def _radlab_rows(payload):
    """Normalize common JSON response shapes into a list of row dictionaries."""
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("data", "results", "rows", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

        # Column-oriented JSON can be returned by tabular services.
        if payload and all(isinstance(value, list) for value in payload.values()):
            columns = list(payload.keys())
            lengths = {len(payload[column]) for column in columns}
            if len(lengths) == 1:
                return [
                    {column: payload[column][index] for column in columns}
                    for index in range(next(iter(lengths), 0))
                ]

    raise ValueError("Unrecognized RadLab JSON response structure.")


def _row_value(row, *names):
    lowered = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, "", "NA", "NaN", "nan"):
            return value
    return None


def _integrate_dose_sample(timestamp, dose_rate):
    """
    Trapezoidal integration of dose-equivalent rate.

    dose_rate is μSv/hour; elapsed seconds are converted to hours.
    Large gaps are deliberately not integrated, avoiding fabricated dose.
    """
    global _radlab_previous_sample

    current = (timestamp, dose_rate)
    previous = _radlab_previous_sample

    if previous is None:
        _radlab_previous_sample = current
        radiation_dosimetry_data["integration_status"] = "WAITING_FOR_NEXT_SAMPLE"
        return

    previous_timestamp, previous_rate = previous
    elapsed_seconds = (timestamp - previous_timestamp).total_seconds()

    if elapsed_seconds <= 0:
        return

    if elapsed_seconds <= API_CONFIG["radlab_max_integration_gap_seconds"]:
        average_rate = (previous_rate + dose_rate) / 2.0
        dose_increment_usv = average_rate * (elapsed_seconds / 3600.0)

        radiation_dosimetry_data["cumulative_dose_usv"] += dose_increment_usv
        radiation_dosimetry_data["cumulative_dose_msv"] = (
            radiation_dosimetry_data["cumulative_dose_usv"] / 1000.0
        )
        radiation_dosimetry_data["integration_status"] = "INTEGRATING"
    else:
        radiation_dosimetry_data["integration_status"] = (
            "GAP_NOT_INTEGRATED"
        )

    _radlab_previous_sample = current


def update_radiation_measurements(force=False):
    """
    Retrieve archived ISS dose-equivalent-rate records from NASA RadLab.

    Only new, timestamped records are processed. Repeated polling therefore
    does not double-count the same measurement.
    """
    global _radlab_last_attempt, _radlab_failure_backoff

    now_mono = time.monotonic()
    wait_for = max(
        API_CONFIG["radlab_poll_interval_seconds"],
        _radlab_failure_backoff,
    )
    if not force and now_mono - _radlab_last_attempt < wait_for:
        return False

    _radlab_last_attempt = now_mono

    try:
        url = _radlab_query_url()
        payload, _headers = http_get_json(url)
        rows = _radlab_rows(payload)

        parsed_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            timestamp_value = _row_value(row, "timestamp")
            rate_value = _row_value(row, "dose_equivalent_rate")
            if timestamp_value is None or rate_value is None:
                continue

            try:
                timestamp = parse_timestamp(timestamp_value)
                dose_rate = float(rate_value)
            except (ValueError, TypeError, OverflowError):
                continue

            if not math.isfinite(dose_rate) or dose_rate < 0:
                continue

            latitude = _row_value(row, "latitude")
            longitude = _row_value(row, "longitude")
            altitude = _row_value(row, "altitude")
            instrument_id = _row_value(row, "instrument_id")

            parsed_rows.append({
                "timestamp": timestamp,
                "dose_rate": dose_rate,
                "latitude": _optional_float(latitude),
                "longitude": _optional_float(longitude),
                "altitude_km": _optional_float(altitude),
                "instrument_id": instrument_id,
            })

        parsed_rows.sort(key=lambda item: item["timestamp"])

        new_count = 0
        for sample in parsed_rows:
            timestamp_key = sample["timestamp"].isoformat()
            if timestamp_key in _radlab_seen_timestamps:
                continue

            _radlab_seen_timestamps.add(timestamp_key)
            # Do not include archived exposure from before this program session.
            if sample["timestamp"] < _radiation_session_start:
                continue
            _integrate_dose_sample(
                sample["timestamp"],
                sample["dose_rate"],
            )

            radiation_dosimetry_data.update({
                "dose_rate_usv_h": sample["dose_rate"],
                "last_measurement_timestamp": timestamp_key,
                "last_measurement_latitude": sample["latitude"],
                "last_measurement_longitude": sample["longitude"],
                "last_measurement_altitude_km": sample["altitude_km"],
                "instrument_id": sample["instrument_id"],
                "measurement_count": (
                    radiation_dosimetry_data["measurement_count"] + 1
                ),
                "measurement_status": "HISTORICAL_MEASUREMENT",
                "measurement_temporality": "HISTORICAL_ARCHIVE_NOT_LIVE_TELEMETRY",
            })
            new_count += 1

        radiation_dosimetry_data["last_api_update"] = iso_utc()
        radiation_dosimetry_data["last_error"] = None

        if not parsed_rows:
            radiation_dosimetry_data["measurement_status"] = (
                "NO_MEASUREMENTS_IN_QUERY_WINDOW"
            )
        elif new_count == 0:
            radiation_dosimetry_data["measurement_status"] = (
                "NO_NEW_MEASUREMENTS"
            )

        _radlab_failure_backoff = 0.0
        return True

    except HTTPError as exc:
        retry_after = retry_after_seconds(exc.headers)
        _radlab_failure_backoff = min(
            21600.0,
            max(300.0, retry_after or _radlab_failure_backoff * 2.0),
        )
        radiation_dosimetry_data["measurement_status"] = (
            "STALE" if radiation_dosimetry_data["last_measurement_timestamp"]
            else "ERROR"
        )
        radiation_dosimetry_data["last_error"] = api_error_message(exc)
        return False

    except (URLError, TimeoutError, OSError, ValueError, TypeError,
            json.JSONDecodeError) as exc:
        _radlab_failure_backoff = min(
            21600.0, max(300.0, _radlab_failure_backoff * 2.0)
        )
        radiation_dosimetry_data["measurement_status"] = (
            "STALE" if radiation_dosimetry_data["last_measurement_timestamp"]
            else "ERROR"
        )
        radiation_dosimetry_data["last_error"] = api_error_message(exc)
        return False


def _optional_float(value):
    if value in (None, "", "NA", "NaN", "nan"):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


# ============================================================
# PUBLIC DATA VARIABLES
# ============================================================

physiological_data = {}
environmental_data = {}
system_data = {}

data = {
    "physiological_data": physiological_data,
    "environmental_data": environmental_data,
    "system_data": system_data,
    "iss_position_data": iss_position_data,
    "space_weather_data": space_weather_data,
    "radiation_dosimetry_data": radiation_dosimetry_data,
    "measurement_metadata": measurement_metadata,
}


# ============================================================
# MAIN REFRESH FUNCTION
# ============================================================

def refresh_data(include_remote=True):
    """
    Advance simulation and update remote data only when their own
    polling intervals are due. API polling never runs at ECG frequency.
    """
    global _last_state_update, _last_environment_update

    validate_mode()
    validate_profile()

    now = time.monotonic()
    physiological_dt = now - _last_state_update
    environmental_dt = now - _last_environment_update

    advance_physiological_state(physiological_dt)
    advance_environmental_state(environmental_dt)
    apply_scenario_overrides(physiological_dt)

    _last_state_update = now
    _last_environment_update = now

    physiological_source = {
        "heart_rate": round(_state["heart_rate"], 1),
        "systolic_bp": round(clamp(_state["systolic_bp"], 80, 160), 1),
        "diastolic_bp": round(clamp(_state["diastolic_bp"], 45, 100), 1),
        "heart_rate_variability": round(
            _state["heart_rate_variability"], 1
        ),
        "respiratory_rate": round(_state["respiratory_rate"], 1),
        "spo2": round(clamp(_state["spo2"], 90, 100), 1),
        "body_temperature": round(
            clamp(_state["body_temperature"], 34.0, 39.0), 2
        ),
        "skin_temperature": round(_state["skin_temperature"], 2),
        "blood_glucose": round(_state["blood_glucose"], 1),
        "stress_level": round(_state["stress_level"], 1),
        "sleep_duration": _state["sleep_duration"],
        "sleep_quality": round(_state["sleep_quality"], 1),
        "physical_activity": round(_state["physical_activity"], 1),
        "body_mass": ASTRONAUT_PROFILE["body_mass"],
        "hydration_level": round(_state["hydration_level"], 1),
    }

    publish_due_values(physiological_data, physiological_source, now)

    environmental_source = {
        "cabin_temperature": round(
            _environment_state["cabin_temperature"], 2
        ),
        "cabin_pressure": round(_environment_state["cabin_pressure"], 2),
        "cabin_humidity": round(_environment_state["cabin_humidity"], 1),
        "cabin_oxygen": round(_environment_state["cabin_oxygen"], 2),
        "cabin_co2": round(_environment_state["cabin_co2"], 1),
        "microgravity_level": round(
            _environment_state["microgravity_level"], 6
        ),
        "cabin_air_quality": round(
            _environment_state["cabin_air_quality"], 1
        ),
    }

    publish_due_values(environmental_data, environmental_source, now)

    # The legacy field is retained for consumers, but is no longer
    # filled with a fabricated radiation rate.
    environmental_data["radiation_dose_rate_usv_h"] = (
        radiation_dosimetry_data["dose_rate_usv_h"]
    )
    if radiation_dosimetry_data["last_measurement_timestamp"]:
        measurement_metadata["radiation_dose_rate_usv_h"] = {
            "measured_at": radiation_dosimetry_data["last_measurement_timestamp"],
            "unit": "µSv/hour",
            "definition": "NASA OSDR RadLab historical dose-equivalent rate; not live telemetry",
            "interpretation_ready": False,
            "data_temporality": "HISTORICAL_ARCHIVE_NOT_LIVE_TELEMETRY",
        }

    # Independent, cached API polling. Disabled during module import.
    if include_remote:
        update_iss_position()
        update_space_weather()
        update_radiation_measurements()

    system_data.update({
        "timestamp": iso_utc(),
        "simulation_mode": SIMULATION_MODE,
        "active_abnormalities": list(_active_abnormalities),
        "scenario_type": "SYNTHETIC_TEST_DATA",
        "data_source": "SIMULATED",
        "ecg_sample_rate_hz": ECG_SAMPLE_RATE_HZ,
        "api_status": {
            "iss_position": iss_position_data["status"],
            "nasa_donki": space_weather_data["status"],
            "nasa_radlab": radiation_dosimetry_data["measurement_status"],
        },
    })

    return data


# ============================================================
# SNAPSHOT FUNCTION
# ============================================================

def generate_snapshot():
    """Return copies of all currently published data."""
    refresh_data()

    return {
        "physiological_data": dict(physiological_data),
        "environmental_data": dict(environmental_data),
        "system_data": dict(system_data),
        "iss_position_data": dict(iss_position_data),
        "space_weather_data": {
            **space_weather_data,
            "sep_events": list(space_weather_data["sep_events"]),
            "cme_events": list(space_weather_data["cme_events"]),
            "geomagnetic_storms": list(
                space_weather_data["geomagnetic_storms"]
            ),
        },
        "radiation_dosimetry_data": dict(radiation_dosimetry_data),
        "measurement_metadata": {
            key: dict(value) for key, value in measurement_metadata.items()
        },
    }


# ============================================================
# INITIALIZATION
# ============================================================

# Initialize local simulation values without making network requests.
refresh_data(include_remote=False)


# ============================================================
# INTERACTIVE SIMULATION CLIENT
# ============================================================

def _print_client_help():
    """Display commands accepted by the interactive simulation client."""
    print("\nAvailable commands:")
    print("  normal                 Start normal simulation")
    print("  rest                   Switch to rest mode")
    print("  exercise               Switch to exercise mode")
    print("  sleep                  Switch to sleep mode")
    print("  abnormal <condition>   Activate an abnormal test scenario")
    print("                         Example: abnormal bradycardia")
    print("                         Multiple: abnormal bradycardia, hypoxemia")
    print("  status                 Show the active simulation scenario")
    print("  snapshot               Print the latest generated data as JSON")
    print("  help                   Show this help")
    print("  exit                   Stop the simulation client\n")
    print("Abnormality names:")
    print("  " + ", ".join(name.lower() for name in SUPPORTED_ABNORMALITIES))
    print()


def _parse_client_command(command):
    """Parse a client command and return (mode, abnormalities)."""
    parts = command.strip().split(maxsplit=1)
    if not parts:
        return None

    action = parts[0].lower()

    if action in ("normal", "rest", "exercise", "sleep"):
        if len(parts) != 1:
            raise ValueError(f"'{action}' does not accept an additional argument.")
        return action.upper(), None

    if action == "abnormal":
        if len(parts) != 2 or not parts[1].strip():
            raise ValueError(
                "Usage: abnormal <condition> "
                "(example: abnormal bradycardia)"
            )
        abnormalities = [
            item.strip().upper().replace("-", "_").replace(" ", "_")
            for item in parts[1].split(",")
            if item.strip()
        ]
        if not abnormalities:
            raise ValueError("At least one abnormality must be specified.")
        return "ABNORMAL", abnormalities

    return action, None


def _simulation_worker(stop_event, interval_seconds=1.0):
    """Keep synthetic measurements advancing while the client accepts commands."""
    while not stop_event.is_set():
        try:
            refresh_data(include_remote=True)
        except Exception as exc:
            # Keep the interactive client alive; expose the error to the console.
            print(f"\n[SIMULATION ERROR] {exc}")
        stop_event.wait(interval_seconds)


def run_client():
    """Run the interactive command-line client; not started when imported."""
    stop_event = threading.Event()
    worker = threading.Thread(
        target=_simulation_worker,
        args=(stop_event,),
        name="shuffler-simulation",
        daemon=True,
    )

    print("=" * 58)
    print("ASTRONAUT HEALTH DATA SHUFFLER — CLIENT v1.3.5")
    print("=" * 58)
    print("Starting in NORMAL mode. Synthetic data generation is active.")
    print("Type 'help' to see commands or 'exit' to stop.\n")

    # Explicitly establish the documented default scenario.
    set_simulation_scenario("NORMAL")
    worker.start()

    try:
        while True:
            try:
                command = input("shuffler> ").strip()
            except EOFError:
                print()
                break

            if not command:
                continue

            try:
                parsed = _parse_client_command(command)
                if parsed is None:
                    continue

                action, abnormalities = parsed

                if action == "HELP":
                    _print_client_help()
                elif action == "STATUS":
                    scenario = get_simulation_scenario()
                    print(
                        f"Active mode: {scenario['mode']} | "
                        f"Abnormalities: "
                        f"{', '.join(scenario['abnormalities']) or 'none'}"
                    )
                elif action == "SNAPSHOT":
                    snapshot = generate_snapshot()
                    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
                elif action in ("EXIT", "QUIT"):
                    break
                elif action in SUPPORTED_MODES:
                    scenario = set_simulation_scenario(
                        action, abnormalities=abnormalities
                    )
                    print(
                        f"[ACTIVE] Mode: {scenario['mode']} | "
                        f"Abnormalities: "
                        f"{', '.join(scenario['abnormalities']) or 'none'}"
                    )
                else:
                    print(
                        "Unknown command. Type 'help' to see available commands."
                    )

            except (TypeError, ValueError) as exc:
                print(f"[INVALID COMMAND] {exc}")

    except KeyboardInterrupt:
        print("\nInterrupt received.")
    finally:
        stop_event.set()
        worker.join(timeout=2.0)
        print("Simulation client stopped.")


if __name__ == "__main__":
    run_client()
