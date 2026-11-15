
"""
Astronaut Health Monitoring Backend
FastAPI Application Entry Point
Version: 0.4.0

Run from Garage/healthProc:
    python main.py

Or:
    uvicorn main:app --host 0.0.0.0 --port 8080

This is an educational multi-astronaut simulation.
It is NOT a diagnostic medical system.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from itertools import count
from threading import Lock
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import shuffler
from condition_engine import evaluate_conditions, validate_measurement


# ==================================================
# CONFIGURATION
# ==================================================

API_VERSION = "0.4.0"
REFRESH_INTERVAL_SECONDS = 2.0
LIFE_THREATENING_VERIFICATION_SECONDS = 3.0

DEFAULT_ASTRONAUT_ID = "user1"


# ==================================================
# SHARED STATE
# ==================================================

_latest_results: dict[str, dict[str, Any]] = {}

_result_lock = Lock()
_refresh_lock = Lock()
_shuffler_lock = Lock()

# Daily entries are intentionally in-memory only.
_daily_entries: dict[str, dict[str, Any]] = {}
_daily_entry_lock = Lock()

# Alarm verification and acknowledgement state.
_alarm_lock = Lock()

_life_threatening_candidates: dict[str, dict[str, Any]] = {}
_crew_alerts: dict[str, dict[str, Any]] = {}

_alert_id_counter = count(1)


# ==================================================
# REQUEST MODELS
# ==================================================

class ScenarioRequest(BaseModel):
    mode: str = Field(
        default="NORMAL",
        min_length=1,
        max_length=32,
    )

    abnormalities: list[str] | None = Field(
        default=None,
        max_length=len(shuffler.SUPPORTED_ABNORMALITIES),
    )


class DailyEntryRequest(BaseModel):
    astronaut_id: str = Field(
        min_length=1,
        max_length=64,
    )

    sleep_hours: float = Field(
        ge=0,
        le=24,
    )

    fatigue_level: int = Field(
        ge=0,
        le=10,
    )

    stress_level: int = Field(
        ge=0,
        le=10,
    )


class AlertAcknowledgementRequest(BaseModel):
    response: Literal[
        "I_AM_OK",
        "INTERVENING",
    ]


# ==================================================
# GENERAL HELPERS
# ==================================================

def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def get_astronaut_ids() -> tuple[str, ...]:
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
# LIFE-THREATENING ALERT MANAGEMENT
# ==================================================

def get_life_threatening_candidates(
    assessment: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Read explicit life-threatening candidates from
    condition_engine output.

    The API does not infer life-threatening severity
    from CRITICAL status alone.
    """

    candidates = []

    active_conditions = assessment.get(
        "active_conditions",
        [],
    )

    if not isinstance(active_conditions, list):
        active_conditions = []

    for condition in active_conditions:

        if not isinstance(condition, dict):
            continue

        if condition.get("life_threatening_candidate") is True:
            candidates.append(condition)

    # Also support a top-level candidate contract.
    top_level_candidate = assessment.get(
        "life_threatening_candidate"
    )

    if top_level_candidate is True and not candidates:
        candidates.append({
            "id": "LIFE_THREATENING_EVENT",
            "title": "Life-threatening event",
            "status": "CRITICAL",
        })

    elif isinstance(top_level_candidate, dict):
        candidates.append(top_level_candidate)

    # Remove duplicate candidate IDs.
    unique_candidates = {}

    for candidate in candidates:

        candidate_id = str(
            candidate.get(
                "id",
                "LIFE_THREATENING_EVENT",
            )
        )

        unique_candidates[candidate_id] = candidate

    return list(unique_candidates.values())


