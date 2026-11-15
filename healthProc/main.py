
"""
Astronaut Health Monitoring Backend
FastAPI Application Entry Point
Version: 0.3.0

Run from Garage/healthProc:
    python main.py

Or:
    uvicorn main:app --host 0.0.0.0 --port 8080

This is an educational multi-astronaut simulation.
It is NOT a diagnostic medical system.
"""

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import shuffler
from condition_engine import evaluate_conditions, validate_measurement


# ==================================================
# CONFIGURATION
# ==================================================

API_VERSION = "0.3.0"
REFRESH_INTERVAL_SECONDS = 2.0

DEFAULT_ASTRONAUT_ID = "user1"


# Each astronaut has an independent result.
_latest_results: dict[str, dict[str, Any]] = {}

# Protects the latest result dictionary.
_result_lock = Lock()

# Serializes complete refresh and scenario-update operations.
# Prevents an older refresh from overwriting newer scenario results.
_refresh_lock = Lock()

# Protects shared shuffler state.
_shuffler_lock = Lock()


# ==================================================
# REQUEST MODELS
# ==================================================

class ScenarioRequest(BaseModel):
    """
    Request model for changing one astronaut's
    synthetic simulation scenario.
    """

    mode: str = Field(
        default="NORMAL",
        min_length=1,
        max_length=32,
    )

    abnormalities: list[str] | None = Field(
        default=None,
        max_length=len(shuffler.SUPPORTED_ABNORMALITIES),
    )


# ==================================================
# ASTRONAUT HELPERS
# ==================================================

def get_astronaut_ids() -> tuple[str, ...]:
    """
    Return the astronaut identifiers configured
    by the shuffler.
    """

    astronaut_ids = getattr(
        shuffler,
        "ASTRONAUT_IDS",
        None,
    )

    if not isinstance(astronaut_ids, (tuple, list)):
        raise RuntimeError(
            "shuffler.ASTRONAUT_IDS is not configured."
        )

    if not astronaut_ids:
        raise RuntimeError(
            "No astronauts are configured."
        )

    validated_ids = []

    for astronaut_id in astronaut_ids:

        if (
            not isinstance(astronaut_id, str)
            or not astronaut_id.strip()
        ):
            raise RuntimeError(
                "Invalid astronaut identifier in shuffler configuration."
            )

        normalized_id = astronaut_id.strip().lower()

        if normalized_id in validated_ids:
            raise RuntimeError(
                f"Duplicate astronaut identifier: {normalized_id}"
            )

        validated_ids.append(normalized_id)

    return tuple(validated_ids)


def validate_astronaut_id(
    astronaut_id: str,
) -> str:
    """
    Validate and normalize an astronaut identifier
    against the configured crew.
    """

    if not isinstance(astronaut_id, str):
        raise HTTPException(
            status_code=400,
            detail="Astronaut identifier must be a string.",
        )

    normalized_id = astronaut_id.strip().lower()

    if normalized_id not in get_astronaut_ids():
        raise HTTPException(
            status_code=404,
            detail=f"Unknown astronaut: {astronaut_id}",
        )

    return normalized_id


# ==================================================
# DATA COLLECTION AND EVALUATION
# ==================================================

def collect_and_evaluate_all() -> dict[str, dict[str, Any]]:
    """
    Refresh shared data once, then collect and evaluate
    an independent snapshot for every astronaut.

    The shuffler is responsible for maintaining:
    - Independent physiological states.
    - Independent scenario configurations.
    - Shared environmental state.
    - Shared external NASA data.
    """

    astronaut_ids = get_astronaut_ids()

    # The shuffler refreshes the entire crew and shared
    # environment in one operation.
    with _shuffler_lock:
        snapshots = shuffler.generate_all_snapshots(
            include_remote=True
        )

    if not isinstance(snapshots, dict):
        raise RuntimeError(
            "Shuffler returned an invalid snapshot collection."
        )

    results = {}

    for astronaut_id in astronaut_ids:

        snapshot = snapshots.get(astronaut_id)

        if not isinstance(snapshot, dict):
            raise RuntimeError(
                f"Missing or invalid snapshot for {astronaut_id}."
            )

        assessment = evaluate_conditions(
            snapshot
        )

        results[astronaut_id] = {
            "astronaut_id": astronaut_id,
            "snapshot": snapshot,
            "assessment": assessment,
        }

    return results


