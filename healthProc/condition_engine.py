
"""
Astronaut Health Monitoring
Condition Evaluation Engine

Evaluates incoming measurements and reports synthetic
health findings. This is NOT a diagnostic medical system.
"""

from datetime import datetime, timezone


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

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
# These are initial software freshness limits, not medical limits.
MAX_MEASUREMENT_AGE = {
    "heart_rate": 5,
    "systolic_bp": 180,
    "diastolic_bp": 180,
    "blood_glucose": 180,
    "body_temperature": 30,
    "spo2": 10,
    "respiratory_rate": 5,
}


# --------------------------------------------------
# DATA ACCESS
# --------------------------------------------------

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
    return datetime.now(timezone.utc)


def parse_timestamp(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed

    except (ValueError, TypeError, AttributeError):
        return None


def get_measurement(snapshot, measurement_name):
    group = MEASUREMENT_GROUPS.get(measurement_name)

    if group is None:
        return None

    return snapshot.get(group, {}).get(measurement_name)


# --------------------------------------------------
# MEASUREMENT VALIDATION
# --------------------------------------------------

def validate_measurement(snapshot, measurement_name):
    value = get_measurement(snapshot, measurement_name)

    if value is None:
        return {
            "quality": "MISSING",
            "value": None,
            "measured_at": None,
        }

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return {
            "quality": "INVALID",
            "value": None,
            "measured_at": None,
        }

    metadata = snapshot.get(
        "measurement_metadata", {}
    ).get(measurement_name, {})

    measured_at = metadata.get("measured_at")
    parsed_time = parse_timestamp(measured_at)

    if parsed_time is None:
        return {
            "quality": "UNKNOWN",
            "value": value,
            "measured_at": measured_at,
        }

    age = (utc_now() - parsed_time).total_seconds()

    if age < -5:
        quality = "INVALID"

    elif age > MAX_MEASUREMENT_AGE.get(
        measurement_name, 60
    ):
        quality = "STALE"

    else:
        quality = "VALID"

    return {
        "quality": quality,
        "value": value,
        "measured_at": measured_at,
        "interpretation_ready": metadata.get(
            "interpretation_ready", True
        ),
        "age_seconds": max(0, age),
    }


# --------------------------------------------------
# CONDITION EVALUATION
# --------------------------------------------------

def evaluate_single_factor(snapshot, condition_id):
    values = CONDITION_RULES[condition_id]
    measurement = values["measurements"][0]

    result = validate_measurement(snapshot, measurement)

    if result["quality"] != "VALID":
        return None

    value = result["value"]
    threshold = values["threshold"]

    if condition_id in (
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
        "unit": values["unit"],
        "measured_at": result["measured_at"],
        "quality": result["quality"],
        "interpretation_ready": result.get(
            "interpretation_ready", True
        ),
    }


def evaluate_blood_pressure(snapshot, condition_id):
    systolic = validate_measurement(snapshot, "systolic_bp")
    diastolic = validate_measurement(snapshot, "diastolic_bp")

    valid_systolic = systolic["quality"] == "VALID"
    valid_diastolic = diastolic["quality"] == "VALID"

    if not valid_systolic and not valid_diastolic:
        return None

    if condition_id == "HYPERTENSION":
        detected = (
            (valid_systolic and systolic["value"] >= 130)
            or
            (valid_diastolic and diastolic["value"] >= 80)
        )

    else:
        detected = (
            (valid_systolic and systolic["value"] <= 99)
            or
            (valid_diastolic and diastolic["value"] <= 64)
        )

    if not detected:
        return None

    return {
        "observed_value": {
            "systolic": systolic["value"] if valid_systolic else None,
            "diastolic": diastolic["value"] if valid_diastolic else None,
        },
        "unit": "mmHg",
        "measured_at": {
            "systolic": systolic["measured_at"],
            "diastolic": diastolic["measured_at"],
        },
        "quality": "VALID",
        "interpretation_ready": True,
    }


def evaluate_hypoxemia(snapshot):
    spo2 = validate_measurement(snapshot, "spo2")
    respiration = validate_measurement(
        snapshot, "respiratory_rate"
    )

    if spo2["quality"] != "VALID":
        return None

    if spo2["value"] > 94:
        return None

    supporting_factor = (
        respiration["quality"] == "VALID"
        and respiration["value"] >= 22
    )

    return {
        "observed_value": {
            "spo2": spo2["value"],
            "respiratory_rate": (
                respiration["value"]
                if respiration["quality"] == "VALID"
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
        "interpretation_ready": True,
    }


# --------------------------------------------------
# MAIN EVALUATION FUNCTION
# --------------------------------------------------

def evaluate_conditions(snapshot):
    active_conditions = []
    data_quality = {}

    # Validate all measurements used by our rules.
    for measurement in MEASUREMENT_GROUPS:
        result = validate_measurement(snapshot, measurement)

        if result["quality"] != "VALID":
            data_quality[measurement] = {
                "quality": result["quality"],
                "measured_at": result["measured_at"],
            }

    for condition_id in CONDITION_RULES:

        if condition_id in (
            "HYPERTENSION",
            "HYPOTENSION",
        ):
            result = evaluate_blood_pressure(
                snapshot, condition_id
            )

        elif condition_id == "HYPOXEMIA":
            result = evaluate_hypoxemia(snapshot)

        else:
            result = evaluate_single_factor(
                snapshot, condition_id
            )

        if result is None:
            continue

        # Initial severity assignment.
        # These levels are provisional simulation rules.
        status = "CAUTION"

        if condition_id == "HYPOXEMIA" and (
            result["observed_value"]["spo2"] <= 92
            and result["supporting_factor_present"]
        ):
            status = "WARNING"

        if condition_id in (
            "HYPERGLYCEMIA",
            "HYPOGLYCEMIA",
        ):
            result["interpretation_limited"] = True
            result["context_note"] = (
                "Meal timing and fasting status are not modelled. "
                "This is a synthetic observation, not a diagnosis."
            )

        active_conditions.append({
            "id": condition_id,
            "status": status,
            "title": CONDITION_RULES[condition_id]["title"],
            "description": (
                "A measurement-based synthetic finding was detected."
            ),
            **result,
            "recommendations": [],
            "related_measurements": (
                CONDITION_RULES[condition_id]["measurements"]
            ),
        })

    severity_order = {
        "NORMAL": 0,
        "CAUTION": 1,
        "WARNING": 2,
        "CRITICAL": 3,
    }

    overall_status = "NORMAL"

    for condition in active_conditions:
        if severity_order[condition["status"]] > severity_order[overall_status]:
            overall_status = condition["status"]

    return {
        "overall_status": overall_status,
        "active_conditions": active_conditions,
        "data_quality": data_quality,
        "evaluated_at": utc_now().isoformat(),
    }
