
"""
Astronaut Health Monitoring Backend
FastAPI Application Entry Point

Run from Garage/healthProc:
    python main.py

Or:
    uvicorn main:app --host 0.0.0.0 --port 8080

This is an educational simulation.
It is NOT a diagnostic medical system.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import shuffler
from condition_engine import evaluate_conditions, validate_measurement


# ==================================================
# CONFIGURATION
# ==================================================

API_VERSION = "0.1"
REFRESH_INTERVAL_SECONDS = 2.0

_latest_result: dict[str, Any] | None = None

_result_lock = Lock()

# Protect shared shuffler state from concurrent access.
_shuffler_lock = Lock()


# ==================================================
# REQUEST MODELS
# ==================================================

class ScenarioRequest(BaseModel):
    """
    Request model for changing the synthetic simulation scenario.
    """

    mode: str = "NORMAL"
    abnormalities: list[str] | None = None


# ==================================================
# DATA COLLECTION AND EVALUATION
# ==================================================

def collect_and_evaluate() -> dict[str, Any]:
    """
    Collect the latest synthetic snapshot
    and evaluate its measurements.
    """

    with _shuffler_lock:
        snapshot = shuffler.generate_snapshot()

    assessment = evaluate_conditions(snapshot)

    return {
        "snapshot": snapshot,
        "assessment": assessment,
    }


def refresh_latest_result() -> dict[str, Any]:
    """
    Refresh the shared backend result.
    """

    global _latest_result

    result = collect_and_evaluate()

    with _result_lock:
        _latest_result = result

    return result


def get_latest_result() -> dict[str, Any]:
    """
    Return the latest available result.
    """

    with _result_lock:
        result = _latest_result

    if result is None:
        result = refresh_latest_result()

    return result


def get_current_scenario() -> dict[str, Any]:
    """
    Return the current scenario from the active
    shuffler instance.
    """

    with _shuffler_lock:
        return shuffler.get_simulation_scenario()


def set_scenario_and_refresh(
    mode: str,
    abnormalities: list[str] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Change the scenario and immediately generate
    a new snapshot and health assessment.

    The scenario change and snapshot generation
    are protected by the same lock.
    """

    global _latest_result

    with _shuffler_lock:

        scenario = shuffler.set_simulation_scenario(
            mode,
            abnormalities,
        )

        snapshot = shuffler.generate_snapshot()

    assessment = evaluate_conditions(snapshot)

    result = {
        "snapshot": snapshot,
        "assessment": assessment,
    }

    with _result_lock:
        _latest_result = result

    return scenario, result


async def refresh_loop() -> None:
    """
    Refresh simulation data periodically.

    API requests do not independently trigger
    simulator updates.
    """

    while True:

        try:
            await asyncio.to_thread(
                refresh_latest_result
            )

        except Exception as exc:
            print(
                f"[Backend] Data refresh failed: {exc}"
            )

        await asyncio.sleep(
            REFRESH_INTERVAL_SECONDS
        )


# ==================================================
# APPLICATION LIFECYCLE
# ==================================================

@asynccontextmanager
async def lifespan(_app: FastAPI):

    # Initial snapshot
    await asyncio.to_thread(
        refresh_latest_result
    )

    # Background refresh task
    task = asyncio.create_task(
        refresh_loop()
    )

    try:
        yield

    finally:
        task.cancel()

        try:
            await task

        except asyncio.CancelledError:
            pass


# ==================================================
# FASTAPI APPLICATION
# ==================================================

app = FastAPI(
    title="Astronaut Health Monitoring API",
    description=(
        "Educational astronaut health monitoring "
        "simulation. Not a diagnostic medical system."
    ),
    version=API_VERSION,
    lifespan=lifespan,
)


# ==================================================
# CORS CONFIGURATION
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# RESPONSE HELPERS
# ==================================================

def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def measurement_quality(
    snapshot: dict[str, Any],
    group_name: str,
    measurement_name: str,
) -> str:
    """
    Determine measurement quality.

    Measurements supported by condition_engine
    use its freshness validation.

    Other measurements remain UNKNOWN until
    dedicated validation rules are implemented.
    """

    value = snapshot.get(
        group_name, {}
    ).get(measurement_name)

    if value is None:
        return "MISSING"

    if group_name == "physiological_data":

        try:
            result = validate_measurement(
                snapshot,
                measurement_name,
            )

            return result["quality"]

        except (
            KeyError,
            TypeError,
            AttributeError,
        ):
            return "UNKNOWN"

    return "UNKNOWN"


def build_measurement(
    snapshot: dict[str, Any],
    group_name: str,
    measurement_name: str,
    value: Any,
) -> dict[str, Any]:

    metadata = snapshot.get(
        "measurement_metadata", {}
    ).get(measurement_name, {})

    return {
        "value": value,
        "unit": metadata.get(
            "unit", "unknown"
        ),
        "measured_at": metadata.get(
            "measured_at"
        ),
        "quality": measurement_quality(
            snapshot,
            group_name,
            measurement_name,
        ),
    }