def refresh_latest_results() -> dict[str, dict[str, Any]]:
    """
    Refresh and atomically replace the latest results
    for all configured astronauts.

    The refresh lock prevents an older refresh from
    overwriting results from a newer scenario update.
    """

    global _latest_results

    with _refresh_lock:

        results = collect_and_evaluate_all()

        with _result_lock:
            _latest_results = results

            return deepcopy(_latest_results)


def get_latest_result(
    astronaut_id: str,
) -> dict[str, Any]:
    """
    Return the latest result for one astronaut.
    """

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    with _result_lock:
        result = _latest_results.get(
            astronaut_id
        )

        if result is not None:
            return deepcopy(result)

    # No result exists yet. Trigger an initial refresh.
    refresh_latest_results()

    with _result_lock:
        result = _latest_results.get(
            astronaut_id
        )

        if result is None:
            raise HTTPException(
                status_code=503,
                detail="Astronaut data is not available yet.",
            )

        return deepcopy(result)


def get_all_latest_results() -> dict[str, dict[str, Any]]:
    """
    Return an independent copy of the latest crew results.
    """

    with _result_lock:
        results = deepcopy(_latest_results)

    if not results:
        results = refresh_latest_results()

    return results


# ==================================================
# SCENARIO MANAGEMENT
# ==================================================

def get_current_scenario(
    astronaut_id: str,
) -> dict[str, Any]:
    """
    Return the active scenario of one astronaut.
    """

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    with _shuffler_lock:
        return shuffler.get_simulation_scenario(
            astronaut_id=astronaut_id
        )


