
"""
Astronaut Health Data Shuffler
Version: 2.1.0

Multi-astronaut synthetic simulation with:
- Independent physiological state for each astronaut
- Independent simulation scenarios and profiles
- Shared ISS cabin environment
- Shared ISS position data
- Shared NASA DONKI space-weather context
- Shared NASA OSDR RadLab historical radiation data
- Per-astronaut synthetic ECG generation

Standard library only.

This is an educational simulation.
It is NOT a diagnostic medical system.
"""

import json
import math
import random
import threading
import time

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

VERSION = "2.1.0"

ASTRONAUT_IDS = ("user1", "user2", "user3")

SUPPORTED_MODES = (
    "NORMAL",
    "REST",
    "EXERCISE",
    "SLEEP",
    "ABNORMAL",
)

SUPPORTED_ABNORMALITIES = (
    "HYPERGLYCEMIA",
    "HYPOGLYCEMIA",
    "TACHYCARDIA",
    "BRADYCARDIA",
    "HYPOTHERMIA",
    "FEVER",
    "HYPOXEMIA",
    "SEVERE_HYPOXEMIA",
    "CARDIAC_ARREST",
    "TACHYPNEA",
    "HYPERTENSION",
    "HYPOTENSION",
)

_ABNORMALITY_CONFLICTS = (
    frozenset(("HYPERGLYCEMIA", "HYPOGLYCEMIA")),
    frozenset(("TACHYCARDIA", "BRADYCARDIA")),
    frozenset(("HYPOTHERMIA", "FEVER")),
    frozenset(("HYPERTENSION", "HYPOTENSION")),
    frozenset(("HYPOXEMIA", "SEVERE_HYPOXEMIA")),
    frozenset(("CARDIAC_ARREST", "TACHYCARDIA")),
    frozenset(("CARDIAC_ARREST", "BRADYCARDIA")),
)

ECG_SAMPLE_RATE_HZ = 500

DEFAULT_ASTRONAUT_PROFILE = {
    "body_mass": 75.0,
    "resting_hr": 68.0,
    "baseline_hrv": 65.0,
    "baseline_skin_temp": 34.5,
}

# Each astronaut starts with an independent copy.
ASTRONAUT_PROFILES = {
    astronaut_id: dict(DEFAULT_ASTRONAUT_PROFILE)
    for astronaut_id in ASTRONAUT_IDS
}

# Compatibility alias for older single-user code.
ASTRONAUT_PROFILE = ASTRONAUT_PROFILES["user1"]


UPDATE_INTERVALS = {
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

    "cabin_temperature": 5.0,
    "cabin_pressure": 1.0,
    "cabin_humidity": 5.0,
    "cabin_oxygen": 5.0,
    "cabin_co2": 5.0,
    "microgravity_level": 0.1,
    "cabin_air_quality": 10.0,
}


MEASUREMENT_INFO = {
    "heart_rate": {
        "unit": "bpm",
        "definition": "Heart rate",
    },
    "systolic_bp": {
        "unit": "mmHg",
        "definition": "Systolic blood pressure",
    },
    "diastolic_bp": {
        "unit": "mmHg",
        "definition": "Diastolic blood pressure",
    },
    "heart_rate_variability": {
        "unit": "ms",
        "definition": "Synthetic HRV value; SDNN/RMSSD method is not specified",
        "interpretation_ready": False,
    },
    "respiratory_rate": {
        "unit": "breaths/min",
        "definition": "Respiratory rate",
    },
    "spo2": {
        "unit": "%",
        "definition": "Peripheral oxygen saturation (simulated)",
    },
    "body_temperature": {
        "unit": "°C",
        "definition": "Simulated core body temperature",
    },
    "skin_temperature": {
        "unit": "°C",
        "definition": "Simulated skin temperature",
    },
    "blood_glucose": {
        "unit": "mg/dL",
        "definition": "Synthetic blood glucose concentration",
        "context": "Meal timing and fasting status are not modelled",
        "interpretation_ready": False,
    },
    "stress_level": {
        "unit": "index",
        "definition": "Synthetic relative stress index (0-100)",
        "interpretation_ready": False,
    },
    "sleep_duration": {
        "unit": "h",
        "definition": "Accumulated simulated sleep duration",
    },
    "sleep_quality": {
        "unit": "index",
        "definition": "Synthetic sleep quality index (0-100)",
        "interpretation_ready": False,
    },
    "physical_activity": {
        "unit": "simulation_index",
        "definition": "Synthetic activity index (0-25); not MET",
        "interpretation_ready": False,
    },
    "body_mass": {
        "unit": "kg",
        "definition": "Configured astronaut body mass",
    },
    "hydration_level": {
        "unit": "index",
        "definition": "Synthetic hydration index (0-100); not a direct clinical measurement",
        "interpretation_ready": False,
    },
    "cabin_temperature": {
        "unit": "°C",
        "definition": "Simulated cabin air temperature",
    },
    "cabin_pressure": {
        "unit": "kPa",
        "definition": "Simulated cabin pressure",
    },
    "cabin_humidity": {
        "unit": "%",
        "definition": "Simulated relative humidity",
    },
    "cabin_oxygen": {
        "unit": "%",
        "definition": "Simulated oxygen fraction by volume; not oxygen partial pressure",
        "interpretation_ready": False,
    },
    "cabin_co2": {
        "unit": "ppm",
        "definition": "Simulated cabin carbon dioxide concentration",
    },
    "microgravity_level": {
        "unit": "simulation_index",
        "definition": "Synthetic microgravity index; not measured acceleration",
        "interpretation_ready": False,
    },
    "cabin_air_quality": {
        "unit": "index",
        "definition": "Synthetic air quality index (0-100)",
        "interpretation_ready": False,
    },
}


API_CONFIG = {
    "iss_position_url": "https://api.wheretheiss.at/v1/satellites/25544",
    "iss_poll_interval_seconds": 10.0,

    "nasa_donki_base_url": "https://api.nasa.gov/DONKI",
    "nasa_donki_poll_interval_seconds": 900.0,
    "nasa_donki_lookback_days": 7,

    "radlab_url": "https://visualization.osdr.nasa.gov/radlab/api/",
    "radlab_poll_interval_seconds": 3600.0,
    "radlab_lookback_hours": 24,
    "radlab_max_integration_gap_seconds": 21600.0,

    "http_timeout_seconds": 12.0,
    "user_agent": f"AstronautHealthDataShuffler/{VERSION}",
    "api_keys_file": "api_keys.json",

    "backend_base_url": "http://127.0.0.1:8080",
    "backend_timeout_seconds": 5.0,
}

NASA_DONKI_ENDPOINTS = ("SEP", "CME", "GST")


# ============================================================
# VALIDATION AND GENERAL HELPERS
# ============================================================

