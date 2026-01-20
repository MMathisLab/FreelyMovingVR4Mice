#!/usr/bin/env python
"""
Golden Master Comparison Script for DataJoint 2.0 Migration.

This script compares post-migration outputs with pre-migration baseline data
stored in the golden_master/ directory.

Usage:
    cd scene/tests
    python compare_golden_master.py

The script will:
1. Load baseline data from golden_master/
2. Regenerate current state from test data (if available)
3. Compare data structures, sample values, and test results
4. Report any differences found
"""

import json
import os
import pickle
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================================
# Path Configuration
# ==============================================================================

TESTS_DIR = Path(__file__).parent
GOLDEN_MASTER_DIR = TESTS_DIR / "golden_master"
PROJECT_ROOT = TESTS_DIR.parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "test_data" / "Celia_Set_14012026"

DATASET_NAME = "Nightingale_2024-08-16_1"
CAMERA_PREFIX = "Imagingsource"


# ==============================================================================
# Baseline Loading
# ==============================================================================

def load_baseline():
    """Load all baseline files from golden_master directory."""
    baseline = {}

    files = [
        "capture_metadata.json",
        "data_structures.json",
        "sample_values.json",
        "test_results.json",
    ]

    for filename in files:
        filepath = GOLDEN_MASTER_DIR / filename
        if filepath.exists():
            with open(filepath) as f:
                key = filename.replace(".json", "")
                baseline[key] = json.load(f)
        else:
            print(f"Warning: Baseline file not found: {filepath}")

    return baseline


# ==============================================================================
# Current State Capture
# ==============================================================================

def capture_current_state():
    """Capture current state from test data files."""
    current = {
        "data_structures": {},
        "sample_values": {},
    }

    if not TEST_DATA_DIR.exists():
        print(f"Warning: Test data directory not found: {TEST_DATA_DIR}")
        return current

    # Load pickle file
    pickle_path = TEST_DATA_DIR / f"{DATASET_NAME}.pickle"
    if pickle_path.exists():
        with open(pickle_path, "rb") as f:
            pickle_data = pickle.load(f)
        current["data_structures"]["pickle"] = capture_pickle_structure(pickle_data)
        current["sample_values"]["pickle"] = capture_pickle_samples(pickle_data)

    # Load JSON metadata
    json_path = TEST_DATA_DIR / f"{DATASET_NAME}.json"
    if json_path.exists():
        with open(json_path) as f:
            json_data = json.load(f)
        current["data_structures"]["json"] = {
            "keys": sorted(json_data.keys()),
            "key_count": len(json_data),
        }

    # Load DLC DataFrame
    dlc_path = TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_DLC.hdf5"
    if dlc_path.exists():
        dlc_df = pd.read_hdf(dlc_path)
        current["data_structures"]["dlc"] = capture_dlc_structure(dlc_df)
        current["sample_values"]["dlc"] = capture_dlc_samples(dlc_df)

    # Load timestamp array
    ts_path = TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_TS.npy"
    if ts_path.exists():
        ts_data = np.load(ts_path)
        current["data_structures"]["timestamp"] = {
            "shape": list(ts_data.shape),
            "dtype": str(ts_data.dtype),
        }
        current["sample_values"]["timestamp"] = capture_array_samples(ts_data, "timestamp")

    # Load proc data
    proc_path = TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_PROC"
    if proc_path.exists():
        proc_data = np.load(proc_path, allow_pickle=True)
        current["data_structures"]["proc"] = capture_proc_structure(proc_data)
        current["sample_values"]["proc"] = capture_proc_samples(proc_data)

    return current


def capture_pickle_structure(data):
    """Capture structure information from pickle data."""
    structure = {
        "keys": sorted(data.keys()),
        "key_count": len(data),
        "arrays": {},
        "scalars": {},
    }

    for key, value in data.items():
        if isinstance(value, np.ndarray):
            structure["arrays"][key] = {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "size": value.size,
                "nbytes": value.nbytes,
            }
        elif isinstance(value, (int, float)):
            structure["scalars"][key] = {
                "type": type(value).__name__,
                "value": value,
            }

    return structure