def set_scenario_and_refresh(
    astronaut_id: str,
    mode: str,
    abnormalities: list[str] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Change one astronaut's scenario and immediately
    refresh the crew snapshots and health assessments.

    Only the selected astronaut's scenario is changed.
    Shared environment data is refreshed without
    performing additional remote API requests.
    """

    global _latest_results

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    # Serialize scenario changes with background refreshes.
    with _refresh_lock:

        with _shuffler_lock:

            scenario = shuffler.set_simulation_scenario(
                mode,
                abnormalities,
                astronaut_id=astronaut_id,
            )

            # Advance the crew and shared environment once.
            # Do not make another NASA API request here.
            snapshots = shuffler.refresh_all_data(
                include_remote=False
            )

        if not isinstance(snapshots, dict):
            raise RuntimeError(
                "Shuffler returned an invalid snapshot collection."
            )

        results = {}

        for current_id in get_astronaut_ids():

            snapshot = snapshots.get(current_id)

            if not isinstance(snapshot, dict):
                raise RuntimeError(
                    f"Missing or invalid snapshot for {current_id}."
                )

            assessment = evaluate_conditions(
                snapshot
            )

            results[current_id] = {
                "astronaut_id": current_id,
                "snapshot": snapshot,
                "assessment": assessment,
            }

        # Replace all results together. This ensures that
        # every result belongs to the same refresh cycle.
        with _result_lock:
            _latest_results = results

            selected_result = deepcopy(
                _latest_results[astronaut_id]
            )

        return scenario, selected_result


# ==================================================
# BACKGROUND REFRESH LOOP
# ==================================================

async def refresh_loop() -> None:
    """
    Periodically refresh all astronaut measurements.

    API requests do not independently advance
    the simulation. The background loop owns
    the regular refresh cycle.
    """

    while True:

        try:
            await asyncio.to_thread(
                refresh_latest_results
            )

        except Exception as exc:
            print(
                f"[Backend] Crew data refresh failed: {exc}"
            )

        await asyncio.sleep(
            REFRESH_INTERVAL_SECONDS
        )


# ==================================================
# APPLICATION LIFECYCLE
# ==================================================

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Initialize the crew data and start the
    background refresh task.
    """

    astronaut_ids = get_astronaut_ids()

    print(
        "[Backend] Configured astronauts: "
        + ", ".join(astronaut_ids)
    )

    # Initial crew snapshot.
    await asyncio.to_thread(
        refresh_latest_results
    )

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
        "Educational multi-astronaut health monitoring "
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

    group = snapshot.get(
        group_name,
        {},
    )

    if not isinstance(group, dict):
        return "UNKNOWN"

    value = group.get(
        measurement_name
    )

    if value is None:
        return "MISSING"

    if group_name == "physiological_data":

        try:
            result = validate_measurement(
                snapshot,
                measurement_name,
            )

            return result.get(
                "quality",
                "UNKNOWN",
            )

        except (
            KeyError,
            TypeError,
            AttributeError,
            ValueError,
        ):
            return "UNKNOWN"

    return "UNKNOWN"


def build_measurement(
    snapshot: dict[str, Any],
    group_name: str,
    measurement_name: str,
    value: Any,
) -> dict[str, Any]:
    """
    Convert a raw measurement into the API
    measurement response format.
    """

    metadata = snapshot.get(
        "measurement_metadata",
        {},
    )

    if not isinstance(metadata, dict):
        metadata = {}

    measurement_info = metadata.get(
        measurement_name,
        {},
    )

    if not isinstance(measurement_info, dict):
        measurement_info = {}

    return {
        "value": value,
        "unit": measurement_info.get(
            "unit",
            "unknown",
        ),
        "measured_at": measurement_info.get(
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
    """
    Build telemetry groups for the frontend.

    Physiological measurements are astronaut-specific.
    Environmental measurements are shared.
    """

    telemetry = {}

    groups = (
        "physiological_data",
        "environmental_data",
    )

    for group_name in groups:

        source_group = snapshot.get(
            group_name,
            {},
        )

        if not isinstance(source_group, dict):
            source_group = {}

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

    # Contextual data, not ordinary physiological measurements.
    telemetry["iss_position_data"] = deepcopy(
        snapshot.get(
            "iss_position_data",
            {},
        )
    )

    telemetry["space_weather_data"] = deepcopy(
        snapshot.get(
            "space_weather_data",
            {},
        )
    )

    telemetry["radiation_dosimetry_data"] = deepcopy(
        snapshot.get(
            "radiation_dosimetry_data",
            {},
        )
    )

    return telemetry


def build_dashboard_response(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the complete dashboard response
    for one astronaut.
    """

    snapshot = result["snapshot"]
    assessment = result["assessment"]

    system_data = snapshot.get(
        "system_data",
        {},
    )

    if not isinstance(system_data, dict):
        system_data = {}

    return {
        "api_version": API_VERSION,
        "astronaut_id": result["astronaut_id"],
        "generated_at": utc_now_iso(),

        "simulation_scenario": {
            "mode": system_data.get(
                "simulation_mode",
                "UNKNOWN",
            ),
            "abnormalities": system_data.get(
                "active_abnormalities",
                [],
            ),
            "scenario_type": system_data.get(
                "scenario_type",
                "UNKNOWN",
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


def build_conditions_response(
    result: dict[str, Any],
) -> dict[str, Any]:

    assessment = result["assessment"]

    return {
        "api_version": API_VERSION,
        "astronaut_id": result["astronaut_id"],
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


def build_telemetry_response(
    result: dict[str, Any],
) -> dict[str, Any]:

    return {
        "api_version": API_VERSION,
        "astronaut_id": result["astronaut_id"],
        "generated_at": utc_now_iso(),
        "telemetry": build_telemetry(
            result["snapshot"]
        ),
    }


# ==================================================
# HEALTH CHECK
# ==================================================

@app.get("/health")
async def health_check():

    return {
        "status": "OK",
        "api_version": API_VERSION,
        "timestamp": utc_now_iso(),
    }


# ==================================================
# CREW
# ==================================================

@app.get("/api/v1/crew")
async def crew():

    results = await asyncio.to_thread(
        get_all_latest_results
    )

    crew_members = []

    for astronaut_id in get_astronaut_ids():

        result = results.get(
            astronaut_id
        )

        if result is None:
            crew_members.append({
                "astronaut_id": astronaut_id,
                "status": "UNKNOWN",
                "overall_status": "UNKNOWN",
                "active_conditions": [],
                "scenario": None,
            })
            continue

        snapshot = result["snapshot"]
        assessment = result["assessment"]

        system_data = snapshot.get(
            "system_data",
            {},
        )

        crew_members.append({
            "astronaut_id": astronaut_id,
            "status": "AVAILABLE",
            "overall_status": assessment[
                "overall_status"
            ],
            "active_conditions": assessment[
                "active_conditions"
            ],
            "scenario": {
                "mode": system_data.get(
                    "simulation_mode",
                    "UNKNOWN",
                ),
                "abnormalities": system_data.get(
                    "active_abnormalities",
                    [],
                ),
            },
        })

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "crew_count": len(crew_members),
        "crew": crew_members,
    }


# ==================================================
# SHARED ENVIRONMENT
# ==================================================

@app.get("/api/v1/environment")
async def environment():

    try:
        with _shuffler_lock:
            shared_data = shuffler.get_environment_snapshot()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Shared environmental data is unavailable.",
        ) from exc

    environmental_data = shared_data.get(
        "environmental_data",
        {},
    )

    metadata = shared_data.get(
        "environment_measurement_metadata",
        {},
    )

    return {
        "api_version": API_VERSION,
        "generated_at": shared_data.get(
            "generated_at",
            utc_now_iso(),
        ),
        "environmental_data": environmental_data,
        "measurement_metadata": metadata,
    }


# ==================================================
# SHARED SPACE DATA
# ==================================================

@app.get("/api/v1/space-data")
async def space_data():

    try:
        with _shuffler_lock:
            shared_data = shuffler.get_environment_snapshot()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Shared space data is unavailable.",
        ) from exc

    return {
        "api_version": API_VERSION,
        "generated_at": shared_data.get(
            "generated_at",
            utc_now_iso(),
        ),

        "iss_position_data": shared_data.get(
            "iss_position_data",
            {},
        ),

        "space_weather_data": shared_data.get(
            "space_weather_data",
            {},
        ),

        "radiation_dosimetry_data": shared_data.get(
            "radiation_dosimetry_data",
            {},
        ),
    }


# ==================================================
# ASTRONAUT DASHBOARD
# ==================================================

@app.get("/api/v1/astronauts/{astronaut_id}/dashboard")
async def astronaut_dashboard(
    astronaut_id: str,
):

    result = get_latest_result(
        astronaut_id
    )

    return build_dashboard_response(
        result
    )


# ==================================================
# ASTRONAUT CONDITIONS
# ==================================================

@app.get("/api/v1/astronauts/{astronaut_id}/conditions")
async def astronaut_conditions(
    astronaut_id: str,
):

    result = get_latest_result(
        astronaut_id
    )

    return build_conditions_response(
        result
    )


# ==================================================
# ASTRONAUT TELEMETRY
# ==================================================

@app.get("/api/v1/astronauts/{astronaut_id}/telemetry")
async def astronaut_telemetry(
    astronaut_id: str,
):

    result = get_latest_result(
        astronaut_id
    )

    return build_telemetry_response(
        result
    )


# ==================================================
# ASTRONAUT SCENARIO
# ==================================================

@app.get("/api/v1/astronauts/{astronaut_id}/scenario")
async def astronaut_get_scenario(
    astronaut_id: str,
):

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    scenario = await asyncio.to_thread(
        get_current_scenario,
        astronaut_id,
    )

    return {
        "api_version": API_VERSION,
        "astronaut_id": astronaut_id,
        "generated_at": utc_now_iso(),
        "scenario": scenario,
    }


@app.post("/api/v1/astronauts/{astronaut_id}/scenario")
async def astronaut_change_scenario(
    astronaut_id: str,
    request: ScenarioRequest,
):

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    try:

        scenario, result = await asyncio.to_thread(
            set_scenario_and_refresh,
            astronaut_id,
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
        "astronaut_id": astronaut_id,
        "generated_at": utc_now_iso(),
        "message": (
            "Astronaut simulation scenario updated successfully."
        ),
        "scenario": scenario,
        "overall_status": assessment[
            "overall_status"
        ],
        "active_conditions": assessment[
            "active_conditions"
        ],
    }


# ==================================================
# ASTRONAUT ECG
# ==================================================

def get_ecg_samples_threadsafe(
    astronaut_id: str,
    sample_count: int,
) -> list[float]:

    with _shuffler_lock:
        return shuffler.get_ecg_samples(
            sample_count,
            astronaut_id=astronaut_id,
        )


@app.get("/api/v1/astronauts/{astronaut_id}/ecg")
async def astronaut_ecg(
    astronaut_id: str,
    sample_count: int = Query(
        default=25,
        ge=1,
        le=5000,
    ),
):

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    result = get_latest_result(
        astronaut_id
    )

    snapshot = result["snapshot"]

    try:

        samples = await asyncio.to_thread(
            get_ecg_samples_threadsafe,
            astronaut_id,
            sample_count,
        )

    except (
        TypeError,
        ValueError,
        KeyError,
    ) as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "api_version": API_VERSION,
        "astronaut_id": astronaut_id,
        "generated_at": utc_now_iso(),
        "sample_rate_hz": snapshot.get(
            "system_data",
            {},
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
# LEGACY USER1 ENDPOINTS
# ==================================================
#
# These routes preserve compatibility with the
# original single-astronaut frontend integration.
#
# All legacy routes operate on DEFAULT_ASTRONAUT_ID.
# ==================================================

@app.get("/api/v1/dashboard")
async def dashboard():

    result = get_latest_result(
        DEFAULT_ASTRONAUT_ID
    )

    return build_dashboard_response(
        result
    )


@app.get("/api/v1/conditions")
async def conditions():

    result = get_latest_result(
        DEFAULT_ASTRONAUT_ID
    )

    return build_conditions_response(
        result
    )


@app.get("/api/v1/telemetry")
async def telemetry():

    result = get_latest_result(
        DEFAULT_ASTRONAUT_ID
    )

    return build_telemetry_response(
        result
    )


@app.get("/api/v1/scenario")
async def get_scenario():

    scenario = await asyncio.to_thread(
        get_current_scenario,
        DEFAULT_ASTRONAUT_ID,
    )

    return {
        "api_version": API_VERSION,
        "astronaut_id": DEFAULT_ASTRONAUT_ID,
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
            DEFAULT_ASTRONAUT_ID,
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
        "astronaut_id": DEFAULT_ASTRONAUT_ID,
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


@app.get("/api/v1/ecg")
async def ecg(
    sample_count: int = Query(
        default=25,
        ge=1,
        le=5000,
    ),
):

    return await astronaut_ecg(
        DEFAULT_ASTRONAUT_ID,
        sample_count,
    )


# ==================================================
# TERMINAL DEVELOPMENT OUTPUT
# ==================================================

def print_result(
    result: dict[str, Any],
) -> None:

    assessment = result["assessment"]

    print("\n" + "=" * 55)
    print("ASTRONAUT HEALTH MONITORING BACKEND")
    print(
        f"ASTRONAUT: {result['astronaut_id']}"
    )
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