def validate_number(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric.")

    try:
        is_finite = math.isfinite(value)

    except OverflowError as exc:
        raise ValueError(f"{name} must be finite.") from exc

    if not is_finite:
        raise ValueError(f"{name} must be finite.")

    if not minimum <= value <= maximum:
        raise ValueError(
            f"{name} must be between {minimum} and {maximum}."
        )


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise TypeError("Astronaut profile must be a dictionary.")

    required = {
        "body_mass": (20, 300),
        "resting_hr": (40, 100),
        "baseline_hrv": (10, 200),
        "baseline_skin_temp": (25, 38),
    }

    for key, (minimum, maximum) in required.items():
        if key not in profile:
            raise ValueError(f"Missing profile parameter: {key}")

        validate_number(
            key,
            profile[key],
            minimum,
            maximum,
        )


def validate_astronaut_id(astronaut_id):
    if not isinstance(astronaut_id, str):
        raise TypeError("astronaut_id must be a string.")

    astronaut_id = astronaut_id.strip().lower()

    if astronaut_id not in ASTRONAUT_IDS:
        raise ValueError(
            f"Unknown astronaut '{astronaut_id}'. "
            f"Supported astronauts: {', '.join(ASTRONAUT_IDS)}"
        )

    return astronaut_id


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
        try:
            if not math.isfinite(value):
                raise ValueError("Timestamp must be finite.")

            return datetime.fromtimestamp(
                value,
                tz=timezone.utc,
            )

        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError(
                "Timestamp is outside the supported range."
            ) from exc

    if not isinstance(value, str):
        raise ValueError("Unsupported timestamp format.")

    normalized = value.strip().replace("Z", "+00:00")

    if not normalized:
        raise ValueError("Timestamp cannot be empty.")

    try:
        parsed = datetime.fromisoformat(normalized)

    except ValueError as exc:
        raise ValueError("Invalid ISO-8601 timestamp.") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


# ============================================================
# PER-ASTRONAUT STATE
# ============================================================

def _initial_physiological_state(profile):
    return {
        "physical_activity": 5.0,
        "sleep_duration": 7.8,
        "sleep_quality": 88.0,
        "hydration_level": 95.0,
        "stress_level": 15.0,

        "heart_rate": profile["resting_hr"],
        "systolic_bp": 112.0,
        "diastolic_bp": 72.0,
        "heart_rate_variability": profile["baseline_hrv"],

        "respiratory_rate": 13.0,
        "spo2": 98.5,

        "body_temperature": 36.6,
        "skin_temperature": profile["baseline_skin_temp"],

        "blood_glucose": 90.0,
    }


def _create_astronaut_state(astronaut_id):
    profile = dict(ASTRONAUT_PROFILES[astronaut_id])

    return {
        "profile": profile,
        "mode": "NORMAL",
        "active_abnormalities": (),
        "abnormality_targets": {},

        "state": _initial_physiological_state(profile),
        "physiological_data": {},
        "measurement_metadata": {},
        "last_publish": {},
        "last_state_update": time.monotonic(),
        "ecg_phase": 0.0,
    }


_astronauts = {
    astronaut_id: _create_astronaut_state(astronaut_id)
    for astronaut_id in ASTRONAUT_IDS
}

# Compatibility aliases for the original single-astronaut implementation.
# They always refer to user1.
SIMULATION_MODE = "NORMAL"
_active_abnormalities = ()
_abnormality_targets = {}
_state = _astronauts["user1"]["state"]
physiological_data = _astronauts["user1"]["physiological_data"]
measurement_metadata = _astronauts["user1"]["measurement_metadata"]
_last_publish = _astronauts["user1"]["last_publish"]
_ecg_phase = 0.0


# ============================================================
# SHARED ENVIRONMENTAL STATE
# ============================================================

_environment_state = {
    "cabin_temperature": 22.5,
    "cabin_pressure": 101.3,
    "cabin_humidity": 45.0,
    "cabin_oxygen": 20.9,
    "cabin_co2": 900.0,
    "microgravity_level": 0.001,
    "cabin_air_quality": 95.0,
}

environmental_data = {}
environment_measurement_metadata = {}

_last_environment_update = time.monotonic()
_environment_last_publish = {}


# ============================================================
# LOCKS
# ============================================================

# The backend should serialize simulation updates.
# This lock also protects direct calls from the CLI or other threads.
_state_lock = threading.RLock()


# ============================================================
# API KEY CONFIGURATION
# ============================================================

def load_api_keys():
    """Load NASA API credentials from api_keys.json beside this file."""
    config_path = (
        Path(__file__).resolve().parent
        / API_CONFIG["api_keys_file"]
    )

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
    """Perform a bounded-timeout GET request and decode JSON."""
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
        timeout=API_CONFIG["http_timeout_seconds"],
    ) as response:
        payload = response.read()
        decoded = payload.decode("utf-8")

        return json.loads(decoded), dict(response.headers.items())


def retry_after_seconds(headers):
    """Read Retry-After as seconds or an HTTP date."""
    if not headers:
        return None

    value = (
        headers.get("Retry-After")
        or headers.get("retry-after")
    )

    if not value:
        return None

    try:
        retry_seconds = float(value)

        if math.isfinite(retry_seconds):
            return max(0.0, retry_seconds)

    except (TypeError, ValueError, OverflowError):
        pass

    try:
        retry_time = parsedate_to_datetime(value)

        if retry_time.tzinfo is None:
            retry_time = retry_time.replace(
                tzinfo=timezone.utc
            )

        retry_seconds = (
            retry_time - utc_now()
        ).total_seconds()

        if not math.isfinite(retry_seconds):
            return None

        return max(0.0, retry_seconds)

    except (
        TypeError,
        ValueError,
        OverflowError,
        IndexError,
    ):
        return None


def api_error_message(exc):
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"

    if isinstance(exc, URLError):
        return f"Network error: {exc.reason}"

    return str(exc)


# ============================================================
# SCENARIO MANAGEMENT
# ============================================================

def _build_abnormality_targets(selected):
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

        elif item == "CARDIAC_ARREST":
            targets["heart_rate"] = 0.0

        elif item == "HYPOTHERMIA":
            targets["body_temperature"] = random_value(34.2, 34.8, 2)

        elif item == "FEVER":
            targets["body_temperature"] = random_value(37.8, 38.3, 2)

        elif item == "HYPOXEMIA":
            targets["spo2"] = random_value(92, 94, 1)

        elif item == "SEVERE_HYPOXEMIA":
            targets["spo2"] = 65.0
            targets["respiratory_rate"] = 28.0

        elif item == "TACHYPNEA":
            targets["respiratory_rate"] = random_value(22, 25, 1)

        elif item == "HYPERTENSION":
            targets["systolic_bp"] = random_value(130, 145, 1)
            targets["diastolic_bp"] = random_value(80, 90, 1)

        elif item == "HYPOTENSION":
            targets["systolic_bp"] = random_value(90, 99, 1)
            targets["diastolic_bp"] = random_value(55, 64, 1)

    return targets