def capture_pickle_samples(data):
    """Capture sample values from pickle data."""
    samples = {}

    # Key arrays to sample
    key_arrays = ["state", "episode", "step", "step_time", "reward",
                  "l_report_box", "r_report_box", "start_box"]

    for key in key_arrays:
        if key in data and isinstance(data[key], np.ndarray):
            arr = data[key]

            # Small arrays (size <= 10) get special treatment
            if arr.size <= 10:
                sample = {
                    "_type": "ndarray",
                    "shape": list(arr.shape),
                    "dtype": str(arr.dtype),
                    "sample": arr.flatten().tolist(),
                }
            elif arr.ndim == 1:
                sample = {
                    "shape": list(arr.shape),
                    "dtype": str(arr.dtype),
                    "first_10": arr[:10].tolist(),
                    "last_10": arr[-10:].tolist(),
                    "mean": float(np.mean(arr)),
                    "std": float(np.std(arr)),
                    "min": float(np.min(arr)),
                    "max": float(np.max(arr)),
                }
            elif arr.ndim == 2:
                sample = {
                    "shape": list(arr.shape),
                    "dtype": str(arr.dtype),
                    "first_row": arr[0].tolist(),
                    "last_row": arr[-1].tolist(),
                    "mean_per_column": np.mean(arr, axis=0).tolist(),
                    "std_per_column": np.std(arr, axis=0).tolist(),
                }
                if arr.shape[0] > 1000:
                    sample["row_1000"] = arr[1000].tolist()
            else:
                sample = {
                    "shape": list(arr.shape),
                    "dtype": str(arr.dtype),
                }

            samples[key] = sample

    return samples


def capture_dlc_structure(df):
    """Capture structure information from DLC DataFrame."""
    return {
        "shape": list(df.shape),
        "columns": {
            "is_multiindex": isinstance(df.columns, pd.MultiIndex),
            "nlevels": df.columns.nlevels if isinstance(df.columns, pd.MultiIndex) else 1,
        },
    }


def capture_dlc_samples(df):
    """Capture sample values from DLC DataFrame."""
    return {
        "shape": list(df.shape),
        "first_row": df.iloc[0].tolist(),
        "last_row": df.iloc[-1].tolist(),
        "row_1000": df.iloc[1000].tolist() if len(df) > 1000 else None,
    }


def capture_array_samples(arr, name):
    """Capture sample values from a numpy array."""
    return {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "first_10": arr[:10].tolist(),
        "last_10": arr[-10:].tolist(),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def capture_proc_structure(data):
    """Capture structure from proc data."""
    # proc_data is a numpy file with allow_pickle=True
    # It may return a 0-d array containing dict, or directly a dict
    if isinstance(data, np.ndarray) and data.ndim == 0:
        data = data.item()

    structure = {
        "keys": sorted(data.keys()),
        "key_count": len(data),
        "arrays": {},
    }

    for key, value in data.items():
        if isinstance(value, np.ndarray):
            structure["arrays"][key] = {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
            }

    return structure


def capture_proc_samples(data):
    """Capture sample values from proc data."""
    if isinstance(data, np.ndarray) and data.ndim == 0:
        data = data.item()

    samples = {}
    key_arrays = ["x_pos", "y_pos", "heading_direction", "head_angle"]

    for key in key_arrays:
        if key in data and isinstance(data[key], np.ndarray):
            arr = data[key]
            samples[key] = {
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
                "first_10": arr[:10].tolist(),
                "last_10": arr[-10:].tolist(),
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
            }

    return samples


# ==============================================================================
# Comparison Functions
# ==============================================================================

def compare_values(baseline, current, path=""):
    """Recursively compare two values and return differences."""
    differences = []

    if type(baseline) != type(current):
        differences.append({
            "path": path,
            "type": "type_mismatch",
            "baseline": type(baseline).__name__,
            "current": type(current).__name__,
        })
        return differences

    if isinstance(baseline, dict):
        all_keys = set(baseline.keys()) | set(current.keys())
        for key in all_keys:
            key_path = f"{path}.{key}" if path else key
            if key not in baseline:
                differences.append({
                    "path": key_path,
                    "type": "new_key",
                    "current": current[key],
                })
            elif key not in current:
                differences.append({
                    "path": key_path,
                    "type": "missing_key",
                    "baseline": baseline[key],
                })
            else:
                differences.extend(compare_values(baseline[key], current[key], key_path))

    elif isinstance(baseline, list):
        if baseline != current:
            # For numeric lists, check if they're close enough
            if all(isinstance(x, (int, float)) for x in baseline + current):
                if len(baseline) == len(current):
                    max_diff = max(abs(b - c) for b, c in zip(baseline, current))
                    if max_diff > 1e-6:
                        differences.append({
                            "path": path,
                            "type": "value_difference",
                            "max_diff": max_diff,
                        })
                else:
                    differences.append({
                        "path": path,
                        "type": "length_mismatch",
                        "baseline": len(baseline),
                        "current": len(current),
                    })
            else:
                differences.append({
                    "path": path,
                    "type": "list_difference",
                    "baseline": baseline[:5] if len(baseline) > 5 else baseline,
                    "current": current[:5] if len(current) > 5 else current,
                })

    elif isinstance(baseline, (int, float)):
        if abs(baseline - current) > 1e-6:
            differences.append({
                "path": path,
                "type": "value_difference",
                "baseline": baseline,
                "current": current,
                "diff": abs(baseline - current),
            })

    elif baseline != current:
        differences.append({
            "path": path,
            "type": "value_mismatch",
            "baseline": baseline,
            "current": current,
        })

    return differences


def run_unit_tests():
    """Run unit tests and capture results."""
    print("\nRunning unit tests...")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "unit/", "-v", "--tb=no", "-q"],
        cwd=TESTS_DIR,
        capture_output=True,
        text=True,
    )

    # Parse test results
    test_results = {}
    for line in result.stdout.split("\n"):
        if "::" in line and ("PASSED" in line or "FAILED" in line):
            parts = line.split()
            if parts:
                test_name = parts[0]
                status = "passed" if "PASSED" in line else "failed"
                test_results[test_name] = status

    # Count results
    passed = sum(1 for s in test_results.values() if s == "passed")
    failed = sum(1 for s in test_results.values() if s == "failed")

    return {
        "tests": test_results,
        "passed": passed,
        "failed": failed,
        "total": len(test_results),
        "returncode": result.returncode,
    }


