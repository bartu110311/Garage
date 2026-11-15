
"""
Astronaut Health Monitoring
Condition Evaluation Engine

Evaluates incoming measurements and reports synthetic
health findings. This is NOT a diagnostic medical system.

The evaluation engine is stateless:
each astronaut snapshot is evaluated independently.
"""

import math
from datetime import datetime, timezone


# ==================================================
# CONFIGURATION
# ==================================================

CONDITION_RULES = {
    "HYPERGLYCEMIA": {
        "title": "Elevated Blood Glucose",
        "measurements": ["blood_glucose"],
        "threshold": 145,
        "unit": "mg/dL",
    },
    "HYPOGLYCEMIA": {
        "title": "Low Blood Glucose",
        "measurements": ["blood_glucose"],
        "threshold": 69,
        "unit": "mg/dL",
    },
    "TACHYCARDIA": {
        "title": "Elevated Heart Rate",
        "measurements": ["heart_rate"],
        "threshold": 105,
        "unit": "bpm",
    },
    "BRADYCARDIA": {
        "title": "Low Heart Rate",
        "measurements": ["heart_rate"],
        "threshold": 55,
        "unit": "bpm",
    },
    "CARDIAC_ARREST": {
        "title": "Cardiac Arrest Simulation",
        "measurements": ["heart_rate"],
        "threshold": 0,
        "unit": "bpm",
    },
    "HYPOTHERMIA": {
        "title": "Low Body Temperature",
        "measurements": ["body_temperature"],
        "threshold": 34.8,
        "unit": "°C",
    },
    "FEVER": {
        "title": "Elevated Body Temperature",
        "measurements": ["body_temperature"],
        "threshold": 37.8,
        "unit": "°C",
    },
    "HYPOXEMIA": {
        "title": "Low Blood Oxygen Saturation",
        "measurements": ["spo2", "respiratory_rate"],
        "threshold": 94,
        "unit": "%",
    },
    "TACHYPNEA": {
        "title": "Elevated Respiratory Rate",
        "measurements": ["respiratory_rate"],
        "threshold": 22,
        "unit": "breaths/min",
    },
    "HYPERTENSION": {
        "title": "Elevated Blood Pressure",
        "measurements": ["systolic_bp", "diastolic_bp"],
        "threshold": 130,
        "unit": "mmHg",
    },
    "HYPOTENSION": {
        "title": "Low Blood Pressure",
        "measurements": ["systolic_bp", "diastolic_bp"],
        "threshold": 99,
        "unit": "mmHg",
    },
}


# Maximum allowed measurement age in seconds.
# These are software freshness limits, not medical limits.

MAX_MEASUREMENT_AGE = {
    "heart_rate": 5,
    "systolic_bp": 180,
    "diastolic_bp": 180,
    "blood_glucose": 180,
    "body_temperature": 30,
    "spo2": 10,
    "respiratory_rate": 5,
}


# SpO2 below this threshold is marked as a
# life-threatening simulation candidate.
SEVERE_HYPOXEMIA_THRESHOLD = 70


# ==================================================
# DATA ACCESS
# ==================================================

MEASUREMENT_GROUPS = {
    "heart_rate": "physiological_data",
    "systolic_bp": "physiological_data",
    "diastolic_bp": "physiological_data",
    "blood_glucose": "physiological_data",
    "body_temperature": "physiological_data",
    "spo2": "physiological_data",
    "respiratory_rate": "physiological_data",
}


def utc_now():
    """
    Return the current timezone-aware UTC timestamp.
    """

    return datetime.now(timezone.utc)


def parse_timestamp(value):
    """
    Parse an ISO 8601 timestamp.

    Naive timestamps are interpreted as UTC.
    Invalid timestamps return None.
    """

    if not isinstance(value, str) or not value.strip():
        return None

    try:
        normalized = value.strip()

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        parsed = datetime.fromisoformat(
            normalized
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)

    except (
        ValueError,
        TypeError,
        AttributeError,
        OverflowError,
    ):
        return None


def get_measurement(snapshot, measurement_name):
    """
    Retrieve a measurement from a snapshot.
    """

    if not isinstance(snapshot, dict):
        return None

    group = MEASUREMENT_GROUPS.get(
        measurement_name
    )

    if group is None:
        return None

    values = snapshot.get(group)

    if not isinstance(values, dict):
        return None

    return values.get(measurement_name)


def get_interpretation_readiness(result):
    """
    Return the interpretation readiness of a validated
    measurement result.

    Missing readiness metadata defaults to True for
    backward compatibility with older snapshots.
    """

    if not isinstance(result, dict):
        return True

    readiness = result.get(
        "interpretation_ready",
        True,
    )

    if not isinstance(readiness, bool):
        return False

    return readiness


# ==================================================
# MEASUREMENT VALIDATION
# ==================================================