def set_simulation_scenario(
    mode="NORMAL",
    abnormalities=None,
    astronaut_id="user1",
):
    """
    Set a scenario for one astronaut only.

    Examples:
        set_simulation_scenario("NORMAL", astronaut_id="user1")
        set_simulation_scenario(
            "ABNORMAL",
            ["HYPERGLYCEMIA"],
            astronaut_id="user2",
        )
        set_simulation_scenario(
            "ABNORMAL",
            ["CARDIAC_ARREST"],
            astronaut_id="user3",
        )
    """

    astronaut_id = validate_astronaut_id(astronaut_id)

    if not isinstance(mode, str):
        raise TypeError("mode must be a string.")

    mode = mode.strip().upper()

    if mode not in SUPPORTED_MODES:
        raise ValueError(
            f"Unsupported simulation mode: {mode}"
        )

    if abnormalities is None:
        selected = ()

    elif isinstance(abnormalities, str):
        selected = (
            abnormalities.strip().upper(),
        )

    else:
        try:
            selected = tuple(
                str(item).strip().upper()
                for item in abnormalities
            )

        except TypeError as exc:
            raise TypeError(
                "abnormalities must be an iterable of names."
            ) from exc

    if any(not item for item in selected):
        raise ValueError("Abnormality names cannot be empty.")

    if len(set(selected)) != len(selected):
        raise ValueError(
            "Duplicate abnormalities are not allowed."
        )

    unknown = sorted(
        set(selected) - set(SUPPORTED_ABNORMALITIES)
    )

    if unknown:
        raise ValueError(
            f"Unsupported abnormality: {', '.join(unknown)}"
        )

    if mode == "ABNORMAL" and not selected:
        raise ValueError(
            "ABNORMAL mode requires at least one abnormality."
        )

    if mode != "ABNORMAL" and selected:
        raise ValueError(
            "abnormalities must only be supplied in ABNORMAL mode."
        )

    selected_set = set(selected)

    for conflict in _ABNORMALITY_CONFLICTS:
        if conflict.issubset(selected_set):
            raise ValueError(
                "Conflicting abnormalities cannot be combined: "
                + " / ".join(sorted(conflict))
            )

    targets = _build_abnormality_targets(selected)

    with _state_lock:
        astronaut = _astronauts[astronaut_id]
        previously_in_cardiac_arrest = (
            "CARDIAC_ARREST"
            in astronaut["active_abnormalities"]
        )

        astronaut["mode"] = mode
        astronaut["active_abnormalities"] = selected
        astronaut["abnormality_targets"] = targets

        # Move target values immediately so the first snapshot
        # does not have to wait for the smoothing process.
        for key, target in targets.items():
            astronaut["state"][key] = target
            astronaut["last_publish"].pop(key, None)

        # Reset ECG phase when entering or leaving cardiac arrest.
        if (
            "CARDIAC_ARREST" in selected
            or previously_in_cardiac_arrest
        ):
            astronaut["ecg_phase"] = 0.0

        _sync_user1_compatibility()

        return get_simulation_scenario(astronaut_id)


def get_simulation_scenario(astronaut_id="user1"):
    """Return the current scenario for one astronaut."""
    astronaut_id = validate_astronaut_id(astronaut_id)

    with _state_lock:
        astronaut = _astronauts[astronaut_id]

        return {
            "astronaut_id": astronaut_id,
            "mode": astronaut["mode"],
            "abnormalities": list(
                astronaut["active_abnormalities"]
            ),
            "scenario_type": "SYNTHETIC_TEST_DATA",
        }


def get_all_simulation_scenarios():
    return {
        astronaut_id: get_simulation_scenario(astronaut_id)
        for astronaut_id in ASTRONAUT_IDS
    }


def _sync_user1_compatibility():
    """Keep legacy module-level variables aligned with user1."""
    global SIMULATION_MODE
    global _active_abnormalities
    global _abnormality_targets
    global _state
    global physiological_data
    global measurement_metadata
    global _last_publish
    global ASTRONAUT_PROFILE

    user1 = _astronauts["user1"]

    SIMULATION_MODE = user1["mode"]
    _active_abnormalities = user1["active_abnormalities"]
    _abnormality_targets = user1["abnormality_targets"]
    _state = user1["state"]
    physiological_data = user1["physiological_data"]
    measurement_metadata = user1["measurement_metadata"]
    _last_publish = user1["last_publish"]

    # Keep both compatibility references aligned after profile replacement.
    ASTRONAUT_PROFILES["user1"] = user1["profile"]
    ASTRONAUT_PROFILE = user1["profile"]


# ============================================================
# PHYSIOLOGICAL MODEL
# ============================================================

def advance_physiological_state(
    dt,
    astronaut_id="user1",
):
    """Advance one astronaut's independent physiological state."""
    astronaut_id = validate_astronaut_id(astronaut_id)

    if dt <= 0:
        return

    dt = min(dt, 5.0)

    astronaut = _astronauts[astronaut_id]
    state = astronaut["state"]
    profile = astronaut["profile"]
    mode = astronaut["mode"]

    activity = state["physical_activity"]

    activity_targets = {
        "NORMAL": 5.0,
        "REST": 1.5,
        "EXERCISE": 16.0,
        "SLEEP": 0.5,
        "ABNORMAL": 5.0,
    }

    activity_target = activity_targets[mode]

    activity += random.gauss(
        0,
        0.35 * math.sqrt(dt),
    )

    activity += (
        (activity_target - activity)
        * dt / 20.0
    )

    activity = clamp(activity, 0, 25)
    state["physical_activity"] = activity

    sleep_quality = state["sleep_quality"]

    target_stress = (
        12.0
        + (90.0 - sleep_quality) * 0.4
        + activity * 0.35
    )

    target_stress += random.gauss(0, 1.0)
    target_stress = clamp(target_stress, 5, 40)

    state["stress_level"] = smooth_value(
        state["stress_level"],
        target_stress,
        dt,
        45.0,
    )

    hydration = state["hydration_level"]

    hydration += random.gauss(
        0,
        0.025 * math.sqrt(dt),
    )

    hydration -= 0.002 * dt

    state["hydration_level"] = clamp(
        hydration,
        85,
        100,
    )

    stress = state["stress_level"]

    target_hr = (
        profile["resting_hr"]
        + activity * 0.8
        + stress * 0.15
        + (95.0 - state["hydration_level"]) * 0.3
    )

    target_hr = clamp(target_hr, 55, 100)

    state["heart_rate"] = smooth_value(
        state["heart_rate"],
        target_hr,
        dt,
        3.0,
    )

    target_systolic = (
        112.0
        + stress * 0.08
        + activity * 0.08
    )

    target_diastolic = (
        72.0
        + stress * 0.05
        + activity * 0.025
    )

    state["systolic_bp"] = smooth_value(
        state["systolic_bp"],
        target_systolic,
        dt,
        15.0,
    )

    state["diastolic_bp"] = smooth_value(
        state["diastolic_bp"],
        target_diastolic,
        dt,
        15.0,
    )

    target_hrv = (
        profile["baseline_hrv"]
        - stress * 0.45
        - activity * 0.25
    )

    state["heart_rate_variability"] = smooth_value(
        state["heart_rate_variability"],
        target_hrv,
        dt,
        20.0,
    )

    target_rr = (
        13.0
        + activity * 0.1
        + stress * 0.025
    )

    state["respiratory_rate"] = smooth_value(
        state["respiratory_rate"],
        target_rr,
        dt,
        5.0,
    )

    target_spo2 = (
        98.5
        - max(0, stress - 25) * 0.015
    )

    state["spo2"] = smooth_value(
        state["spo2"],
        target_spo2,
        dt,
        8.0,
    )

    target_temp = (
        36.6
        + activity * 0.004
        + stress * 0.001
    )

    state["body_temperature"] = smooth_value(
        state["body_temperature"],
        target_temp,
        dt,
        60.0,
    )

    target_skin_temp = (
        profile["baseline_skin_temp"]
        + activity * 0.01
    )

    state["skin_temperature"] = smooth_value(
        state["skin_temperature"],
        target_skin_temp,
        dt,
        20.0,
    )

    target_glucose = (
        90.0
        + stress * 0.12
        - activity * 0.08
    )

    state["blood_glucose"] = smooth_value(
        state["blood_glucose"],
        target_glucose,
        dt,
        120.0,
    )


