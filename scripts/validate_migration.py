#!/usr/bin/env python
"""
Validate DJ 2.x Migration

This script validates that the DJ 0.x -> DJ 2.x migration was successful by:
1. Connecting to the migrated database (with DJ 2.0)
2. Fetching all blob data from tables
3. Comparing fetched data against original Nightingale golden dataset files
4. Reporting pass/fail for each table and column

Run this AFTER the migration has been applied.

Usage:
    # From scene/ directory (dj2-minimal-migration branch):
    cd /path/to/scene
    source venv/bin/activate

    # Set environment variables for DB connection:
    export DJ_HOST=localhost
    export DJ_PORT=3306
    export DJ_USER=root
    export DJ_PASSWORD=simple

    # Run validation:
    python scripts/validate_migration.py

    # With verbose output:
    python scripts/validate_migration.py --verbose

Environment Variables:
    DJ_HOST: Database host (default: localhost)
    DJ_PORT: Database port (default: 3306)
    DJ_USER: Database user (default: root)
    DJ_PASSWORD: Database password (default: simple)
    TEST_DATA_DIR: Path to test data (default: ../test_data/Celia_Set_14012026)

Exit Codes:
    0: All validations passed
    1: One or more validations failed
    2: Error (connection failed, missing data, etc.)
"""

import argparse
import json
import os
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ==============================================================================
# Path Configuration
# ==============================================================================

SCRIPT_DIR = Path(__file__).parent
SCENE_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = SCENE_ROOT.parent

# Add module paths for imports
DJ_PIPELINE = SCENE_ROOT / "dj_pipeline"
VR4MICE_PATH = DJ_PIPELINE / "vr4mice"
BASE_SCHEMAS_PATH = DJ_PIPELINE / "base" / "base_min_schemas"

for path in [DJ_PIPELINE, VR4MICE_PATH, BASE_SCHEMAS_PATH]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Set required environment variables
os.environ.setdefault("IMG_SRC", "Imagingsource")
os.environ.setdefault("GUI", "false")
os.environ.setdefault("DJ_LAB", "test")


# ==============================================================================
# Configuration
# ==============================================================================

DEFAULT_TEST_DATA_DIR = PROJECT_ROOT / "test_data" / "Celia_Set_14012026"
DATASET_NAME = "Nightingale_2024-08-16_1"
CAMERA_PREFIX = "Imagingsource"
SCHEMA_PREFIX = "test_"


# ==============================================================================
# Helper Functions
# ==============================================================================

def get_state(raw_data, key):
    """Extract state data from pickle's state array."""
    keys = {
        "x_pos": 0,
        "z_pos": 1,
        "head_dir": 2,
        "mouse_can_report": 3,
        "iti": 4,
        "obj_left": 5,
        "mouse_report_correct": 6,
        "report_left": 7,
        "report_right": 8,
        "velocity": 9,
    }

    if key not in keys:
        return None

    data = []
    idx = keys[key]

    for s in raw_data["state"]:
        if idx < len(s):
            data.append(s[idx])
        else:
            data.append(None)

    return data


def configure_datajoint():
    """Configure DataJoint connection from environment variables."""
    import datajoint as dj
    from vr4mice.utils import schema_config

    host = os.environ.get("DJ_HOST", "localhost")
    port = os.environ.get("DJ_PORT", "3306")
    user = os.environ.get("DJ_USER", "root")
    password = os.environ.get("DJ_PASSWORD", "simple")

    dj.config["database.host"] = f"{host}:{port}"
    dj.config["database.user"] = user
    dj.config["database.password"] = password
    dj.config["safemode"] = False

    # Configure schema prefix (DJ 2.0 compatible - uses module variables)
    schema_config._schema_prefix = SCHEMA_PREFIX
    schema_config._create_tables = True

    return dj


def load_original_data(test_data_dir):
    """Load original Nightingale dataset files."""
    print(f"\nLoading original data from: {test_data_dir}")

    # Load pickle
    pickle_path = test_data_dir / f"{DATASET_NAME}.pickle"
    with open(pickle_path, "rb") as f:
        pickle_data = pickle.load(f)
    print(f"  Loaded pickle: {pickle_path.name}")

    # Load JSON
    json_path = test_data_dir / f"{DATASET_NAME}.json"
    with open(json_path, "r") as f:
        json_data = json.load(f)
    print(f"  Loaded JSON: {json_path.name}")

    return {
        "pickle": pickle_data,
        "json": json_data,
    }


