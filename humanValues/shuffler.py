
"""
Astronaut Health Data Shuffler
Version: 1.0.0

Generates correlated synthetic physiological and environmental data.
Standard library only.
"""

import random
import math
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

SIMULATION_MODE = "NORMAL"

SUPPORTED_MODES = ("NORMAL",)

ASTRONAUT_PROFILE = {
    "body_mass": 75.0,
    "resting_hr": 68.0,
    "baseline_hrv": 65.0,
    "baseline_skin_temp": 34.5,
}


# ============================================================
# VALIDATION
# ============================================================

def validate_number(name, value, minimum, maximum):
    """Validate numeric configuration values."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a numeric value.")

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")

    if not minimum <= value <= maximum:
        raise ValueError(
            f"{name} must be between {minimum} and {maximum}."
        )


def validate_profile():
    """Validate the astronaut's baseline profile."""

    required = {
        "body_mass": (20, 300),
        "resting_hr": (40, 100),
        "baseline_hrv": (10, 200),
        "baseline_skin_temp": (25, 38),
    }

    if not isinstance(ASTRONAUT_PROFILE, dict):
        raise TypeError("ASTRONAUT_PROFILE must be a dictionary.")

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
    """Ensure that the selected simulation mode is supported."""

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
    """Restrict a numeric value to a specified range."""

    return max(minimum, min(value, maximum))


def random_value(minimum, maximum, decimals=1):
    """Generate a random floating-point value."""

    return round(random.uniform(minimum, maximum), decimals)


# ============================================================
# PHYSIOLOGICAL DATA
# ============================================================

def generate_physiological_data():

    validate_profile()

    # --------------------------------------------------------
    # General conditions
    # --------------------------------------------------------

    physical_activity = random_value(0, 25)
    sleep_duration = random_value(7, 9)
    sleep_quality = random_value(75, 100)
    hydration_level = random_value(85, 100)

    # --------------------------------------------------------
    # Stress
    # --------------------------------------------------------

    stress_level = (
        random.uniform(10, 25)
        + (90 - sleep_quality) * 0.35
        + physical_activity * 0.08
    )

    stress_level = clamp(stress_level, 0, 100)

    # --------------------------------------------------------
    # Cardiovascular system
    # --------------------------------------------------------

    heart_rate = (
        ASTRONAUT_PROFILE["resting_hr"]
        + physical_activity * 0.45
        + stress_level * 0.12
        + (95 - hydration_level) * 0.25
        + random.gauss(0, 2)
    )

    heart_rate = clamp(heart_rate, 55, 100)

    systolic_bp = (
        112
        + stress_level * 0.08
        + physical_activity * 0.04
        + random.gauss(0, 3)
    )

    diastolic_bp = (
        72
        + stress_level * 0.05
        + random.gauss(0, 2)
    )

    systolic_bp = clamp(systolic_bp, 90, 119)
    diastolic_bp = clamp(diastolic_bp, 60, 79)

    heart_rate_variability = (
        ASTRONAUT_PROFILE["baseline_hrv"]
        - stress_level * 0.45
        - physical_activity * 0.25
        + random.gauss(0, 4)
    )

    heart_rate_variability = clamp(
        heart_rate_variability, 20, 100
    )

    # --------------------------------------------------------
    # Respiratory system
    # --------------------------------------------------------

    respiratory_rate = (
        13
        + physical_activity * 0.07
        + stress_level * 0.025
        + random.gauss(0, 0.5)
    )

    respiratory_rate = clamp(respiratory_rate, 12, 20)

    spo2 = random_value(97, 100, 0)

    # --------------------------------------------------------
    # Body temperature
    # --------------------------------------------------------

    body_temperature = (
        36.6
        + physical_activity * 0.004
        + stress_level * 0.001
        + random.gauss(0, 0.08)
    )

    body_temperature = clamp(body_temperature, 36.1, 37.2)

    skin_temperature = (
        ASTRONAUT_PROFILE["baseline_skin_temp"]
        + physical_activity * 0.01
        + random.gauss(0, 0.3)
    )

    # --------------------------------------------------------
    # Metabolism
    # --------------------------------------------------------

    blood_glucose = random_value(80, 105)

    # --------------------------------------------------------
    # Return physiological data
    # --------------------------------------------------------

    return {
        "heart_rate": round(heart_rate, 1),
        "systolic_bp": round(systolic_bp, 1),
        "diastolic_bp": round(diastolic_bp, 1),
        "heart_rate_variability": round(
            heart_rate_variability, 1
        ),

        "respiratory_rate": round(respiratory_rate, 1),
        "spo2": spo2,

        "body_temperature": round(body_temperature, 2),
        "skin_temperature": round(skin_temperature, 2),
        "blood_glucose": blood_glucose,

        "stress_level": round(stress_level, 1),
        "sleep_duration": sleep_duration,
        "sleep_quality": sleep_quality,
        "physical_activity": physical_activity,

        "body_mass": ASTRONAUT_PROFILE["body_mass"],
        "hydration_level": hydration_level,
    }


# ============================================================
# ENVIRONMENTAL DATA
# ============================================================

def generate_environmental_data():

    return {
        "cabin_temperature": random_value(21, 24),
        "cabin_pressure": random_value(99, 103),
        "cabin_humidity": random_value(35, 55),

        "cabin_oxygen": random_value(20.5, 21.0, 2),
        "cabin_co2": random.randint(500, 1500),

        "radiation_dose_rate_usv_h": random_value(5, 30),
        "microgravity_level": random_value(0.0001, 0.01, 5),

        "cabin_air_quality": random.randint(90, 100),
    }


# ============================================================
# SNAPSHOT GENERATOR
# ============================================================

def generate_snapshot():

    validate_mode()

    if SIMULATION_MODE == "NORMAL":

        return {
            "physiological_data": generate_physiological_data(),
            "environmental_data": generate_environmental_data(),

            "system_data": {
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),

                "simulation_mode": SIMULATION_MODE,
                "data_source": "SIMULATED",
            },
        }

    raise ValueError(
        f"No generator available for mode: {SIMULATION_MODE}"
    )


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
# DATA REFRESH
# ============================================================

def refresh_data():
    """
    Generate a new snapshot and update existing dictionaries.

    Existing references to the public dictionaries remain valid.
    """

    snapshot = generate_snapshot()

    physiological_data.clear()
    physiological_data.update(snapshot["physiological_data"])

    environmental_data.clear()
    environmental_data.update(snapshot["environmental_data"])

    system_data.clear()
    system_data.update(snapshot["system_data"])

    return data


# ============================================================
# INITIALIZATION
# ============================================================

refresh_data()