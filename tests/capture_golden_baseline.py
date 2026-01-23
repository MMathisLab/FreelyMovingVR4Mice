#!/usr/bin/env python
"""
Golden Baseline Capture Script for DJ 2.0 Migration

Captures the current test outputs and data structures BEFORE migration
so we can verify the migration didn't break anything.

Run this script with DJ 1.x installed to capture baseline behavior.
After migration to DJ 2.0, run again and compare outputs.

Usage:
    cd scene/tests
    source ../venv/bin/activate
    python capture_golden_baseline.py

Output:
    golden_baseline/
        test_results.json      - Pass/fail for each test
        data_structures.json   - Shapes, dtypes, column names
        sample_values.json     - Small sample of actual values
        capture_metadata.json  - Timestamp, git commit, DJ version
"""

import json
import os
import pickle
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ==============================================================================
# Configuration
# ==============================================================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
GOLDEN_BASELINE_DIR = SCRIPT_DIR / "golden_baseline"

# Test data location
TEST_DATA_DIR = PROJECT_ROOT / "test_data" / "Celia_Set_14012026"
DATASET_NAME = "Nightingale_2024-08-16_1"
CAMERA_PREFIX = "Imagingsource"


# ==============================================================================
# Utility Functions
# ==============================================================================

def ensure_output_dir():
    """Create golden_baseline directory if it doesn't exist."""
    GOLDEN_BASELINE_DIR.mkdir(parents=True, exist_ok=True)


def get_git_commit():
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except Exception:
        pass
    return "unknown"


def get_git_branch():
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def get_datajoint_version():
    """Get installed DataJoint version."""
    try:
        import datajoint as dj
        return dj.__version__
    except ImportError:
        return "not installed"


def tuple_key_to_str(key: Any) -> str:
    """Convert tuple keys (e.g., MultiIndex columns) to JSON-safe strings."""
    if isinstance(key, tuple):
        return "_".join(str(k) for k in key)
    return str(key)


def numpy_to_json(obj: Any) -> Any:
    """Convert numpy types to JSON-serializable types."""
    if isinstance(obj, np.ndarray):
        return {
            "_type": "ndarray",
            "shape": list(obj.shape),
            "dtype": str(obj.dtype),
            "sample": obj.flatten()[:10].tolist() if obj.size > 0 else [],
        }
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, (np.str_, str)):
        return str(obj)
    elif isinstance(obj, dict):
        # Convert tuple keys to strings for JSON compatibility (e.g., MultiIndex columns)
        return {tuple_key_to_str(k): numpy_to_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [numpy_to_json(v) for v in obj]
    elif pd.isna(obj):
        return None
    else:
        return obj


def save_json(data: dict, filename: str):
    """Save data to JSON file in golden_baseline directory."""
    filepath = GOLDEN_BASELINE_DIR / filename
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Saved: {filepath}")


# ==============================================================================
# Test Result Capture
# ==============================================================================

def run_tests_and_capture_results() -> dict:
    """
    Run pytest and capture pass/fail status for each test.

    Returns dict mapping test names to their status.
    """
    print("\n" + "=" * 60)
    print("CAPTURING TEST RESULTS")
    print("=" * 60)

    results = {
        "unit_tests": {},
        "integration_tests": {},
        "summary": {},
    }

    # Run unit tests with JSON output
    print("\nRunning unit tests...")
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "unit/", "-v", "--tb=no", "-q",
                "--collect-only", "-q",
            ],
            capture_output=True,
            text=True,
            cwd=SCRIPT_DIR,
            timeout=300,
        )

        # Parse collected tests
        collected_tests = []
        for line in result.stdout.split("\n"):
            if "::" in line and not line.startswith(" "):
                test_name = line.strip()
                if test_name:
                    collected_tests.append(test_name)

        print(f"  Collected {len(collected_tests)} unit tests")

        # Now run them
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "unit/", "-v", "--tb=short",
            ],
            capture_output=True,
            text=True,
            cwd=SCRIPT_DIR,
            timeout=300,
        )

        # Parse results from output
        passed = 0
        failed = 0
        for line in result.stdout.split("\n"):
            if " PASSED" in line:
                test_name = line.split(" PASSED")[0].strip()
                results["unit_tests"][test_name] = "passed"
                passed += 1
            elif " FAILED" in line:
                test_name = line.split(" FAILED")[0].strip()
                results["unit_tests"][test_name] = "failed"
                failed += 1

        results["summary"]["unit_passed"] = passed
        results["summary"]["unit_failed"] = failed
        results["summary"]["unit_total"] = passed + failed

        print(f"  Unit tests: {passed} passed, {failed} failed")

    except subprocess.TimeoutExpired:
        print("  ERROR: Unit tests timed out")
        results["summary"]["unit_error"] = "timeout"
    except Exception as e:
        print(f"  ERROR running unit tests: {e}")
        results["summary"]["unit_error"] = str(e)

    # Note: Integration tests require Docker, so we just collect them
    print("\nCollecting integration tests (not running - requires Docker)...")
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "integration/", "--collect-only", "-q",
            ],
            capture_output=True,
            text=True,
            cwd=SCRIPT_DIR,
            timeout=60,
        )

        collected = 0
        for line in result.stdout.split("\n"):
            if "::" in line and not line.startswith(" "):
                test_name = line.strip()
                if test_name:
                    results["integration_tests"][test_name] = "not_run"
                    collected += 1

        results["summary"]["integration_collected"] = collected
        print(f"  Collected {collected} integration tests")

    except Exception as e:
        print(f"  ERROR collecting integration tests: {e}")
        results["summary"]["integration_error"] = str(e)

    return results