def compare_arrays(fetched, original, name, verbose=False):
    """
    Compare two arrays for equality.

    Returns:
        dict with comparison results
    """
    result = {
        "name": name,
        "passed": False,
        "message": "",
        "details": {},
    }

    # Convert to numpy arrays
    fetched_arr = np.array(fetched) if not isinstance(fetched, np.ndarray) else fetched
    original_arr = np.array(original) if not isinstance(original, np.ndarray) else original

    result["details"]["fetched_shape"] = fetched_arr.shape
    result["details"]["original_shape"] = original_arr.shape
    result["details"]["fetched_dtype"] = str(fetched_arr.dtype)
    result["details"]["original_dtype"] = str(original_arr.dtype)

    # Check shape
    if fetched_arr.shape != original_arr.shape:
        result["message"] = f"Shape mismatch: {fetched_arr.shape} vs {original_arr.shape}"
        return result

    # Check if empty
    if fetched_arr.size == 0:
        result["passed"] = True
        result["message"] = "Both arrays empty"
        return result

    # Check values
    try:
        if np.allclose(fetched_arr, original_arr, equal_nan=True, rtol=1e-6):
            result["passed"] = True
            result["message"] = "Values match"

            if verbose:
                result["details"]["mean"] = float(np.nanmean(original_arr))
                result["details"]["std"] = float(np.nanstd(original_arr))
                result["details"]["min"] = float(np.nanmin(original_arr))
                result["details"]["max"] = float(np.nanmax(original_arr))
        else:
            # Find differences
            diff = np.abs(fetched_arr - original_arr)
            max_diff = np.nanmax(diff)
            result["message"] = f"Values differ (max diff: {max_diff})"
            result["details"]["max_diff"] = float(max_diff)

    except Exception as e:
        result["message"] = f"Comparison error: {e}"

    return result


def validate_mousestate(vr4mice, original_data, verbose=False):
    """Validate MouseState table data."""
    print("\n  Validating MouseState table...")

    results = []
    pickle_data = original_data["pickle"]

    # Fetch from DB
    try:
        fetched = (vr4mice.MouseState & f'dataset="{DATASET_NAME}"').fetch1()
    except Exception as e:
        return [{"name": "MouseState.fetch", "passed": False, "message": str(e)}]

    # Compare each blob column
    columns = [
        "x_pos", "z_pos", "head_dir", "mouse_can_report", "iti",
        "obj_left", "mouse_report_correct", "report_left", "report_right", "velocity"
    ]

    for col in columns:
        original = get_state(raw_data=pickle_data, key=col)
        if original is None:
            results.append({
                "name": f"MouseState.{col}",
                "passed": True,
                "message": "Column not in original data (skipped)",
            })
            continue

        result = compare_arrays(
            fetched[col],
            original,
            f"MouseState.{col}",
            verbose=verbose
        )
        results.append(result)

        status = "[PASS]" if result["passed"] else "[FAIL]"
        print(f"    {status} {col}: {result['message']}")

    return results


def validate_state(vr4mice, original_data, verbose=False):
    """Validate State table data."""
    print("\n  Validating State table...")

    results = []
    pickle_data = original_data["pickle"]

    # Fetch from DB
    try:
        fetched = (vr4mice.State & f'dataset="{DATASET_NAME}"').fetch1()
    except Exception as e:
        return [{"name": "State.fetch", "passed": False, "message": str(e)}]

    # Compare each blob column
    columns = [
        ("episode", "episode"),
        ("step", "step"),
        ("step_time", "step_time"),
        ("action", "action"),
        ("reward", "reward"),
        ("terminal", "terminal"),
        ("dlc_x", "dlc_x"),
        ("dlc_y", "dlc_y"),
        ("dlc_heading", "dlc_heading"),
    ]

    for db_col, pickle_key in columns:
        if pickle_key not in pickle_data:
            results.append({
                "name": f"State.{db_col}",
                "passed": True,
                "message": "Column not in original data (skipped)",
            })
            continue

        result = compare_arrays(
            fetched[db_col],
            pickle_data[pickle_key],
            f"State.{db_col}",
            verbose=verbose
        )
        results.append(result)

        status = "[PASS]" if result["passed"] else "[FAIL]"
        print(f"    {status} {db_col}: {result['message']}")

    return results


