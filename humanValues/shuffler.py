
"""
Astronaut Health Data Shuffler
Version: 1.1.0

Continuous, time-based synthetic physiological simulation.
Standard library only.
"""

import math
import random
import time
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

SIMULATION_MODE = "NORMAL"
SUPPORTED_MODES = ("NORMAL",)

ECG_SAMPLE_RATE_HZ = 500

ASTRONAUT_PROFILE = {
    "body_mass": 75.0,
    "resting_hr": 68.0,
    "baseline_hrv": 65.0,
    "baseline_skin_temp": 34.5,
}

# Update intervals in seconds.
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
    "radiation_dose_rate_usv_h": 1.0,
    "microgravity_level": 0.1,
    "cabin_air_quality": 10.0,
}


# ============================================================
# VALIDATION
# ============================================================

def validate_number(name, value, minimum, maximum):

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric.")

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")

    if not minimum <= value <= maximum:
        raise ValueError(
            f"{name} must be between {minimum} and {maximum}."
        )


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

        validate_number(
            key,
            ASTRONAUT_PROFILE[key],
            minimum,
            maximum
        )


def validate_mode():

    if not isinstance(SIMULATION_MODE, str):
        raise TypeError("SIMULATION_MODE must be a string.")

    if SIMULATION_MODE not in SUPPORTED_MODES:
        raise ValueError(
            f"Unsupported simulation mode: {SIMULATION_MODE}"
        )


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
    "radiation_dose_rate_usv_h": 15.0,
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
    """
    Advance internal physiological state.

    Values depend on previous state and shared physiological
    conditions rather than independent random generation.
    """

    if dt <= 0:
        return

    dt = min(dt, 5.0)

    # --------------------------------------------------------
    # Activity
    # --------------------------------------------------------

    activity = _state["physical_activity"]

    activity += random.gauss(0, 0.35 * math.sqrt(dt))
    activity += (5.0 - activity) * dt / 45.0

    activity = clamp(activity, 0, 25)

    _state["physical_activity"] = activity

    # --------------------------------------------------------
    # Sleep and stress
    # --------------------------------------------------------

    sleep_quality = _state["sleep_quality"]

    target_stress = (
        12.0
        + (90.0 - sleep_quality) * 0.4
        + activity * 0.35
    )

    target_stress += random.gauss(0, 1.0)
    target_stress = clamp(target_stress, 5, 40)

    _state["stress_level"] = smooth_value(
        _state["stress_level"],
        target_stress,
        dt,
        45.0
    )

    # --------------------------------------------------------
    # Hydration
    # --------------------------------------------------------

    hydration = _state["hydration_level"]

    hydration += random.gauss(0, 0.025 * math.sqrt(dt))
    hydration -= 0.002 * dt

    hydration = clamp(hydration, 85, 100)

    _state["hydration_level"] = hydration

    # --------------------------------------------------------
    # Cardiovascular system
    # --------------------------------------------------------

    stress = _state["stress_level"]

    target_hr = (
        ASTRONAUT_PROFILE["resting_hr"]
        + activity * 0.8
        + stress * 0.15
        + (95.0 - hydration) * 0.3
    )

    target_hr = clamp(target_hr, 55, 100)

    _state["heart_rate"] = smooth_value(
        _state["heart_rate"],
        target_hr,
        dt,
        3.0
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

    _state["systolic_bp"] = smooth_value(
        _state["systolic_bp"],
        target_systolic,
        dt,
        15.0
    )

    _state["diastolic_bp"] = smooth_value(
        _state["diastolic_bp"],
        target_diastolic,
        dt,
        15.0
    )

    target_hrv = (
        ASTRONAUT_PROFILE["baseline_hrv"]
        - stress * 0.45
        - activity * 0.25
    )

    _state["heart_rate_variability"] = smooth_value(
        _state["heart_rate_variability"],
        target_hrv,
        dt,
        20.0
    )

    # --------------------------------------------------------
    # Respiratory system
    # --------------------------------------------------------

    target_rr = (
        13.0
        + activity * 0.1
        + stress * 0.025
    )

    _state["respiratory_rate"] = smooth_value(
        _state["respiratory_rate"],
        target_rr,
        dt,
        5.0
    )

    # --------------------------------------------------------
    # Oxygen saturation
    # --------------------------------------------------------

    # Normal-mode oxygen saturation remains stable.
    target_spo2 = 98.5 - max(0, stress - 25) * 0.015

    _state["spo2"] = smooth_value(
        _state["spo2"],
        target_spo2,
        dt,
        8.0
    )

    # --------------------------------------------------------
    # Body temperature
    # --------------------------------------------------------

    target_temp = (
        36.6
        + activity * 0.004
        + stress * 0.001
    )

    _state["body_temperature"] = smooth_value(
        _state["body_temperature"],
        target_temp,
        dt,
        60.0
    )

    target_skin_temp = (
        ASTRONAUT_PROFILE["baseline_skin_temp"]
        + activity * 0.01
    )

    _state["skin_temperature"] = smooth_value(
        _state["skin_temperature"],
        target_skin_temp,
        dt,
        20.0
    )

    # --------------------------------------------------------
    # Blood glucose
    # --------------------------------------------------------

    target_glucose = (
        90.0
        + stress * 0.12
        - activity * 0.08
    )

    _state["blood_glucose"] = smooth_value(
        _state["blood_glucose"],
        target_glucose,
        dt,
        120.0
    )


# ============================================================
# ENVIRONMENTAL MODEL
# ============================================================

def advance_environmental_state(dt):

    if dt <= 0:
        return

    dt = min(dt, 5.0)

    # Slow environmental fluctuations.

    changes = {
        "cabin_temperature": (0.015, 21, 24),
        "cabin_pressure": (0.008, 99, 103),
        "cabin_humidity": (0.04, 35, 55),
        "cabin_oxygen": (0.003, 20.5, 21.0),
        "cabin_co2": (0.8, 500, 1500),
        "radiation_dose_rate_usv_h": (0.08, 5, 30),
        "microgravity_level": (0.00001, 0.0001, 0.01),
        "cabin_air_quality": (0.015, 90, 100),
    }

    for key, (noise, minimum, maximum) in changes.items():

        current = _environment_state[key]

        current += random.gauss(0, noise * math.sqrt(dt))

        _environment_state[key] = clamp(
            current,
            minimum,
            maximum
        )


# ============================================================
# DATA SAMPLING
# ============================================================

def publish_due_values(target, source, now):
    """
    Update only values whose sampling interval has elapsed.
    """

    for key, interval in UPDATE_INTERVALS.items():

        if key not in source:
            continue

        last_time = _last_publish.get(key)

        if last_time is None or now - last_time >= interval:

            target[key] = source[key]
            _last_publish[key] = now


# ============================================================
# ECG SIGNAL GENERATOR
# ============================================================

_ecg_phase = 0.0


def _circular_gaussian(phase, center, width):
    """Generate a Gaussian wave with circular phase wrapping."""

    distance = (phase - center + 0.5) % 1.0 - 0.5

    return math.exp(
        -0.5 * (distance / width) ** 2
    )


def _generate_ecg_point(phase):
    """
    Simplified synthetic P-QRS-T waveform.

    Output unit: millivolts (mV).
    This is a visualization model, not a diagnostic ECG.
    """

    p_wave = 0.12 * _circular_gaussian(
        phase, 0.18, 0.025
    )

    q_wave = -0.15 * _circular_gaussian(
        phase, 0.275, 0.008
    )

    r_wave = 1.0 * _circular_gaussian(
        phase, 0.30, 0.006
    )

    s_wave = -0.25 * _circular_gaussian(
        phase, 0.325, 0.010
    )

    t_wave = 0.30 * _circular_gaussian(
        phase, 0.55, 0.050
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


def get_ecg_samples(sample_count=25):
    """
    Generate ECG samples at 500 Hz.

    A sample_count of 25 represents 50 ms of signal.

    Returns:
        list[float]: ECG waveform samples in mV.
    """

    global _ecg_phase

    if isinstance(sample_count, bool) or not isinstance(sample_count, int):
        raise TypeError("sample_count must be an integer.")

    if not 1 <= sample_count <= 5000:
        raise ValueError(
            "sample_count must be between 1 and 5000."
        )

    bpm = physiological_data.get("heart_rate", 68.0)

    samples = []

    phase_increment = (
        bpm / (60.0 * ECG_SAMPLE_RATE_HZ)
    )

    for _ in range(sample_count):

        sample = _generate_ecg_point(_ecg_phase)

        samples.append(round(sample, 5))

        _ecg_phase = (
            _ecg_phase + phase_increment
        ) % 1.0

    return samples


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
}


# ============================================================
# MAIN REFRESH FUNCTION
# ============================================================

def refresh_data():
    """
    Advance simulation and publish values when their
    individual sampling intervals have elapsed.

    Existing dictionary references remain valid.
    """

    global _last_state_update
    global _last_environment_update

    validate_mode()
    validate_profile()

    now = time.monotonic()

    physiological_dt = now - _last_state_update
    environmental_dt = now - _last_environment_update

    advance_physiological_state(physiological_dt)
    advance_environmental_state(environmental_dt)

    _last_state_update = now
    _last_environment_update = now

    # --------------------------------------------------------
    # Physiological sampling
    # --------------------------------------------------------

    physiological_source = {
        "heart_rate": round(_state["heart_rate"], 1),

        "systolic_bp": round(
            clamp(_state["systolic_bp"], 90, 119), 1
        ),

        "diastolic_bp": round(
            clamp(_state["diastolic_bp"], 60, 79), 1
        ),

        "heart_rate_variability": round(
            _state["heart_rate_variability"], 1
        ),

        "respiratory_rate": round(
            _state["respiratory_rate"], 1
        ),

        "spo2": round(
            clamp(_state["spo2"], 97, 100), 1
        ),

        "body_temperature": round(
            clamp(_state["body_temperature"], 36.1, 37.2), 2
        ),

        "skin_temperature": round(
            _state["skin_temperature"], 2
        ),

        "blood_glucose": round(
            _state["blood_glucose"], 1
        ),

        "stress_level": round(
            _state["stress_level"], 1
        ),

        "sleep_duration": _state["sleep_duration"],
        "sleep_quality": round(_state["sleep_quality"], 1),

        "physical_activity": round(
            _state["physical_activity"], 1
        ),

        "body_mass": ASTRONAUT_PROFILE["body_mass"],

        "hydration_level": round(
            _state["hydration_level"], 1
        ),
    }

    publish_due_values(
        physiological_data,
        physiological_source,
        now
    )

    # --------------------------------------------------------
    # Environmental sampling
    # --------------------------------------------------------

    environmental_source = {
        "cabin_temperature": round(
            _environment_state["cabin_temperature"], 2
        ),

        "cabin_pressure": round(
            _environment_state["cabin_pressure"], 2
        ),

        "cabin_humidity": round(
            _environment_state["cabin_humidity"], 1
        ),

        "cabin_oxygen": round(
            _environment_state["cabin_oxygen"], 2
        ),

        "cabin_co2": round(
            _environment_state["cabin_co2"], 1
        ),

        "radiation_dose_rate_usv_h": round(
            _environment_state["radiation_dose_rate_usv_h"], 3
        ),

        "microgravity_level": round(
            _environment_state["microgravity_level"], 6
        ),

        "cabin_air_quality": round(
            _environment_state["cabin_air_quality"], 1
        ),
    }

    publish_due_values(
        environmental_data,
        environmental_source,
        now
    )

    # --------------------------------------------------------
    # System information
    # --------------------------------------------------------

    system_data.update({
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),

        "simulation_mode": SIMULATION_MODE,
        "data_source": "SIMULATED",
        "ecg_sample_rate_hz": ECG_SAMPLE_RATE_HZ,
    })

    return data


# ============================================================
# SNAPSHOT FUNCTION
# ============================================================

def generate_snapshot():
    """Return a copy of the latest published data."""

    refresh_data()

    return {
        "physiological_data": dict(physiological_data),
        "environmental_data": dict(environmental_data),
        "system_data": dict(system_data),
    }


# ============================================================
# INITIALIZATION
# ============================================================

refresh_data()