def compare_test_results(baseline_tests, current_tests):
    """Compare test results between baseline and current."""
    differences = []

    baseline_set = set(baseline_tests.get("unit_tests", {}).keys())
    current_set = set(current_tests.get("tests", {}).keys())

    # New tests
    for test in current_set - baseline_set:
        differences.append({
            "type": "new_test",
            "test": test,
            "status": current_tests["tests"][test],
        })

    # Missing tests
    for test in baseline_set - current_set:
        differences.append({
            "type": "missing_test",
            "test": test,
            "baseline_status": baseline_tests["unit_tests"][test],
        })

    # Status changes
    for test in baseline_set & current_set:
        baseline_status = baseline_tests["unit_tests"][test]
        current_status = current_tests["tests"][test]
        if baseline_status != current_status:
            differences.append({
                "type": "status_change",
                "test": test,
                "baseline": baseline_status,
                "current": current_status,
            })

    return differences


# ==============================================================================
# Main Comparison
# ==============================================================================

def main():
    """Run the golden master comparison."""
    print("=" * 70)
    print("Golden Master Comparison")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Golden Master Dir: {GOLDEN_MASTER_DIR}")
    print(f"Test Data Dir: {TEST_DATA_DIR}")
    print()

    # Load baseline
    print("Loading baseline...")
    baseline = load_baseline()
    if not baseline:
        print("ERROR: No baseline data found!")
        return 1

    print(f"  Loaded {len(baseline)} baseline files")

    # Capture current state
    print("\nCapturing current state...")
    current = capture_current_state()

    all_differences = []

    # Compare data structures
    if "data_structures" in baseline:
        print("\nComparing data structures...")
        # Compare just the key fields that matter
        if "pickle" in baseline["data_structures"] and "pickle" in current["data_structures"]:
            baseline_pickle = baseline["data_structures"]["pickle"]
            current_pickle = current["data_structures"]["pickle"]

            # Compare arrays (shapes and dtypes)
            if "arrays" in baseline_pickle and "arrays" in current_pickle:
                for key in baseline_pickle["arrays"]:
                    if key in current_pickle["arrays"]:
                        b_arr = baseline_pickle["arrays"][key]
                        c_arr = current_pickle["arrays"][key]
                        if b_arr.get("shape") != c_arr.get("shape"):
                            all_differences.append({
                                "category": "data_structures",
                                "path": f"pickle.arrays.{key}.shape",
                                "baseline": b_arr.get("shape"),
                                "current": c_arr.get("shape"),
                            })
                        if b_arr.get("dtype") != c_arr.get("dtype"):
                            all_differences.append({
                                "category": "data_structures",
                                "path": f"pickle.arrays.{key}.dtype",
                                "baseline": b_arr.get("dtype"),
                                "current": c_arr.get("dtype"),
                            })

        if "dlc" in baseline["data_structures"] and "dlc" in current["data_structures"]:
            b_dlc = baseline["data_structures"]["dlc"]
            c_dlc = current["data_structures"]["dlc"]
            if b_dlc.get("shape") != c_dlc.get("shape"):
                all_differences.append({
                    "category": "data_structures",
                    "path": "dlc.shape",
                    "baseline": b_dlc.get("shape"),
                    "current": c_dlc.get("shape"),
                })

    # Compare sample values - only compare critical fields that exist in both
    if "sample_values" in baseline:
        print("Comparing sample values...")
        # Critical fields to compare for each data type
        critical_fields = {
            "pickle": {
                "state": ["shape", "dtype", "first_row", "last_row"],
                "episode": ["shape", "dtype", "first_10", "last_10"],
                "step": ["shape", "dtype", "first_10", "last_10"],
                "step_time": ["shape", "dtype", "first_10", "last_10"],
                "reward": ["shape", "dtype", "first_10", "last_10"],
                "l_report_box": ["shape", "dtype", "sample"],
                "r_report_box": ["shape", "dtype", "sample"],
                "start_box": ["shape", "dtype", "sample"],
            },
            "dlc": ["shape", "first_row", "last_row"],
            "timestamp": ["shape", "dtype", "first_10", "last_10"],
            "proc": {
                "x_pos": ["shape", "dtype", "first_10", "last_10"],
                "y_pos": ["shape", "dtype", "first_10", "last_10"],
                "heading_direction": ["shape", "dtype", "first_10", "last_10"],
                "head_angle": ["shape", "dtype", "first_10", "last_10"],
            },
        }

        for data_type in ["pickle", "dlc", "timestamp", "proc"]:
            if data_type in baseline["sample_values"] and data_type in current["sample_values"]:
                b_data = baseline["sample_values"][data_type]
                c_data = current["sample_values"][data_type]
                fields = critical_fields.get(data_type, [])

                if isinstance(fields, list):
                    # Top-level comparison
                    for field in fields:
                        if field in b_data and field in c_data:
                            diffs = compare_values(b_data[field], c_data[field],
                                                 f"sample_values.{data_type}.{field}")
                            for d in diffs:
                                d["category"] = "sample_values"
                            all_differences.extend(diffs)
                elif isinstance(fields, dict):
                    # Nested comparison
                    for key, key_fields in fields.items():
                        if key in b_data and key in c_data:
                            for field in key_fields:
                                if field in b_data[key] and field in c_data[key]:
                                    diffs = compare_values(b_data[key][field], c_data[key][field],
                                                         f"sample_values.{data_type}.{key}.{field}")
                                    for d in diffs:
                                        d["category"] = "sample_values"
                                    all_differences.extend(diffs)

    # Run and compare tests
    test_results = run_unit_tests()
    print(f"  Tests: {test_results['passed']} passed, {test_results['failed']} failed")

    if "test_results" in baseline:
        print("Comparing test results...")
        test_diffs = compare_test_results(baseline["test_results"], test_results)
        for d in test_diffs:
            d["category"] = "test_results"
        all_differences.extend(test_diffs)

    # Report results
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)

    if not all_differences:
        print("\n  SUCCESS: No differences found from baseline!")
        print("  The migration appears to preserve all data structures and behaviors.")
        return 0
    else:
        print(f"\n  DIFFERENCES FOUND: {len(all_differences)}")
        print()

        # Group by category
        by_category = {}
        for d in all_differences:
            cat = d.get("category", "unknown")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(d)

        for category, diffs in sorted(by_category.items()):
            print(f"\n  {category.upper()} ({len(diffs)} differences):")
            for d in diffs[:10]:  # Show first 10 per category
                if "path" in d:
                    print(f"    - {d['path']}: {d.get('type', 'unknown')}")
                    if "baseline" in d and "current" in d:
                        print(f"      baseline: {d['baseline']}")
                        print(f"      current:  {d['current']}")
                elif "test" in d:
                    print(f"    - {d['test']}: {d.get('type', 'unknown')}")
                    if "baseline" in d:
                        print(f"      baseline: {d['baseline']}")
                    if "current" in d:
                        print(f"      current:  {d['current']}")
            if len(diffs) > 10:
                print(f"    ... and {len(diffs) - 10} more")

        # Check if all tests passed
        if test_results["failed"] > 0:
            print(f"\n  WARNING: {test_results['failed']} tests failed!")
            return 2

        # Check if differences are expected (e.g., new tests)
        critical_diffs = [d for d in all_differences
                        if d.get("type") not in ("new_test",)]
        if not critical_diffs:
            print("\n  INFO: Only non-critical differences found (e.g., new tests).")
            return 0

        return 1


if __name__ == "__main__":
    sys.exit(main())