def update_life_threatening_alerts(
    results: dict[str, dict[str, Any]],
) -> None:
    """
    Verify life-threatening candidates over a continuous
    three-second interval.

    Candidate detection must already account for valid,
    fresh measurements in condition_engine.

    A candidate disappearing resets its verification timer.
    """

    now_monotonic = time.monotonic()
    now_iso = utc_now_iso()

    with _alarm_lock:

        for astronaut_id, result in results.items():

            assessment = result.get(
                "assessment",
                {},
            )

            candidates = get_life_threatening_candidates(
                assessment
            )

            if not candidates:

                _life_threatening_candidates.pop(
                    astronaut_id,
                    None,
                )

                continue

            candidate_ids = sorted(
                str(
                    candidate.get(
                        "id",
                        "LIFE_THREATENING_EVENT",
                    )
                )
                for candidate in candidates
            )

            signature = "|".join(candidate_ids)

            current_state = _life_threatening_candidates.get(
                astronaut_id
            )

            # A changed candidate set starts a new verification period.
            if (
                current_state is None
                or current_state["signature"] != signature
            ):

                _life_threatening_candidates[
                    astronaut_id
                ] = {
                    "signature": signature,
                    "started_at_monotonic": now_monotonic,
                    "started_at": now_iso,
                    "verified": False,
                }

                continue

            elapsed = (
                now_monotonic
                - current_state["started_at_monotonic"]
            )

            if elapsed < LIFE_THREATENING_VERIFICATION_SECONDS:
                continue

            if current_state["verified"]:
                continue

            current_state["verified"] = True

            # Do not create another unacknowledged alert
            # for the same astronaut and candidate signature.
            existing_alert = any(
                alert["astronaut_id"] == astronaut_id
                and alert["signature"] == signature
                and alert.get("resolved_at") is None
                for alert in _crew_alerts.values()
            )

            if existing_alert:
                continue

            alert_id = f"alert-{next(_alert_id_counter)}"

            _crew_alerts[alert_id] = {
                "alert_id": alert_id,
                "astronaut_id": astronaut_id,
                "type": "LIFE_THREATENING",
                "status": "CONFIRMED",
                "life_threatening": True,
                "candidate_conditions": deepcopy(
                    candidates
                ),
                "signature": signature,
                "created_at": now_iso,
                "verification_duration_seconds": round(
                    elapsed,
                    2,
                ),
                "acknowledgement": None,
                "acknowledged_at": None,
                "resolved_at": None,
            }


def get_crew_alerts(
    astronaut_id: str | None = None,
    include_resolved: bool = False,
) -> list[dict[str, Any]]:
    with _alarm_lock:

        alerts = []

        for alert in _crew_alerts.values():

            if (
                astronaut_id is not None
                and alert["astronaut_id"] != astronaut_id
            ):
                continue

            if (
                not include_resolved
                and alert.get("resolved_at") is not None
            ):
                continue

            alerts.append(
                deepcopy(alert)
            )

        return sorted(
            alerts,
            key=lambda item: item["created_at"],
            reverse=True,
        )


def acknowledge_crew_alert(
    alert_id: str,
    response: str,
) -> dict[str, Any]:

    with _alarm_lock:

        alert = _crew_alerts.get(
            alert_id
        )

        if alert is None:
            raise HTTPException(
                status_code=404,
                detail="Alert not found.",
            )

        if alert.get("resolved_at") is not None:
            raise HTTPException(
                status_code=409,
                detail="This alert has already been resolved.",
            )

        if alert.get("acknowledgement") is not None:
            raise HTTPException(
                status_code=409,
                detail="This alert has already been acknowledged.",
            )

        alert["acknowledgement"] = response
        alert["acknowledged_at"] = utc_now_iso()

        if response == "I_AM_OK":
            alert["resolved_at"] = utc_now_iso()
            alert["status"] = "RESOLVED"

        elif response == "INTERVENING":
            alert["status"] = "INTERVENTION_IN_PROGRESS"

        return deepcopy(alert)


# ==================================================
# DATA COLLECTION AND EVALUATION
# ==================================================

def collect_and_evaluate_all() -> dict[str, dict[str, Any]]:

    astronaut_ids = get_astronaut_ids()

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

        snapshot = snapshots.get(
            astronaut_id
        )

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