# ==============================================================================
# Data Structure Capture
# ==============================================================================

def capture_pickle_structure() -> dict:
    """Capture structure of pickle data file."""
    print("\n  Loading pickle data...")

    pickle_path = TEST_DATA_DIR / f"{DATASET_NAME}.pickle"
    if not pickle_path.exists():
        return {"error": f"File not found: {pickle_path}"}

    with open(pickle_path, "rb") as f:
        data = pickle.load(f)

    structure = {
        "filepath": str(pickle_path),
        "keys": list(data.keys()),
        "key_count": len(data),
        "arrays": {},
        "scalars": {},
        "other": {},
    }

    for key, value in data.items():
        if isinstance(value, np.ndarray):
            structure["arrays"][key] = {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "size": value.size,
                "nbytes": value.nbytes,
            }
        elif isinstance(value, (int, float, str, bool)):
            structure["scalars"][key] = {
                "type": type(value).__name__,
                "value": value if not isinstance(value, float) or not np.isnan(value) else "NaN",
            }
        elif isinstance(value, (list, tuple)):
            structure["other"][key] = {
                "type": type(value).__name__,
                "length": len(value),
                "element_types": list(set(type(v).__name__ for v in value[:10])),
            }
        else:
            structure["other"][key] = {
                "type": type(value).__name__,
            }

    print(f"    Keys: {len(data)}")
    print(f"    Arrays: {len(structure['arrays'])}")
    print(f"    Scalars: {len(structure['scalars'])}")

    return structure


def capture_json_structure() -> dict:
    """Capture structure of JSON metadata file."""
    print("\n  Loading JSON metadata...")

    json_path = TEST_DATA_DIR / f"{DATASET_NAME}.json"
    if not json_path.exists():
        return {"error": f"File not found: {json_path}"}

    with open(json_path, "r") as f:
        data = json.load(f)

    def get_structure(obj, depth=0):
        if depth > 3:  # Limit depth
            return {"_truncated": True}
        if isinstance(obj, dict):
            return {k: get_structure(v, depth + 1) for k, v in obj.items()}
        elif isinstance(obj, list):
            if len(obj) == 0:
                return {"_type": "list", "length": 0}
            return {
                "_type": "list",
                "length": len(obj),
                "element_sample": get_structure(obj[0], depth + 1),
            }
        else:
            return {"_type": type(obj).__name__, "_value": obj}

    structure = {
        "filepath": str(json_path),
        "keys": list(data.keys()),
        "key_count": len(data),
        "structure": get_structure(data),
    }

    print(f"    Keys: {len(data)}")

    return structure