def apply_scenario_overrides(
    dt,
    astronaut_id="user1",
):
    """Apply one astronaut's active scenario targets."""
    astronaut_id = validate_astronaut_id(astronaut_id)

    astronaut = _astronauts[astronaut_id]
    state = astronaut["state"]
    mode = astronaut["mode"]
    abnormalities = set(astronaut["active_abnormalities"])

    if mode == "ABNORMAL":
        # Scenario targets are applied exactly. set_simulation_scenario()
        # already initializes these values immediately, and the normal
        # physiological model runs before this function on each refresh.
        # Reapplying the targets prevents that model from pulling an
        # active synthetic abnormality back toward baseline.
        for key, target in astronaut[
            "abnormality_targets"
        ].items():
            state[key] = target

    # These scenarios require exact, persistent synthetic values.
    # Apply them after smoothing so the normal physiological model
    # cannot gradually overwrite their target measurements.
    if "CARDIAC_ARREST" in abnormalities:
        state["heart_rate"] = 0.0

    if "SEVERE_HYPOXEMIA" in abnormalities:
        state["spo2"] = 65.0
        state["respiratory_rate"] = 28.0

    if dt > 0 and mode == "SLEEP":
        state["sleep_duration"] = min(
            12.0,
            state["sleep_duration"] + dt / 3600.0,
        )


# ============================================================
# SHARED ENVIRONMENTAL MODEL
# ============================================================

def advance_environmental_state(dt):
    """Advance the shared cabin environment once per refresh cycle."""
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

        current += random.gauss(
            0,
            noise * math.sqrt(dt),
        )

        _environment_state[key] = clamp(
            current,
            minimum,
            maximum,
        )


# ============================================================
# DATA SAMPLING
# ============================================================

def _publish_values(
    target,
    source,
    now,
    last_publish,
    metadata,
):
    """Publish due measurements with independent timestamps."""
    for key, interval in UPDATE_INTERVALS.items():

        if key not in source:
            continue

        last_time = last_publish.get(key)

        if (
            last_time is None
            or now - last_time >= interval
        ):
            target[key] = source[key]
            last_publish[key] = now

            info = MEASUREMENT_INFO.get(key, {})

            entry = {
                "measured_at": iso_utc(),
                "unit": info.get("unit", "unknown"),
                "definition": info.get("definition", ""),
                "interpretation_ready": info.get(
                    "interpretation_ready",
                    True,
                ),
            }

            if "context" in info:
                entry["context"] = info["context"]

            metadata[key] = entry


def _publish_astronaut_values(
    astronaut,
    now,
):
    state = astronaut["state"]
    profile = astronaut["profile"]
    abnormalities = set(astronaut["active_abnormalities"])

    spo2_minimum = (
        0
        if "SEVERE_HYPOXEMIA" in abnormalities
        else 90
    )

    source = {
        "heart_rate": round(state["heart_rate"], 1),
        "systolic_bp": round(
            clamp(state["systolic_bp"], 80, 160),
            1,
        ),
        "diastolic_bp": round(
            clamp(state["diastolic_bp"], 45, 100),
            1,
        ),
        "heart_rate_variability": round(
            state["heart_rate_variability"],
            1,
        ),
        "respiratory_rate": round(
            state["respiratory_rate"],
            1,
        ),
        "spo2": round(
            clamp(state["spo2"], spo2_minimum, 100),
            1,
        ),
        "body_temperature": round(
            clamp(state["body_temperature"], 34.0, 39.0),
            2,
        ),
        "skin_temperature": round(
            state["skin_temperature"],
            2,
        ),
        "blood_glucose": round(
            state["blood_glucose"],
            1,
        ),
        "stress_level": round(
            state["stress_level"],
            1,
        ),
        "sleep_duration": round(
            state["sleep_duration"],
            2,
        ),
        "sleep_quality": round(
            state["sleep_quality"],
            1,
        ),
        "physical_activity": round(
            state["physical_activity"],
            1,
        ),
        "body_mass": profile["body_mass"],
        "hydration_level": round(
            state["hydration_level"],
            1,
        ),
    }

    _publish_values(
        astronaut["physiological_data"],
        source,
        now,
        astronaut["last_publish"],
        astronaut["measurement_metadata"],
    )


def _publish_environment_values(now):
    source = {
        "cabin_temperature": round(
            _environment_state["cabin_temperature"],
            2,
        ),
        "cabin_pressure": round(
            _environment_state["cabin_pressure"],
            2,
        ),
        "cabin_humidity": round(
            _environment_state["cabin_humidity"],
            1,
        ),
        "cabin_oxygen": round(
            _environment_state["cabin_oxygen"],
            2,
        ),
        "cabin_co2": round(
            _environment_state["cabin_co2"],
            1,
        ),
        "microgravity_level": round(
            _environment_state["microgravity_level"],
            6,
        ),
        "cabin_air_quality": round(
            _environment_state["cabin_air_quality"],
            1,
        ),
    }

    _publish_values(
        environmental_data,
        source,
        now,
        _environment_last_publish,
        environment_measurement_metadata,
    )


# ============================================================
# ECG SIGNAL GENERATOR
# ============================================================

def _circular_gaussian(phase, center, width):
    distance = (phase - center + 0.5) % 1.0 - 0.5

    return math.exp(
        -0.5 * (distance / width) ** 2
    )


def _generate_ecg_point(phase):
    """Simplified synthetic P-QRS-T waveform; visualization only."""
    p_wave = 0.12 * _circular_gaussian(
        phase,
        0.18,
        0.025,
    )

    q_wave = -0.15 * _circular_gaussian(
        phase,
        0.275,
        0.008,
    )

    r_wave = 1.0 * _circular_gaussian(
        phase,
        0.30,
        0.006,
    )

    s_wave = -0.25 * _circular_gaussian(
        phase,
        0.325,
        0.010,
    )

    t_wave = 0.30 * _circular_gaussian(
        phase,
        0.55,
        0.050,
    )

    noise = random.gauss(0, 0.005)

    return (
        p_wave
        + q_wave
        + r_wave
        + s_wave
        + t_wave
        + noise
    )


