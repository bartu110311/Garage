
"""
Astronaut Health Monitoring Backend
Main Application Entry Point
"""

import json
import time

import shuffler
from condition_engine import evaluate_conditions


def collect_and_evaluate():
    """
    Collect the latest synthetic snapshot and evaluate it.
    """

    snapshot = shuffler.generate_snapshot()

    assessment = evaluate_conditions(snapshot)

    return {
        "snapshot": snapshot,
        "assessment": assessment,
    }


def print_result(result):
    """
    Display a readable development output.
    """

    assessment = result["assessment"]

    print("\n" + "=" * 55)
    print("ASTRONAUT HEALTH MONITORING BACKEND")
    print("=" * 55)

    print(f"Overall status: {assessment['overall_status']}")

    print("\nActive findings:")

    if not assessment["active_conditions"]:
        print("No active findings.")

    for condition in assessment["active_conditions"]:
        print(
            f"- {condition['id']}: "
            f"{condition['status']}"
        )

    print("\nData quality issues:")

    if not assessment["data_quality"]:
        print("No detected data quality issues.")

    for measurement, details in assessment["data_quality"].items():
        print(
            f"- {measurement}: "
            f"{details['quality']}"
        )

    print("=" * 55)


def main():
    print("Astronaut Health Monitoring Backend started.")

    try:
        while True:
            result = collect_and_evaluate()

            print_result(result)

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nBackend stopped.")


if __name__ == "__main__":
    main()