def capture_dlc_structure() -> dict:
    """Capture structure of DLC HDF5 file."""
    print("\n  Loading DLC DataFrame...")

    dlc_path = TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_DLC.hdf5"
    if not dlc_path.exists():
        return {"error": f"File not found: {dlc_path}"}

    df = pd.read_hdf(dlc_path)

    structure = {
        "filepath": str(dlc_path),
        "shape": list(df.shape),
        "index": {
            "name": df.index.name,
            "dtype": str(df.index.dtype),
            "length": len(df.index),
            "first_5": df.index[:5].tolist(),
            "last_5": df.index[-5:].tolist(),
        },
        "columns": {
            "is_multiindex": isinstance(df.columns, pd.MultiIndex),
            "nlevels": df.columns.nlevels,
            "names": list(df.columns.names),
        },
        "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
    }

    if isinstance(df.columns, pd.MultiIndex):
        structure["columns"]["levels"] = {
            level_name: list(df.columns.get_level_values(i).unique())
            for i, level_name in enumerate(df.columns.names)
        }
    else:
        structure["columns"]["values"] = list(df.columns)

    print(f"    Shape: {df.shape}")
    print(f"    MultiIndex columns: {structure['columns']['is_multiindex']}")

    return structure


def capture_timestamp_structure() -> dict:
    """Capture structure of timestamp NPY file."""
    print("\n  Loading timestamp array...")

    ts_path = TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_TS.npy"
    if not ts_path.exists():
        return {"error": f"File not found: {ts_path}"}

    data = np.load(ts_path)

    structure = {
        "filepath": str(ts_path),
        "shape": list(data.shape),
        "dtype": str(data.dtype),
        "size": data.size,
        "nbytes": data.nbytes,
        "min": float(np.nanmin(data)),
        "max": float(np.nanmax(data)),
        "first_5": data[:5].tolist(),
        "last_5": data[-5:].tolist(),
    }

    print(f"    Shape: {data.shape}")
    print(f"    Dtype: {data.dtype}")

    return structure


def capture_proc_structure() -> dict:
    """Capture structure of PROC file."""
    print("\n  Loading PROC data...")

    proc_path = TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_PROC"
    if not proc_path.exists():
        return {"error": f"File not found: {proc_path}"}

    data = np.load(proc_path, allow_pickle=True)

    # Handle 0-d array containing dict
    if isinstance(data, np.ndarray) and data.ndim == 0:
        data = data.item()

    if not isinstance(data, dict):
        return {
            "filepath": str(proc_path),
            "type": type(data).__name__,
            "error": "Expected dict",
        }

    structure = {
        "filepath": str(proc_path),
        "keys": list(data.keys()),
        "key_count": len(data),
        "arrays": {},
    }

    for key, value in data.items():
        if isinstance(value, np.ndarray):
            structure["arrays"][key] = {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
            }
        else:
            structure["arrays"][key] = {
                "type": type(value).__name__,
            }

    print(f"    Keys: {len(data)}")

    return structure


def capture_data_structures() -> dict:
    """Capture structures of all data files."""
    print("\n" + "=" * 60)
    print("CAPTURING DATA STRUCTURES")
    print("=" * 60)

    if not TEST_DATA_DIR.exists():
        return {
            "error": f"Test data directory not found: {TEST_DATA_DIR}",
            "note": "Configure RAW_ROOT_DATA_DIR or place data in test_data/",
        }

    structures = {
        "pickle": capture_pickle_structure(),
        "json": capture_json_structure(),
        "dlc": capture_dlc_structure(),
        "timestamp": capture_timestamp_structure(),
        "proc": capture_proc_structure(),
    }

    return structures