def get_ecg_samples(
    sample_count=25,
    astronaut_id="user1",
):
    """
    Generate synthetic ECG samples for one astronaut.

    Output values are millivolts (mV).
    This is for visualization only, not diagnostic ECG data.

    In the explicit CARDIAC_ARREST simulation scenario, the
    generated signal is a flatline consisting of exact zeros.
    """

    astronaut_id = validate_astronaut_id(astronaut_id)

    if (
        isinstance(sample_count, bool)
        or not isinstance(sample_count, int)
    ):
        raise TypeError(
            "sample_count must be an integer."
        )

    if not 1 <= sample_count <= 5000:
        raise ValueError(
            "sample_count must be between 1 and 5000."
        )

    with _state_lock:
        astronaut = _astronauts[astronaut_id]

        if "CARDIAC_ARREST" in astronaut["active_abnormalities"]:
            astronaut["ecg_phase"] = 0.0

            if astronaut_id == "user1":
                global _ecg_phase
                _ecg_phase = 0.0

            return [0.0] * sample_count

        bpm = astronaut["physiological_data"].get(
            "heart_rate",
            astronaut["profile"]["resting_hr"],
        )

        samples = []

        phase_increment = (
            bpm / (60.0 * ECG_SAMPLE_RATE_HZ)
        )

        phase = astronaut["ecg_phase"]

        for _ in range(sample_count):
            samples.append(
                round(
                    _generate_ecg_point(phase),
                    5,
                )
            )

            phase = (
                phase + phase_increment
            ) % 1.0

        astronaut["ecg_phase"] = phase

        if astronaut_id == "user1":
            _ecg_phase = phase

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
    global _iss_last_attempt
    global _iss_failure_backoff

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
        payload, _headers = http_get_json(
            API_CONFIG["iss_position_url"]
        )

        required = (
            "latitude",
            "longitude",
            "altitude",
            "timestamp",
        )

        if (
            not isinstance(payload, dict)
            or any(key not in payload for key in required)
        ):
            raise ValueError(
                "ISS API response is missing required fields."
            )

        latitude = float(payload["latitude"])
        longitude = float(payload["longitude"])
        altitude = float(payload["altitude"])
        timestamp = float(payload["timestamp"])

        validate_number(
            "ISS latitude",
            latitude,
            -90,
            90,
        )

        validate_number(
            "ISS longitude",
            longitude,
            -180,
            180,
        )

        validate_number(
            "ISS altitude",
            altitude,
            0,
            1000,
        )

        validate_number(
            "ISS timestamp",
            timestamp,
            0,
            10000000000,
        )

        velocity = payload.get("velocity")

        if velocity is not None:
            velocity = float(velocity)

            validate_number(
                "ISS velocity",
                velocity,
                0,
                100000,
            )

        iss_position_data.update({
            "latitude": latitude,
            "longitude": longitude,
            "altitude_km": altitude,
            "velocity_km_h": velocity,
            "visibility": payload.get("visibility"),
            "timestamp": iso_utc(
                datetime.fromtimestamp(
                    timestamp,
                    timezone.utc,
                )
            ),
            "last_api_update": iso_utc(),
            "status": "OK",
            "last_error": None,
        })

        _iss_failure_backoff = 0.0

        return True

    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        OverflowError,
    ) as exc:

        iss_position_data["status"] = (
            "STALE"
            if iss_position_data["timestamp"]
            else "ERROR"
        )

        iss_position_data["last_error"] = (
            api_error_message(exc)
        )

        _iss_failure_backoff = min(
            300.0,
            max(
                30.0,
                _iss_failure_backoff * 2.0,
            ),
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

    return (
        start_date.isoformat(),
        end_date.isoformat(),
    )


def update_space_weather(force=False):
    """Fetch SEP, CME and GST event context from NASA DONKI."""
    global _donki_last_attempt
    global _donki_failure_backoff

    nasa_key = _api_keys.get("nasa_api_key")

    if not nasa_key:
        space_weather_data["status"] = (
            "DISABLED_NO_API_KEY"
        )

        space_weather_data["last_error"] = (
            _api_key_load_error
            or "nasa_api_key is not configured."
        )

        return False

    now_mono = time.monotonic()

    wait_for = max(
        API_CONFIG["nasa_donki_poll_interval_seconds"],
        _donki_failure_backoff,
    )

    if (
        not force
        and now_mono - _donki_last_attempt < wait_for
    ):
        return False

    _donki_last_attempt = now_mono

    start_date, end_date = _donki_date_range()

    fetched = {}
    latest_rate_limit = None
    latest_rate_remaining = None

    try:
        for event_type in NASA_DONKI_ENDPOINTS:

            url = (
                f"{API_CONFIG['nasa_donki_base_url']}/"
                f"{event_type}"
            )

            payload, headers = http_get_json(
                url,
                {
                    "startDate": start_date,
                    "endDate": end_date,
                    "api_key": nasa_key,
                },
            )

            if not isinstance(payload, list):
                raise ValueError(
                    f"DONKI {event_type} response was not a list."
                )

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
            _donki_failure_backoff = min(
                3600.0,
                max(60.0, retry_after),
            )

        else:
            _donki_failure_backoff = min(
                3600.0,
                max(
                    60.0,
                    _donki_failure_backoff * 2.0,
                ),
            )

        space_weather_data["status"] = (
            "STALE"
            if space_weather_data["last_api_update"]
            else "ERROR"
        )

        space_weather_data["last_error"] = (
            api_error_message(exc)
        )

        return False

    except (
        URLError,
        TimeoutError,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:

        _donki_failure_backoff = min(
            3600.0,
            max(
                60.0,
                _donki_failure_backoff * 2.0,
            ),
        )

        space_weather_data["status"] = (
            "STALE"
            if space_weather_data["last_api_update"]
            else "ERROR"
        )

        space_weather_data["last_error"] = (
            api_error_message(exc)
        )

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


def _radlab_query_start():
    """Return the minute-aligned start of the RadLab query window."""
    return (
        utc_now()
        - timedelta(hours=API_CONFIG["radlab_lookback_hours"])
    ).replace(second=0, microsecond=0)


def _radlab_query_url(query_start=None):
    """Build a query for recent historical ISS dose-rate records."""
    since = query_start or _radlab_query_start()

    since_text = since.strftime(
        "%Y-%m-%dT%H:%M"
    )

    params = [
        ("spacecraft", "ISS"),
        ("timestamp>=", since_text),
        ("dose_equivalent_rate", ""),
        ("latitude", ""),
        ("longitude", ""),
        ("altitude", ""),
        ("format", "json"),
    ]

    return (
        API_CONFIG["radlab_url"]
        + "?"
        + urlencode(params)
    )


def _radlab_rows(payload):
    """Normalize common JSON response shapes into row dictionaries."""
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):

        for key in (
            "data",
            "results",
            "rows",
            "records",
        ):
            value = payload.get(key)

            if isinstance(value, list):
                return value

        if payload and all(
            isinstance(value, list)
            for value in payload.values()
        ):
            columns = list(payload.keys())

            lengths = {
                len(payload[column])
                for column in columns
            }

            if len(lengths) == 1:
                row_count = next(
                    iter(lengths),
                    0,
                )

                return [
                    {
                        column: payload[column][index]
                        for column in columns
                    }
                    for index in range(row_count)
                ]

    raise ValueError(
        "Unrecognized RadLab JSON response structure."
    )


def _row_value(row, *names):
    lowered = {
        str(key).lower(): value
        for key, value in row.items()
    }

    for name in names:
        value = lowered.get(name.lower())

        if value not in (
            None,
            "",
            "NA",
            "NaN",
            "nan",
        ):
            return value

    return None


def _optional_float(value):
    if value in (
        None,
        "",
        "NA",
        "NaN",
        "nan",
    ):
        return None

    try:
        result = float(value)

    except (TypeError, ValueError, OverflowError):
        return None

    return result if math.isfinite(result) else None


def _integrate_dose_sample(timestamp, dose_rate):
    """Integrate dose rate using the trapezoidal rule."""
    global _radlab_previous_sample

    current = (timestamp, dose_rate)
    previous = _radlab_previous_sample

    if previous is None:
        _radlab_previous_sample = current

        radiation_dosimetry_data[
            "integration_status"
        ] = "WAITING_FOR_NEXT_SAMPLE"

        return

    previous_timestamp, previous_rate = previous

    elapsed_seconds = (
        timestamp - previous_timestamp
    ).total_seconds()

    if elapsed_seconds <= 0:
        return

    if elapsed_seconds <= API_CONFIG[
        "radlab_max_integration_gap_seconds"
    ]:

        average_rate = (
            previous_rate + dose_rate
        ) / 2.0

        dose_increment_usv = (
            average_rate
            * (elapsed_seconds / 3600.0)
        )

        radiation_dosimetry_data[
            "cumulative_dose_usv"
        ] += dose_increment_usv

        radiation_dosimetry_data[
            "cumulative_dose_msv"
        ] = (
            radiation_dosimetry_data[
                "cumulative_dose_usv"
            ] / 1000.0
        )

        radiation_dosimetry_data[
            "integration_status"
        ] = "INTEGRATING"

    else:
        radiation_dosimetry_data[
            "integration_status"
        ] = "GAP_NOT_INTEGRATED"

    _radlab_previous_sample = current


def update_radiation_measurements(force=False):
    """Retrieve archived ISS dose-rate records from NASA RadLab."""
    global _radlab_last_attempt
    global _radlab_failure_backoff

    now_mono = time.monotonic()

    wait_for = max(
        API_CONFIG["radlab_poll_interval_seconds"],
        _radlab_failure_backoff,
    )

    if (
        not force
        and now_mono - _radlab_last_attempt < wait_for
    ):
        return False

    _radlab_last_attempt = now_mono

    try:
        query_start = _radlab_query_start()
        url = _radlab_query_url(query_start)

        payload, _headers = http_get_json(url)

        # The API only returns this rolling window. Older timestamps
        # cannot prevent future duplicates, so prune them to keep the
        # deduplication cache bounded during long-running sessions.
        query_start_key = query_start.isoformat()
        expired_timestamps = (
            timestamp
            for timestamp in tuple(_radlab_seen_timestamps)
            if timestamp < query_start_key
        )
        _radlab_seen_timestamps.difference_update(
            expired_timestamps
        )

        rows = _radlab_rows(payload)

        parsed_rows = []

        for row in rows:

            if not isinstance(row, dict):
                continue

            timestamp_value = _row_value(
                row,
                "timestamp",
            )

            rate_value = _row_value(
                row,
                "dose_equivalent_rate",
            )

            if (
                timestamp_value is None
                or rate_value is None
            ):
                continue

            try:
                timestamp = parse_timestamp(
                    timestamp_value
                )

                dose_rate = float(rate_value)

            except (
                ValueError,
                TypeError,
                OverflowError,
            ):
                continue

            if (
                not math.isfinite(dose_rate)
                or dose_rate < 0
            ):
                continue

            parsed_rows.append({
                "timestamp": timestamp,
                "dose_rate": dose_rate,
                "latitude": _optional_float(
                    _row_value(row, "latitude")
                ),
                "longitude": _optional_float(
                    _row_value(row, "longitude")
                ),
                "altitude_km": _optional_float(
                    _row_value(row, "altitude")
                ),
                "instrument_id": _row_value(
                    row,
                    "instrument_id",
                ),
            })

        parsed_rows.sort(
            key=lambda item: item["timestamp"]
        )

        new_count = 0

        for sample in parsed_rows:
            timestamp_key = (
                sample["timestamp"].isoformat()
            )

            if timestamp_key in _radlab_seen_timestamps:
                continue

            _radlab_seen_timestamps.add(
                timestamp_key
            )

            if (
                sample["timestamp"]
                < _radiation_session_start
            ):
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
                    radiation_dosimetry_data[
                        "measurement_count"
                    ] + 1
                ),
                "measurement_status": "HISTORICAL_MEASUREMENT",
                "measurement_temporality": (
                    "HISTORICAL_ARCHIVE_NOT_LIVE_TELEMETRY"
                ),
            })

            new_count += 1

        radiation_dosimetry_data[
            "last_api_update"
        ] = iso_utc()

        radiation_dosimetry_data[
            "last_error"
        ] = None

        if not parsed_rows:
            radiation_dosimetry_data[
                "measurement_status"
            ] = "NO_MEASUREMENTS_IN_QUERY_WINDOW"

        elif new_count == 0:
            radiation_dosimetry_data[
                "measurement_status"
            ] = "NO_NEW_MEASUREMENTS"

        _radlab_failure_backoff = 0.0

        return True

    except HTTPError as exc:
        retry_after = retry_after_seconds(
            exc.headers
        )

        _radlab_failure_backoff = min(
            21600.0,
            max(
                300.0,
                retry_after
                or _radlab_failure_backoff * 2.0,
            ),
        )

        radiation_dosimetry_data[
            "measurement_status"
        ] = (
            "STALE"
            if radiation_dosimetry_data[
                "last_measurement_timestamp"
            ]
            else "ERROR"
        )

        radiation_dosimetry_data[
            "last_error"
        ] = api_error_message(exc)

        return False

    except (
        URLError,
        TimeoutError,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:

        _radlab_failure_backoff = min(
            21600.0,
            max(
                300.0,
                _radlab_failure_backoff * 2.0,
            ),
        )

        radiation_dosimetry_data[
            "measurement_status"
        ] = (
            "STALE"
            if radiation_dosimetry_data[
                "last_measurement_timestamp"
            ]
            else "ERROR"
        )

        radiation_dosimetry_data[
            "last_error"
        ] = api_error_message(exc)

        return False


# ============================================================
# SYSTEM DATA
# ============================================================

system_data = {
    "version": VERSION,
    "timestamp": None,
    "astronaut_ids": list(ASTRONAUT_IDS),
    "scenario_type": "SYNTHETIC_TEST_DATA",
    "data_source": "SIMULATED",
    "ecg_sample_rate_hz": ECG_SAMPLE_RATE_HZ,
    "api_status": {},
}

# Compatibility data object for user1.
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
# SNAPSHOT HELPERS
# ============================================================

def _copy_space_weather():
    return {
        **space_weather_data,
        "sep_events": deepcopy(
            space_weather_data["sep_events"]
        ),
        "cme_events": deepcopy(
            space_weather_data["cme_events"]
        ),
        "geomagnetic_storms": deepcopy(
            space_weather_data["geomagnetic_storms"]
        ),
    }


def _build_snapshot(astronaut_id):
    astronaut = _astronauts[astronaut_id]

    physiology = deepcopy(
        astronaut["physiological_data"]
    )

    environment = deepcopy(
        environmental_data
    )

    metadata = deepcopy(
        astronaut["measurement_metadata"]
    )

    metadata.update(
        deepcopy(environment_measurement_metadata)
    )

    environment["radiation_dose_rate_usv_h"] = (
        radiation_dosimetry_data[
            "dose_rate_usv_h"
        ]
    )

    if radiation_dosimetry_data[
        "last_measurement_timestamp"
    ]:
        metadata["radiation_dose_rate_usv_h"] = {
            "measured_at": (
                radiation_dosimetry_data[
                    "last_measurement_timestamp"
                ]
            ),
            "unit": "µSv/hour",
            "definition": (
                "NASA OSDR RadLab historical dose-equivalent rate; "
                "not live telemetry"
            ),
            "interpretation_ready": False,
            "data_temporality": (
                "HISTORICAL_ARCHIVE_NOT_LIVE_TELEMETRY"
            ),
        }

    astronaut_system = {
        **deepcopy(system_data),
        "astronaut_id": astronaut_id,
        "simulation_mode": astronaut["mode"],
        "active_abnormalities": list(
            astronaut["active_abnormalities"]
        ),
        "scenario_type": "SYNTHETIC_TEST_DATA",
        "astronaut_profile": deepcopy(
            astronaut["profile"]
        ),
    }

    return {
        "astronaut_id": astronaut_id,
        "physiological_data": physiology,
        "environmental_data": environment,
        "system_data": astronaut_system,
        "iss_position_data": deepcopy(
            iss_position_data
        ),
        "space_weather_data": _copy_space_weather(),
        "radiation_dosimetry_data": deepcopy(
            radiation_dosimetry_data
        ),
        "measurement_metadata": metadata,
    }


# ============================================================
# MAIN REFRESH FUNCTION
# ============================================================

def refresh_all_data(include_remote=True):
    """
    Advance all astronauts and shared environmental data.

    Shared environmental and remote data are updated once,
    not once per astronaut.
    """

    global _last_environment_update

    with _state_lock:
        now = time.monotonic()

        # Shared environment advances once.
        environment_dt = (
            now - _last_environment_update
        )

        advance_environmental_state(
            environment_dt
        )

        _last_environment_update = now

        _publish_environment_values(now)

        # Each astronaut advances independently.
        for astronaut_id in ASTRONAUT_IDS:
            astronaut = _astronauts[astronaut_id]

            validate_profile(
                astronaut["profile"]
            )

            physiological_dt = (
                now - astronaut["last_state_update"]
            )

            advance_physiological_state(
                physiological_dt,
                astronaut_id,
            )

            apply_scenario_overrides(
                physiological_dt,
                astronaut_id,
            )

            astronaut["last_state_update"] = now

            _publish_astronaut_values(
                astronaut,
                now,
            )

        # Shared remote sources are fetched once.
        if include_remote:
            update_iss_position()
            update_space_weather()
            update_radiation_measurements()

        system_data.update({
            "version": VERSION,
            "timestamp": iso_utc(),
            "astronaut_ids": list(ASTRONAUT_IDS),
            "scenario_type": "SYNTHETIC_TEST_DATA",
            "data_source": "SIMULATED",
            "ecg_sample_rate_hz": ECG_SAMPLE_RATE_HZ,
            "api_status": {
                "iss_position": iss_position_data["status"],
                "nasa_donki": space_weather_data["status"],
                "nasa_radlab": (
                    radiation_dosimetry_data[
                        "measurement_status"
                    ]
                ),
            },
        })

        _sync_user1_compatibility()

        return {
            astronaut_id: _build_snapshot(astronaut_id)
            for astronaut_id in ASTRONAUT_IDS
        }


def refresh_data(
    include_remote=True,
    astronaut_id="user1",
):
    """
    Backward-compatible refresh function.

    The entire crew and shared environment are refreshed
    together. The returned data belongs to astronaut_id.
    """

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    snapshots = refresh_all_data(
        include_remote=include_remote
    )

    return snapshots[astronaut_id]


def generate_all_snapshots(include_remote=True):
    """
    Generate one fresh snapshot for every astronaut.

    This is the preferred backend entry point.
    """

    return refresh_all_data(
        include_remote=include_remote
    )


def generate_snapshot(
    astronaut_id="user1",
    include_remote=True,
):
    """Generate a fresh snapshot for one requested astronaut."""
    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    snapshots = generate_all_snapshots(
        include_remote=include_remote
    )

    return snapshots[astronaut_id]


def get_environment_snapshot():
    """Return the shared environment and shared external data."""
    with _state_lock:
        return {
            "environmental_data": deepcopy(
                environmental_data
            ),
            "environment_measurement_metadata": deepcopy(
                environment_measurement_metadata
            ),
            "iss_position_data": deepcopy(
                iss_position_data
            ),
            "space_weather_data": _copy_space_weather(),
            "radiation_dosimetry_data": deepcopy(
                radiation_dosimetry_data
            ),
            "generated_at": iso_utc(),
        }


# ============================================================
# PROFILE MANAGEMENT
# ============================================================

def get_astronaut_profile(astronaut_id="user1"):
    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    with _state_lock:
        return deepcopy(
            _astronauts[astronaut_id]["profile"]
        )


def set_astronaut_profile(
    profile,
    astronaut_id="user1",
):
    """
    Replace one astronaut's profile.

    Existing physiological state is not reset.
    Body mass and baseline targets take effect in subsequent updates.
    """

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    if not isinstance(profile, dict):
        raise TypeError("profile must be a dictionary.")

    required_keys = set(
        DEFAULT_ASTRONAUT_PROFILE
    )

    if set(profile) != required_keys:
        raise ValueError(
            "Profile must contain exactly these fields: "
            + ", ".join(sorted(required_keys))
        )

    new_profile = dict(profile)

    validate_profile(new_profile)

    with _state_lock:
        _astronauts[astronaut_id]["profile"] = (
            new_profile
        )

        ASTRONAUT_PROFILES[astronaut_id] = new_profile

        if astronaut_id == "user1":
            _sync_user1_compatibility()

        return deepcopy(new_profile)


# ============================================================
# INITIALIZATION
# ============================================================

# Publish initial data without making remote requests.
refresh_all_data(include_remote=False)


# ============================================================
# BACKEND CLIENT
# ============================================================

def _backend_url(endpoint):
    base_url = API_CONFIG[
        "backend_base_url"
    ].rstrip("/")

    return f"{base_url}{endpoint}"


def _backend_get(endpoint):
    request = Request(
        _backend_url(endpoint),
        headers={
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=API_CONFIG[
                "backend_timeout_seconds"
            ],
        ) as response:

            payload = response.read().decode("utf-8")

            return json.loads(payload)

    except HTTPError as exc:
        details = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Backend returned HTTP {exc.code}: {details}"
        ) from exc

    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "Could not connect to the FastAPI backend. "
            "Make sure main.py is running."
        ) from exc

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(
            "Backend returned an invalid JSON response."
        ) from exc