def validate_metadata(vr4mice, original_data, verbose=False):
    """Validate Metadata table data."""
    print("\n  Validating Metadata table...")

    results = []
    pickle_data = original_data["pickle"]

    # Fetch from DB
    try:
        fetched = (vr4mice.Metadata & f'dataset="{DATASET_NAME}"').fetch1()
    except Exception as e:
        return [{"name": "Metadata.fetch", "passed": False, "message": str(e)}]

    # Compare blob columns that exist in pickle
    columns = [
        ("slit_size", "slit_size"),
        ("trial_slit_depth", "trial_slit_depth"),
        ("block_labels", "block_labels"),
    ]

    for db_col, pickle_key in columns:
        if pickle_key not in pickle_data:
            results.append({
                "name": f"Metadata.{db_col}",
                "passed": True,
                "message": "Column not in original data (skipped)",
            })
            continue

        result = compare_arrays(
            fetched[db_col],
            pickle_data[pickle_key],
            f"Metadata.{db_col}",
            verbose=verbose
        )
        results.append(result)

        status = "[PASS]" if result["passed"] else "[FAIL]"
        print(f"    {status} {db_col}: {result['message']}")

    return results


def validate_dataset(vr4mice, original_data, verbose=False):
    """Validate Dataset table (non-blob sanity check)."""
    print("\n  Validating Dataset table...")

    results = []

    # Fetch from DB
    try:
        fetched = (vr4mice.Dataset & f'dataset="{DATASET_NAME}"').fetch1()
    except Exception as e:
        return [{"name": "Dataset.fetch", "passed": False, "message": str(e)}]

    # Verify dataset name
    if fetched["dataset"] == DATASET_NAME:
        results.append({
            "name": "Dataset.dataset",
            "passed": True,
            "message": f"Dataset name matches: {DATASET_NAME}",
        })
        print(f"    [PASS] dataset: {DATASET_NAME}")
    else:
        results.append({
            "name": "Dataset.dataset",
            "passed": False,
            "message": f"Dataset name mismatch: {fetched['dataset']} vs {DATASET_NAME}",
        })
        print(f"    [FAIL] dataset: name mismatch")

    return results


def print_summary(all_results):
    """Print validation summary."""
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    total = 0
    passed = 0
    failed = 0

    for table, results in all_results.items():
        table_passed = sum(1 for r in results if r["passed"])
        table_total = len(results)

        status = "[PASS]" if table_passed == table_total else "[FAIL]"
        print(f"  {status} {table}: {table_passed}/{table_total} checks passed")

        total += table_total
        passed += table_passed
        failed += (table_total - table_passed)

    print("-" * 60)
    print(f"  TOTAL: {passed}/{total} checks passed")

    if failed == 0:
        print("\n  All validations PASSED!")
        print("  Migration was successful - blob data is intact.")
    else:
        print(f"\n  {failed} validation(s) FAILED!")
        print("  Review the errors above to identify issues.")

    print("=" * 60)

    return failed == 0


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Validate DJ 2.x migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with additional statistics",
    )

    parser.add_argument(
        "--test-data-dir",
        type=Path,
        default=None,
        help="Path to test data directory",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("VALIDATE DJ 2.x MIGRATION")
    print("=" * 60)

    # Get test data directory
    test_data_dir = args.test_data_dir
    if test_data_dir is None:
        test_data_dir = Path(os.environ.get("TEST_DATA_DIR", DEFAULT_TEST_DATA_DIR))

    if not test_data_dir.exists():
        print(f"\nERROR: Test data directory not found: {test_data_dir}")
        sys.exit(2)

    # Configure DataJoint
    print("\nConfiguring DataJoint (DJ 2.x)...")
    dj = configure_datajoint()

    # Test connection
    try:
        conn = dj.conn()
        print(f"  Connected to: {dj.config['database.host']}")
        print(f"  DataJoint version: {dj.__version__}")
    except Exception as e:
        print(f"\nERROR: Could not connect to database: {e}")
        sys.exit(2)

    # Import schema
    print("\nImporting vr4mice schema...")
    try:
        from vr4mice.schema import vr4mice
    except Exception as e:
        print(f"\nERROR: Could not import schema: {e}")
        sys.exit(2)

    # Load original data
    try:
        original_data = load_original_data(test_data_dir)
    except Exception as e:
        print(f"\nERROR: Could not load original data: {e}")
        sys.exit(2)

    # Run validations
    print("\n" + "=" * 60)
    print("RUNNING VALIDATIONS")
    print("=" * 60)

    all_results = {}

    all_results["Dataset"] = validate_dataset(vr4mice, original_data, args.verbose)
    all_results["MouseState"] = validate_mousestate(vr4mice, original_data, args.verbose)
    all_results["State"] = validate_state(vr4mice, original_data, args.verbose)
    all_results["Metadata"] = validate_metadata(vr4mice, original_data, args.verbose)

    # Print summary
    success = print_summary(all_results)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