# ==============================================================================
# Sample Values Capture
# ==============================================================================

def capture_sample_values() -> dict:
    """Capture sample values for spot-checking after migration."""
    print("\n" + "=" * 60)
    print("CAPTURING SAMPLE VALUES")
    print("=" * 60)

    if not TEST_DATA_DIR.exists():
        return {"error": f"Test data directory not found: {TEST_DATA_DIR}"}

    samples = {}

    # Pickle data samples
    print("\n  Extracting pickle samples...")
    pickle_path = TEST_DATA_DIR / f"{DATASET_NAME}.pickle"
    if pickle_path.exists():
        with open(pickle_path, "rb") as f:
            data = pickle.load(f)

        samples["pickle"] = {}

        # State array samples
        if "state" in data:
            state = data["state"]
            samples["pickle"]["state"] = {
                "shape": list(state.shape),
                "dtype": str(state.dtype),
                "first_row": state[0].tolist(),
                "last_row": state[-1].tolist(),
                "row_1000": state[1000].tolist() if len(state) > 1000 else None,
                "mean_per_column": np.nanmean(state, axis=0).tolist(),
                "std_per_column": np.nanstd(state, axis=0).tolist(),
            }

        # Episode/step samples
        for key in ["episode", "step", "step_time", "reward"]:
            if key in data and isinstance(data[key], np.ndarray):
                arr = data[key]
                samples["pickle"][key] = {
                    "shape": list(arr.shape),
                    "dtype": str(arr.dtype),
                    "first_10": arr[:10].tolist(),
                    "last_10": arr[-10:].tolist(),
                    "mean": float(np.nanmean(arr)),
                    "std": float(np.nanstd(arr)),
                    "min": float(np.nanmin(arr)),
                    "max": float(np.nanmax(arr)),
                }

        # Box coordinates
        for box_key in ["l_report_box", "r_report_box", "start_box"]:
            if box_key in data:
                samples["pickle"][box_key] = numpy_to_json(data[box_key])

        print(f"    Captured {len(samples['pickle'])} pickle samples")

    # DLC DataFrame samples
    print("\n  Extracting DLC samples...")
    dlc_path = TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_DLC.hdf5"
    if dlc_path.exists():
        df = pd.read_hdf(dlc_path)

        samples["dlc"] = {
            "shape": list(df.shape),
            "first_row": df.iloc[0].tolist(),
            "last_row": df.iloc[-1].tolist(),
            "row_1000": df.iloc[1000].tolist() if len(df) > 1000 else None,
            # Convert tuple keys (MultiIndex columns) to strings for JSON serialization
            "column_means": numpy_to_json(df.mean().head(20).to_dict()),
            "column_stds": numpy_to_json(df.std().head(20).to_dict()),
        }

        # Sample specific bodypart if exists
        if ("nose", "x") in df.columns:
            samples["dlc"]["nose_x"] = {
                "first_10": df[("nose", "x")].iloc[:10].tolist(),
                "last_10": df[("nose", "x")].iloc[-10:].tolist(),
                "mean": float(df[("nose", "x")].mean()),
                "std": float(df[("nose", "x")].std()),
            }

        print(f"    Captured DLC samples (shape: {df.shape})")

    # Timestamp samples
    print("\n  Extracting timestamp samples...")
    ts_path = TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_TS.npy"
    if ts_path.exists():
        ts = np.load(ts_path)
        samples["timestamp"] = {
            "shape": list(ts.shape),
            "dtype": str(ts.dtype),
            "first_10": ts[:10].tolist(),
            "last_10": ts[-10:].tolist(),
            "mean": float(np.nanmean(ts)),
            "std": float(np.nanstd(ts)),
            "min": float(np.nanmin(ts)),
            "max": float(np.nanmax(ts)),
        }
        print(f"    Captured timestamp samples (shape: {ts.shape})")

    # PROC samples
    print("\n  Extracting PROC samples...")
    proc_path = TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_PROC"
    if proc_path.exists():
        proc = np.load(proc_path, allow_pickle=True)
        if isinstance(proc, np.ndarray) and proc.ndim == 0:
            proc = proc.item()

        if isinstance(proc, dict):
            samples["proc"] = {}
            for key in ["x_pos", "y_pos", "heading_direction", "head_angle"]:
                if key in proc and isinstance(proc[key], np.ndarray):
                    arr = proc[key]
                    samples["proc"][key] = {
                        "shape": list(arr.shape),
                        "dtype": str(arr.dtype),
                        "first_10": arr[:10].tolist(),
                        "last_10": arr[-10:].tolist(),
                        "mean": float(np.nanmean(arr)),
                        "std": float(np.nanstd(arr)),
                    }
            print(f"    Captured {len(samples['proc'])} PROC samples")

    # Transformation function samples
    print("\n  Extracting transformation function samples...")
    try:
        # Add paths for imports
        sys.path.insert(0, str(SCRIPT_DIR.parent / "dj_pipeline" / "vr4mice" / "analysis"))
        sys.path.insert(0, str(SCRIPT_DIR.parent / "dj_pipeline" / "vr4mice" / "actions"))

        from dlc_helpers import df_to_dj, dj_to_df

        if dlc_path.exists():
            df = pd.read_hdf(dlc_path)

            # Capture df_to_dj output structure
            dj_format = df_to_dj(df)
            samples["transformations"] = {
                "df_to_dj": {
                    "output_keys": list(dj_format.keys()),
                    "data_shape": list(dj_format["data"].shape),
                    "data_dtype": str(dj_format["data"].dtype),
                    "headers_count": len(dj_format["headers"]),
                    "headers_first_5": [list(h) for h in dj_format["headers"][:5]],
                    "scorer": dj_format.get("scorer"),
                    "data_corner_values": {
                        "top_left": dj_format["data"][0, :5].tolist(),
                        "top_right": dj_format["data"][0, -5:].tolist(),
                        "bottom_left": dj_format["data"][-1, :5].tolist(),
                        "bottom_right": dj_format["data"][-1, -5:].tolist(),
                    },
                },
            }

            # Verify round-trip
            reconstructed = dj_to_df(
                dj_format["data"],
                dj_format["headers"],
                dj_format.get("scorer")
            )
            samples["transformations"]["roundtrip"] = {
                "shape_preserved": list(reconstructed.shape) == list(df.shape),
                "values_match": bool(np.allclose(
                    reconstructed.values, df.values, equal_nan=True
                )),
            }

            print("    Captured transformation samples")

    except Exception as e:
        samples["transformations"] = {"error": str(e)}
        print(f"    WARNING: Could not capture transformation samples: {e}")

    return samples