def _backend_post(endpoint, payload):
    encoded_payload = json.dumps(
        payload
    ).encode("utf-8")

    request = Request(
        _backend_url(endpoint),
        data=encoded_payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=API_CONFIG[
                "backend_timeout_seconds"
            ],
        ) as response:

            body = response.read().decode("utf-8")

            return json.loads(body)

    except HTTPError as exc:
        details = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Backend returned HTTP {exc.code}: {details}"
        ) from exc

    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "Could not connect to the FastAPI backend. "
            "Make sure main.py is running."
        ) from exc

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(
            "Backend returned an invalid JSON response."
        ) from exc


# ============================================================
# INTERACTIVE TERMINAL CLIENT
# ============================================================

def _print_client_help():
    print("\nAvailable commands:")
    print("  user1 normal")
    print("  user1 rest")
    print("  user1 exercise")
    print("  user1 sleep")
    print("  user1 abnormal hyperglycemia")
    print("  user1 abnormal hyperglycemia tachycardia")
    print("  user2 abnormal hypoxemia")
    print("  user2 abnormal severe_hypoxemia")
    print("  user3 abnormal cardiac_arrest")
    print("  user3 normal")
    print()
    print("  user1 status")
    print("  users status")
    print("  user1 snapshot")
    print("  user2 snapshot")
    print("  environment")
    print("  help")
    print("  exit")
    print()
    print("Supported abnormalities:")
    print(
        "  "
        + ", ".join(
            name.lower()
            for name in SUPPORTED_ABNORMALITIES
        )
    )
    print()