def validate_measurement(snapshot, measurement_name):
    """
    Validate a measurement's value and timestamp.

    Possible quality values:
        VALID
        MISSING
        INVALID
        STALE
        UNKNOWN

    UNKNOWN means the value exists but its timestamp
    cannot be reliably interpreted.
    """

    value = get_measurement(
        snapshot,
        measurement_name,
    )

    if value is None:
        return {
            "quality": "MISSING",
            "value": None,
            "measured_at": None,
        }

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        return {
            "quality": "INVALID",
            "value": None,
            "measured_at": None,
        }

    try:
        if not math.isfinite(value):
            return {
                "quality": "INVALID",
                "value": None,
                "measured_at": None,
            }

    except (
        OverflowError,
        TypeError,
        ValueError,
    ):
        return {
            "quality": "INVALID",
            "value": None,
            "measured_at": None,
        }

    all_metadata = snapshot.get(
        "measurement_metadata",
        {},
    )

    if not isinstance(all_metadata, dict):
        all_metadata = {}

    metadata = all_metadata.get(
        measurement_name,
        {},
    )

    if not isinstance(metadata, dict):
        metadata = {}

    measured_at = metadata.get(
        "measured_at"
    )

    parsed_time = parse_timestamp(
        measured_at
    )

    if parsed_time is None:
        return {
            "quality": "UNKNOWN",
            "value": value,
            "measured_at": measured_at,
            "interpretation_ready": metadata.get(
                "interpretation_ready",
                True,
            ),
        }

    age = (
        utc_now() - parsed_time
    ).total_seconds()

    if age < -5:
        quality = "INVALID"

    elif age > MAX_MEASUREMENT_AGE.get(
        measurement_name,
        60,
    ):
        quality = "STALE"

    else:
        quality = "VALID"

    return {
        "quality": quality,
        "value": value,
        "measured_at": measured_at,
        "interpretation_ready": metadata.get(
            "interpretation_ready",
            True,
        ),
        "age_seconds": max(0.0, age),
    }


# ==================================================
# CONDITION EVALUATION
# ==================================================

def evaluate_single_factor(snapshot, condition_id):
    """
    Evaluate conditions that depend on one measurement.
    """

    rule = CONDITION_RULES[condition_id]

    measurement = rule["measurements"][0]

    result = validate_measurement(
        snapshot,
        measurement,
    )

    if result["quality"] != "VALID":
        return None

    value = result["value"]
    threshold = rule["threshold"]

    # Cardiac arrest is only generated by an explicitly
    # valid zero heart-rate measurement.
    if condition_id == "CARDIAC_ARREST":
        detected = value == 0

    # A zero heart rate belongs to CARDIAC_ARREST,
    # not the ordinary bradycardia finding.
    elif condition_id == "BRADYCARDIA":
        detected = 0 < value <= threshold

    elif condition_id in (
        "HYPERGLYCEMIA",
        "TACHYCARDIA",
        "FEVER",
        "TACHYPNEA",
    ):
        detected = value >= threshold

    else:
        detected = value <= threshold

    if not detected:
        return None

    return {
        "observed_value": value,
        "unit": rule["unit"],
        "measured_at": result["measured_at"],
        "quality": result["quality"],
        "interpretation_ready": get_interpretation_readiness(
            result
        ),
    }


def evaluate_blood_pressure(snapshot, condition_id):
    """
    Evaluate blood pressure using systolic and
    diastolic measurements independently.

    One valid measurement can be sufficient to
    detect a synthetic finding.

    Invalid or unavailable companion measurements
    do not invalidate a valid measurement.
    """

    systolic = validate_measurement(
        snapshot,
        "systolic_bp",
    )

    diastolic = validate_measurement(
        snapshot,
        "diastolic_bp",
    )

    valid_systolic = (
        systolic["quality"] == "VALID"
    )

    valid_diastolic = (
        diastolic["quality"] == "VALID"
    )

    if not valid_systolic and not valid_diastolic:
        return None

    if condition_id == "HYPERTENSION":

        detected = (
            (
                valid_systolic
                and systolic["value"] >= 130
            )
            or
            (
                valid_diastolic
                and diastolic["value"] >= 80
            )
        )

    else:

        detected = (
            (
                valid_systolic
                and systolic["value"] <= 99
            )
            or
            (
                valid_diastolic
                and diastolic["value"] <= 64
            )
        )

    if not detected:
        return None

    readiness_values = []

    if valid_systolic:
        readiness_values.append(
            get_interpretation_readiness(systolic)
        )

    if valid_diastolic:
        readiness_values.append(
            get_interpretation_readiness(diastolic)
        )

    return {
        "observed_value": {
            "systolic": (
                systolic["value"]
                if valid_systolic
                else None
            ),
            "diastolic": (
                diastolic["value"]
                if valid_diastolic
                else None
            ),
        },
        "unit": "mmHg",
        "measured_at": {
            "systolic": systolic["measured_at"],
            "diastolic": diastolic["measured_at"],
        },
        "quality": "VALID",
        "interpretation_ready": all(
            readiness_values
        ),
    }