def build_telemetry(
    snapshot: dict[str, Any],
) -> dict[str, Any]:

    telemetry = {}

    groups = (
        "physiological_data",
        "environmental_data",
    )

    for group_name in groups:

        source_group = snapshot.get(
            group_name, {}
        )

        telemetry_group = {}

        for measurement_name, value in source_group.items():

            telemetry_group[measurement_name] = (
                build_measurement(
                    snapshot,
                    group_name,
                    measurement_name,
                    value,
                )
            )

        telemetry[group_name] = telemetry_group

    # Contextual data, not ordinary physiological measurements
    telemetry["iss_position_data"] = (
        snapshot.get("iss_position_data", {})
    )

    telemetry["space_weather_data"] = (
        snapshot.get("space_weather_data", {})
    )

    telemetry["radiation_dosimetry_data"] = (
        snapshot.get(
            "radiation_dosimetry_data", {}
        )
    )

    return telemetry


def build_dashboard_response(
    result: dict[str, Any],
) -> dict[str, Any]:

    snapshot = result["snapshot"]
    assessment = result["assessment"]
    system_data = snapshot.get("system_data", {})

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "simulation_scenario": {
            "mode": system_data.get(
                "simulation_mode", "UNKNOWN"
            ),
            "abnormalities": system_data.get(
                "active_abnormalities", []
            ),
            "scenario_type": system_data.get(
                "scenario_type", "UNKNOWN"
            ),
        },
        "overall_status": assessment[
            "overall_status"
        ],
        "active_conditions": assessment[
            "active_conditions"
        ],
        "telemetry": build_telemetry(
            snapshot
        ),
        "data_quality": assessment[
            "data_quality"
        ],
    }


# ==================================================
# API ENDPOINTS
# ==================================================

@app.get("/health")
async def health_check():

    return {
        "status": "OK",
        "api_version": API_VERSION,
        "timestamp": utc_now_iso(),
    }


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.get("/api/v1/dashboard")
async def dashboard():

    result = get_latest_result()

    return build_dashboard_response(
        result
    )


# --------------------------------------------------
# CONDITIONS
# --------------------------------------------------

@app.get("/api/v1/conditions")
async def conditions():

    assessment = get_latest_result()[
        "assessment"
    ]

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "overall_status": assessment[
            "overall_status"
        ],
        "active_conditions": assessment[
            "active_conditions"
        ],
        "data_quality": assessment[
            "data_quality"
        ],
    }


# --------------------------------------------------
# TELEMETRY
# --------------------------------------------------

@app.get("/api/v1/telemetry")
async def telemetry():

    snapshot = get_latest_result()[
        "snapshot"
    ]

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "telemetry": build_telemetry(
            snapshot
        ),
    }


# --------------------------------------------------
# SIMULATION SCENARIO
# --------------------------------------------------

@app.get("/api/v1/scenario")
async def get_scenario():

    scenario = await asyncio.to_thread(
        get_current_scenario
    )

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "scenario": scenario,
    }


@app.post("/api/v1/scenario")
async def change_scenario(
    request: ScenarioRequest,
):

    try:

        scenario, result = await asyncio.to_thread(
            set_scenario_and_refresh,
            request.mode,
            request.abnormalities,
        )

    except (TypeError, ValueError) as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    assessment = result["assessment"]

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "message": "Simulation scenario updated successfully.",
        "scenario": scenario,
        "overall_status": assessment[
            "overall_status"
        ],
        "active_conditions": assessment[
            "active_conditions"
        ],
    }


# --------------------------------------------------
# ECG
# --------------------------------------------------

def get_ecg_samples_threadsafe(
    sample_count: int,
) -> list[float]:

    with _shuffler_lock:
        return shuffler.get_ecg_samples(
            sample_count
        )


@app.get("/api/v1/ecg")
async def ecg(
    sample_count: int = Query(
        default=25,
        ge=1,
        le=5000,
    )
):

    result = get_latest_result()
    snapshot = result["snapshot"]

    try:

        samples = await asyncio.to_thread(
            get_ecg_samples_threadsafe,
            sample_count,
        )

    except (
        TypeError,
        ValueError,
    ) as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "sample_rate_hz": snapshot.get(
            "system_data", {}
        ).get(
            "ecg_sample_rate_hz",
            shuffler.ECG_SAMPLE_RATE_HZ,
        ),
        "unit": "mV",
        "sample_count": len(samples),
        "samples": samples,
        "data_type": (
            "SYNTHETIC_VISUALIZATION_ONLY"
        ),
    }


# ==================================================
# TERMINAL DEVELOPMENT OUTPUT
# ==================================================

def print_result(
    result: dict[str, Any],
) -> None:

    assessment = result["assessment"]

    print("\n" + "=" * 55)
    print("ASTRONAUT HEALTH MONITORING BACKEND")
    print("=" * 55)

    print(
        f"Overall status: "
        f"{assessment['overall_status']}"
    )

    print("\nActive findings:")

    if not assessment["active_conditions"]:
        print("No active findings.")

    for condition in assessment[
        "active_conditions"
    ]:

        print(
            f"- {condition['id']}: "
            f"{condition['status']}"
        )

    print("\nData quality issues:")

    if not assessment["data_quality"]:
        print("No detected data quality issues.")

    for measurement, details in assessment[
        "data_quality"
    ].items():

        print(
            f"- {measurement}: "
            f"{details['quality']}"
        )

    print("=" * 55)


# ==================================================
# APPLICATION ENTRY POINT
# ==================================================

def main():

    import uvicorn

    print(
        "Astronaut Health Monitoring Backend starting..."
    )

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
    )


if __name__ == "__main__":
    main()