def _parse_client_command(command):
    """
    Parse a multi-astronaut CLI command.

    Returns a dictionary describing the requested action.
    """

    parts = command.strip().split()

    if not parts:
        return None

    action = parts[0].lower()

    if action in ("help", "exit", "quit"):
        if len(parts) != 1:
            raise ValueError(
                f"'{action}' does not accept additional arguments."
            )

        return {
            "action": action,
        }

    if action == "users":
        if len(parts) != 2 or parts[1].lower() != "status":
            raise ValueError(
                "Usage: users status"
            )

        return {
            "action": "users_status",
        }

    if action == "environment":
        if len(parts) != 1:
            raise ValueError(
                "Usage: environment"
            )

        return {
            "action": "environment",
        }

    astronaut_id = validate_astronaut_id(
        action
    )

    if len(parts) < 2:
        raise ValueError(
            "A command is required after the astronaut ID."
        )

    command_action = parts[1].lower()

    if command_action in (
        "normal",
        "rest",
        "exercise",
        "sleep",
    ):
        if len(parts) != 2:
            raise ValueError(
                f"Usage: {astronaut_id} {command_action}"
            )

        return {
            "action": "scenario",
            "astronaut_id": astronaut_id,
            "mode": command_action.upper(),
            "abnormalities": [],
        }

    if command_action == "abnormal":
        if len(parts) < 3:
            raise ValueError(
                "Usage: user1 abnormal <condition> [condition ...]"
            )

        abnormalities = []

        for part in parts[2:]:
            # Support both whitespace and comma-separated names.
            for item in part.split(","):
                normalized = (
                    item.strip()
                    .upper()
                    .replace("-", "_")
                    .replace(" ", "_")
                )

                if normalized:
                    abnormalities.append(normalized)

        if not abnormalities:
            raise ValueError(
                "At least one abnormality must be specified."
            )

        return {
            "action": "scenario",
            "astronaut_id": astronaut_id,
            "mode": "ABNORMAL",
            "abnormalities": abnormalities,
        }

    if command_action == "status":
        if len(parts) != 2:
            raise ValueError(
                f"Usage: {astronaut_id} status"
            )

        return {
            "action": "status",
            "astronaut_id": astronaut_id,
        }

    if command_action == "snapshot":
        if len(parts) != 2:
            raise ValueError(
                f"Usage: {astronaut_id} snapshot"
            )

        return {
            "action": "snapshot",
            "astronaut_id": astronaut_id,
        }

    raise ValueError(
        f"Unknown command: {command_action}"
    )