# ==============================================================================
# Metadata Capture
# ==============================================================================

def capture_metadata() -> dict:
    """Capture metadata about the capture run."""
    print("\n" + "=" * 60)
    print("CAPTURING METADATA")
    print("=" * 60)

    metadata = {
        "capture_timestamp": datetime.now().isoformat(),
        "capture_timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "python_version": sys.version,
        "datajoint_version": get_datajoint_version(),
        "git_commit": get_git_commit(),
        "git_branch": get_git_branch(),
        "test_data_dir": str(TEST_DATA_DIR),
        "test_data_exists": TEST_DATA_DIR.exists(),
        "dataset_name": DATASET_NAME,
        "camera_prefix": CAMERA_PREFIX,
        "platform": sys.platform,
        "cwd": str(Path.cwd()),
    }

    # Check for specific files
    metadata["files_present"] = {
        "pickle": (TEST_DATA_DIR / f"{DATASET_NAME}.pickle").exists(),
        "json": (TEST_DATA_DIR / f"{DATASET_NAME}.json").exists(),
        "dlc_hdf5": (TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_DLC.hdf5").exists(),
        "timestamp_npy": (TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_TS.npy").exists(),
        "proc": (TEST_DATA_DIR / f"{CAMERA_PREFIX}_{DATASET_NAME}_PROC").exists(),
    }

    print(f"  Timestamp: {metadata['capture_timestamp']}")
    print(f"  DataJoint: {metadata['datajoint_version']}")
    print(f"  Git commit: {metadata['git_commit']}")
    print(f"  Git branch: {metadata['git_branch']}")
    print(f"  Test data exists: {metadata['test_data_exists']}")

    return metadata


# ==============================================================================
# Main
# ==============================================================================

def print_summary(metadata: dict, test_results: dict, structures: dict, samples: dict):
    """Print summary of captured data."""
    print("\n" + "=" * 60)
    print("CAPTURE SUMMARY")
    print("=" * 60)

    print(f"\nOutput directory: {GOLDEN_BASELINE_DIR}")
    print(f"DataJoint version: {metadata['datajoint_version']}")
    print(f"Git commit: {metadata['git_commit']} ({metadata['git_branch']})")

    print("\nTest Results:")
    summary = test_results.get("summary", {})
    print(f"  Unit tests: {summary.get('unit_passed', 0)} passed, {summary.get('unit_failed', 0)} failed")
    print(f"  Integration tests: {summary.get('integration_collected', 0)} collected (not run)")

    print("\nData Structures Captured:")
    for key, value in structures.items():
        if isinstance(value, dict) and "error" not in value:
            if key == "pickle":
                print(f"  Pickle: {value.get('key_count', 0)} keys, {len(value.get('arrays', {}))} arrays")
            elif key == "dlc":
                print(f"  DLC: shape {value.get('shape', 'unknown')}")
            elif key == "timestamp":
                print(f"  Timestamp: shape {value.get('shape', 'unknown')}")
            elif key == "proc":
                print(f"  PROC: {value.get('key_count', 0)} keys")
            elif key == "json":
                print(f"  JSON: {value.get('key_count', 0)} keys")
        else:
            print(f"  {key}: ERROR - {value.get('error', 'unknown')}")

    print("\nSample Values Captured:")
    for key, value in samples.items():
        if isinstance(value, dict) and "error" not in value:
            print(f"  {key}: {len(value)} items")
        else:
            error = value.get("error", "unknown") if isinstance(value, dict) else str(value)
            print(f"  {key}: ERROR - {error}")

    print("\nFiles created:")
    for filename in ["capture_metadata.json", "test_results.json", "data_structures.json", "sample_values.json"]:
        filepath = GOLDEN_BASELINE_DIR / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"  {filename}: {size:,} bytes")

    print("\n" + "=" * 60)
    print("GOLDEN MASTER CAPTURE COMPLETE")
    print("=" * 60)
    print("\nTo verify after migration:")
    print("  1. Run this script again with DJ 2.0 installed")
    print("  2. Compare the outputs in golden_baseline/")
    print("  3. Use 'diff' or a comparison tool to check for changes")


def main():
    """Main entry point."""
    print("=" * 60)
    print("GOLDEN MASTER CAPTURE SCRIPT")
    print("=" * 60)
    print(f"Capturing current test outputs and data structures")
    print(f"for verification after DJ 2.0 migration.")

    # Create output directory
    ensure_output_dir()

    # Capture everything
    metadata = capture_metadata()
    test_results = run_tests_and_capture_results()
    structures = capture_data_structures()
    samples = capture_sample_values()

    # Save all outputs
    print("\n" + "=" * 60)
    print("SAVING OUTPUTS")
    print("=" * 60)

    save_json(metadata, "capture_metadata.json")
    save_json(test_results, "test_results.json")
    save_json(structures, "data_structures.json")
    save_json(samples, "sample_values.json")

    # Print summary
    print_summary(metadata, test_results, structures, samples)

    return 0


if __name__ == "__main__":
    sys.exit(main())