def evaluate_hypoxemia(snapshot):
    """
    Evaluate oxygen saturation.

    Respiratory rate is used as a supporting factor,
    not as a mandatory measurement.

    SpO2 below 70 is marked as a life-threatening
    simulation candidate.
    """

    spo2 = validate_measurement(
        snapshot,
        "spo2",
    )

    respiration = validate_measurement(
        snapshot,
        "respiratory_rate",
    )

    if spo2["quality"] != "VALID":
        return None

    if spo2["value"] > 94:
        return None

    valid_respiration = (
        respiration["quality"] == "VALID"
    )

    supporting_factor = (
        valid_respiration
        and respiration["value"] >= 22
    )

    readiness_values = [
        get_interpretation_readiness(spo2)
    ]

    if valid_respiration:
        readiness_values.append(
            get_interpretation_readiness(respiration)
        )

    return {
        "observed_value": {
            "spo2": spo2["value"],
            "respiratory_rate": (
                respiration["value"]
                if valid_respiration
                else None
            ),
        },
        "unit": "%",
        "measured_at": {
            "spo2": spo2["measured_at"],
            "respiratory_rate": respiration["measured_at"],
        },
        "quality": "VALID",
        "supporting_factor_present": supporting_factor,
        "life_threatening_candidate": (
            spo2["value"] < SEVERE_HYPOXEMIA_THRESHOLD
        ),
        "interpretation_ready": all(
            readiness_values
        ),
    }


# ==================================================
# MAIN EVALUATION FUNCTION
# ==================================================

def evaluate_conditions(snapshot):
    """
    Evaluate all configured synthetic findings
    for one astronaut snapshot.

    This function is stateless:
    it does not store or share results between users.

    Missing, stale, invalid and unknown measurements
    are excluded from condition evaluation and reported
    separately through data_quality.

    Life-threatening findings are marked as candidates.
    Actual alert verification is handled by main.py.
    """

    if not isinstance(snapshot, dict):
        raise TypeError(
            "snapshot must be a dictionary."
        )

    active_conditions = []
    data_quality = {}

    # Validate all measurements used by our rules.
    for measurement in MEASUREMENT_GROUPS:

        result = validate_measurement(
            snapshot,
            measurement,
        )

        if result["quality"] != "VALID":

            quality_details = {
                "quality": result["quality"],
                "measured_at": result["measured_at"],
            }

            if "age_seconds" in result:
                quality_details["age_seconds"] = (
                    result["age_seconds"]
                )

            data_quality[measurement] = quality_details

    # Evaluate each condition independently.
    for condition_id in CONDITION_RULES:

        if condition_id in (
            "HYPERTENSION",
            "HYPOTENSION",
        ):

            result = evaluate_blood_pressure(
                snapshot,
                condition_id,
            )

        elif condition_id == "HYPOXEMIA":

            result = evaluate_hypoxemia(
                snapshot
            )

        else:

            result = evaluate_single_factor(
                snapshot,
                condition_id,
            )

        if result is None:
            continue

        # Default severity.
        status = "CAUTION"

        # Explicit cardiac arrest simulation.
        if condition_id == "CARDIAC_ARREST":
            status = "CRITICAL"

        # Severe hypoxemia takes precedence over
        # the ordinary hypoxemia severity rules.
        elif (
            condition_id == "HYPOXEMIA"
            and result["observed_value"]["spo2"]
            < SEVERE_HYPOXEMIA_THRESHOLD
        ):
            status = "CRITICAL"

        elif (
            condition_id == "HYPOXEMIA"
            and result["observed_value"]["spo2"] <= 92
            and result["supporting_factor_present"]
        ):
            status = "WARNING"

        # Glucose interpretation requires additional
        # context that this simulator does not model.
        if condition_id in (
            "HYPERGLYCEMIA",
            "HYPOGLYCEMIA",
        ):

            result["interpretation_limited"] = True

            result["context_note"] = (
                "Meal timing and fasting status are not modelled. "
                "This is a synthetic observation, not a diagnosis."
            )

        life_threatening_candidate = (
            condition_id == "CARDIAC_ARREST"
            or (
                condition_id == "HYPOXEMIA"
                and result.get(
                    "life_threatening_candidate",
                    False,
                )
            )
        )

        active_conditions.append({

            "id": condition_id,

            "status": status,

            "life_threatening_candidate": (
                life_threatening_candidate
            ),

            "title": CONDITION_RULES[
                condition_id
            ]["title"],

            "description": (
                "A measurement-based synthetic finding was detected."
            ),

            **result,

            "recommendations": [],

            "related_measurements": (
                CONDITION_RULES[
                    condition_id
                ]["measurements"]
            ),

        })

    # Determine overall status from the most severe
    # active synthetic finding.
    severity_order = {
        "NORMAL": 0,
        "CAUTION": 1,
        "WARNING": 2,
        "CRITICAL": 3,
    }

    overall_status = "NORMAL"

    for condition in active_conditions:

        condition_severity = severity_order.get(
            condition["status"],
            0,
        )

        if (
            condition_severity
            > severity_order[overall_status]
        ):

            overall_status = condition["status"]

    return {
        "overall_status": overall_status,
        "active_conditions": active_conditions,
        "data_quality": data_quality,
        "evaluated_at": utc_now().isoformat(),
    }