def publish_results(
    results: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Process alarms and atomically publish the latest
    results for the complete crew.
    """

    global _latest_results

    update_life_threatening_alerts(
        results
    )

    with _result_lock:
        _latest_results = deepcopy(
            results
        )

        return deepcopy(
            _latest_results
        )


def refresh_latest_results() -> dict[str, dict[str, Any]]:

    with _refresh_lock:

        results = collect_and_evaluate_all()

        return publish_results(
            results
        )


def get_latest_result(
    astronaut_id: str,
) -> dict[str, Any]:

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    with _result_lock:
        result = _latest_results.get(
            astronaut_id
        )

        if result is not None:
            return deepcopy(result)

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

    with _result_lock:
        results = deepcopy(
            _latest_results
        )

    if not results:
        results = refresh_latest_results()

    return results


# ==================================================
# SCENARIO MANAGEMENT
# ==================================================

def get_current_scenario(
    astronaut_id: str,
) -> dict[str, Any]:

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

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    with _refresh_lock:

        with _shuffler_lock:

            scenario = shuffler.set_simulation_scenario(
                mode,
                abnormalities,
                astronaut_id=astronaut_id,
            )

            snapshots = shuffler.refresh_all_data(
                include_remote=False
            )

        if not isinstance(snapshots, dict):
            raise RuntimeError(
                "Shuffler returned an invalid snapshot collection."
            )

        results = {}

        for current_id in get_astronaut_ids():

            snapshot = snapshots.get(
                current_id
            )

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

        published = publish_results(
            results
        )

        selected_result = published[
            astronaut_id
        ]

        return scenario, selected_result


# ==================================================
# DAILY ENTRY MANAGEMENT
# ==================================================

def save_daily_entry(
    request: DailyEntryRequest,
) -> dict[str, Any]:

    astronaut_id = validate_astronaut_id(
        request.astronaut_id
    )

    entry = {
        "astronaut_id": astronaut_id,
        "sleep_hours": request.sleep_hours,
        "fatigue_level": request.fatigue_level,
        "stress_level": request.stress_level,
        "recorded_at": utc_now_iso(),
    }

    with _daily_entry_lock:
        _daily_entries[astronaut_id] = entry

    return deepcopy(entry)


def get_daily_entry(
    astronaut_id: str,
) -> dict[str, Any] | None:

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    with _daily_entry_lock:
        entry = _daily_entries.get(
            astronaut_id
        )

        return deepcopy(entry)


# ==================================================
# BACKGROUND REFRESH LOOP
# ==================================================

async def refresh_loop() -> None:

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

    astronaut_ids = get_astronaut_ids()

    print(
        "[Backend] Configured astronauts: "
        + ", ".join(astronaut_ids)
    )

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

def measurement_quality(
    snapshot: dict[str, Any],
    group_name: str,
    measurement_name: str,
) -> str:

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
            OverflowError,
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

        "daily_entry": get_daily_entry(
            result["astronaut_id"]
        ),

        "life_threatening_alerts": get_crew_alerts(
            astronaut_id=result["astronaut_id"]
        ),
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
                "daily_entry": get_daily_entry(astronaut_id),
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
            "daily_entry": get_daily_entry(
                astronaut_id
            ),
            "unresolved_alert_count": len(
                get_crew_alerts(
                    astronaut_id=astronaut_id
                )
            ),
        })

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "crew_count": len(crew_members),
        "crew": crew_members,
        "alerts": get_crew_alerts(),
    }


# ==================================================
# CREW ALERTS
# ==================================================

@app.get("/api/v1/crew/alerts")
async def crew_alert_list(
    astronaut_id: str | None = Query(
        default=None,
    ),
    include_resolved: bool = Query(
        default=False,
    ),
):

    if astronaut_id is not None:
        astronaut_id = validate_astronaut_id(
            astronaut_id
        )

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "alerts": get_crew_alerts(
            astronaut_id=astronaut_id,
            include_resolved=include_resolved,
        ),
    }


@app.post("/api/v1/crew/alerts/{alert_id}/acknowledge")
async def crew_alert_acknowledge(
    alert_id: str,
    request: AlertAcknowledgementRequest,
):

    alert = acknowledge_crew_alert(
        alert_id,
        request.response,
    )

    return {
        "api_version": API_VERSION,
        "generated_at": utc_now_iso(),
        "message": "Alert acknowledgement recorded.",
        "alert": alert,
    }


# ==================================================
# DAILY ENTRY
# ==================================================

@app.post("/api/v1/daily-entry")
async def daily_entry_create(
    request: DailyEntryRequest,
):

    entry = await asyncio.to_thread(
        save_daily_entry,
        request,
    )

    return {
        "api_version": API_VERSION,
        "message": "Daily entry saved successfully.",
        "entry": entry,
    }


@app.get("/api/v1/astronauts/{astronaut_id}/daily-entry")
async def daily_entry_get(
    astronaut_id: str,
):

    astronaut_id = validate_astronaut_id(
        astronaut_id
    )

    entry = get_daily_entry(
        astronaut_id
    )

    return {
        "api_version": API_VERSION,
        "astronaut_id": astronaut_id,
        "generated_at": utc_now_iso(),
        "entry": entry,
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

    return {
        "api_version": API_VERSION,
        "generated_at": shared_data.get(
            "generated_at",
            utc_now_iso(),
        ),
        "environmental_data": shared_data.get(
            "environmental_data",
            {},
        ),
        "measurement_metadata": shared_data.get(
            "environment_measurement_metadata",
            {},
        ),
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
        "data_type": "SYNTHETIC_VISUALIZATION_ONLY",
    }


# ==================================================
# LEGACY USER1 ENDPOINTS
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