def _send_scenario_command(
    astronaut_id,
    mode,
    abnormalities=None,
):
    payload = {
        "mode": mode,
        "abnormalities": abnormalities or [],
    }

    return _backend_post(
        f"/api/v1/astronauts/{astronaut_id}/scenario",
        payload,
    )


def _show_astronaut_status(astronaut_id):
    result = _backend_get(
        f"/api/v1/astronauts/{astronaut_id}/scenario"
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


def _show_all_status():
    result = _backend_get(
        "/api/v1/crew"
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


def _show_astronaut_snapshot(astronaut_id):
    result = _backend_get(
        f"/api/v1/astronauts/{astronaut_id}/dashboard"
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


def _show_environment():
    result = _backend_get(
        "/api/v1/environment"
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


def run_client():
    """
    Run the interactive terminal client.

    The FastAPI backend owns all simulation state.
    This client only sends commands and retrieves data.
    """

    print("=" * 60)
    print(
        f"ASTRONAUT HEALTH DATA SHUFFLER — CLIENT v{VERSION}"
    )
    print("=" * 60)

    print(
        "Connecting to backend: "
        f"{API_CONFIG['backend_base_url']}"
    )

    try:
        crew = _backend_get(
            "/api/v1/crew"
        )

    except RuntimeError as exc:
        print(f"\n[CONNECTION ERROR] {exc}")

        print(
            "\nStart the backend first by running "
            "'python main.py' from the healthProc directory."
        )

        return

    print("[CONNECTED] FastAPI backend is available.")

    print("\nCrew:")
    print(
        json.dumps(
            crew,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nType 'help' to see available commands.\n")

    while True:
        try:
            command = input("shuffler> ").strip()

        except EOFError:
            print()
            break

        except KeyboardInterrupt:
            print("\nInterrupt received.")
            break

        if not command:
            continue

        try:
            parsed = _parse_client_command(
                command
            )

            if parsed is None:
                continue

            action = parsed["action"]

            if action == "help":
                _print_client_help()

            elif action in ("exit", "quit"):
                break

            elif action == "users_status":
                _show_all_status()

            elif action == "environment":
                _show_environment()

            elif action == "status":
                _show_astronaut_status(
                    parsed["astronaut_id"]
                )

            elif action == "snapshot":
                _show_astronaut_snapshot(
                    parsed["astronaut_id"]
                )

            elif action == "scenario":
                result = _send_scenario_command(
                    parsed["astronaut_id"],
                    parsed["mode"],
                    parsed["abnormalities"],
                )

                print("\n[SCENARIO UPDATED]")

                print(
                    json.dumps(
                        result,
                        indent=2,
                        ensure_ascii=False,
                    )
                )

        except (TypeError, ValueError) as exc:
            print(f"[INVALID COMMAND] {exc}")

        except RuntimeError as exc:
            print(f"[BACKEND ERROR] {exc}")

    print("Shuffler client stopped.")


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_client()
