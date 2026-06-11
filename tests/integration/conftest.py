"""
Database integration test fixtures.

Provides:
- MySQL connection configuration for DataJoint
- Pipeline fixture with access to all vr4mice schema modules
- Real data loading fixtures for the golden dataset

Uses 'test_' schema prefix to isolate from any real data.

Requires an external MySQL instance (via docker-compose or CI).
Configure via environment variables:
    DJ_HOST (default: localhost)
    DJ_PORT (default: 3306)
    DJ_USER (default: root)
    DJ_PASSWORD (default: simple)

NOTE: Mocks from parent conftest.py are cleared INSIDE the pipeline fixture,
not at module level. This allows non-database integration tests (like
test_data_roundtrips.py) to use the mocked modules while database tests
use real DataJoint connections.
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest


def pytest_addoption(parser):
    """Add custom pytest options for integration tests."""
    parser.addoption(
        "--regenerate-golden",
        action="store_true",
        default=False,
        help="Regenerate golden master files instead of comparing against them"
    )


# ==============================================================================
# Path Configuration (must happen before DataJoint imports)
# ==============================================================================

# Get paths
TESTS_DIR = Path(__file__).parent.parent
PROJECT_ROOT = TESTS_DIR.parent

# Add module paths - need to add the vr4mice parent so imports like "from vr4mice.schema import vr4mice" work
VR4MICE_PARENT = PROJECT_ROOT / "dj_pipeline"
VR4MICE_PATH = PROJECT_ROOT / "dj_pipeline" / "vr4mice"
VR4MICE_ACTIONS_PATH = PROJECT_ROOT / "dj_pipeline" / "vr4mice" / "actions"
BASE_SCHEMAS_PATH = PROJECT_ROOT / "dj_pipeline" / "base" / "base_min_schemas"
BASE_ACTIONS_PATH = PROJECT_ROOT / "dj_pipeline" / "base" / "base_actions"

for path in [VR4MICE_PARENT, VR4MICE_PATH, VR4MICE_ACTIONS_PATH, BASE_SCHEMAS_PATH, BASE_ACTIONS_PATH]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Set environment variables before any imports
os.environ.setdefault("IMG_SRC", "Imagingsource")
os.environ.setdefault("GUI", "false")
os.environ.setdefault("DJ_LAB", "test")
os.environ.setdefault("EMAIL", "false")  # Disable email sending in tests


# ==============================================================================
# MySQL Connection Fixture
# ==============================================================================

class _MySqlConnection:
    """MySQL connection info from environment variables."""

    def __init__(self):
        self.host = os.environ.get("DJ_HOST", "localhost")
        self.port = int(os.environ.get("DJ_PORT", "3306"))
        self.user = os.environ.get("DJ_USER", "root")
        self.password = os.environ.get("DJ_PASSWORD", "simple")

    def get_container_host_ip(self):
        return self.host

    def get_exposed_port(self, port):
        return self.port


@pytest.fixture(scope="session")
def mysql_container():
    """
    Provide MySQL connection for database integration tests.

    Reads connection details from environment variables.
    Expects MySQL to be running externally (via docker-compose or CI).
    """
    yield _MySqlConnection()


@pytest.fixture(scope="session")
def dj_config(mysql_container):
    """
    Configure DataJoint to connect to the test MySQL container.

    Uses 'test_' schema prefix to isolate test data.

    IMPORTANT: Clears mocks from parent conftest.py so tests can import
    real DataJoint modules instead of MagicMock objects.
    """
    # Clear mocks from parent conftest.py BEFORE importing DataJoint modules
    # This must happen before any test imports vr4mice.schema
    _mocked_modules = [
        'base_schemas',
        'base_schemas.schemas',
        'base_schemas.schemas.mice',
        'vr4mice',
        'vr4mice.utils',
        'vr4mice.utils.logger',
        'vr4mice.actions',
        'vr4mice.actions.keys2tables_base',
        'vr4mice.actions.keys2tables_vr4mice',
        'vr4mice.schema',
    ]
    for _mod in _mocked_modules:
        if _mod in sys.modules:
            del sys.modules[_mod]

    import datajoint as dj

    # Get connection details from container
    host = mysql_container.get_container_host_ip()
    port = mysql_container.get_exposed_port(3306)

    # Configure DataJoint
    dj.config["database.host"] = f"{host}:{port}"
    dj.config["database.user"] = "root"
    dj.config["database.password"] = "simple"
    dj.config["database.use_tls"] = False  # Test containers don't have TLS certificates
    dj.config["safemode"] = False  # Allow dropping schemas in tests

    # Configure schema prefix
    dj.config["database.database_prefix"] = "test_"
    dj.config["database.create_tables"] = True

    # Test connection
    conn = dj.conn()

    yield dj.config

    # Cleanup: drop all test schemas
    try:
        schemas = dj.list_schemas()
        for schema_name in schemas:
            if schema_name.startswith("test_"):
                schema = dj.Schema(schema_name)
                schema.drop(force=True)
    except Exception as e:
        print(f"Warning: Could not cleanup test schemas: {e}")


@pytest.fixture(scope="function")
def clean_schemas(dj_config):
    """
    Ensure clean schemas for each test function.

    Drops and recreates test schemas before each test.
    """
    import datajoint as dj

    # Drop existing test schemas
    schemas = dj.list_schemas()
    for schema_name in schemas:
        if schema_name.startswith("test_"):
            try:
                schema = dj.Schema(schema_name)
                schema.drop(force=True)
            except Exception:
                pass

    yield

    # Cleanup after test (optional, session cleanup handles this too)


# ==============================================================================
# Pipeline Fixture
# ==============================================================================

@pytest.fixture(scope="session")
def pipeline(dj_config):
    """
    Provide access to all vr4mice pipeline modules.

    Session-scoped for performance - schemas are shared across all tests.
    Cleanup is handled by the session-level bulk drop in dj_config teardown.

    Depends on dj_config to ensure MySQL is started and DataJoint is configured.

    IMPORTANT: Pipeline modules are imported INSIDE this fixture (not at module level)
    to ensure MySQL is running before DataJoint tries to connect.

    Returns:
        dict: Dictionary mapping module names to their imported modules
    """
    # Safety net: clear mocks again in case dj_config's clearing was bypassed.
    # dj_config already clears these, but this guards against future refactors.
    _mocked_modules = [
        'base_schemas',
        'base_schemas.schemas',
        'base_schemas.schemas.mice',
        'vr4mice',
        'vr4mice.utils',
        'vr4mice.utils.logger',
        'vr4mice.actions',
        'vr4mice.actions.keys2tables_base',
        'vr4mice.actions.keys2tables_vr4mice',
        'vr4mice.schema',
    ]
    for _mod in _mocked_modules:
        if _mod in sys.modules:
            del sys.modules[_mod]

    # Import pipeline modules after MySQL is ready and mocks are cleared
    from vr4mice.schema import vr4mice as vr4mice_schema

    return {
        # Main schema module
        "vr4mice": vr4mice_schema,
        # Common tables (shortcuts for convenience)
        "Dataset": vr4mice_schema.Dataset,
        "Session": vr4mice_schema.Session,
        "Mouse": vr4mice_schema.Mouse,
        "Rig": vr4mice_schema.Rig,
        "Block": vr4mice_schema.Block,
        "Trial": vr4mice_schema.Trial,
        "Tracking": vr4mice_schema.Tracking,
        "ProcessedTracking": vr4mice_schema.ProcessedTracking,
        "Video": vr4mice_schema.Video,
        "DLC": vr4mice_schema.DLC,
    }


# ==============================================================================
# Test Data Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def test_data_dir():
    """
    Path to test data directory (LFS test data in repo).

    Data lives at dj_pipeline/tests/data/w_photodiode/.
    Run `git lfs pull` to download the test data files.
    """
    data_dir = PROJECT_ROOT / "dj_pipeline" / "tests" / "data" / "w_photodiode"

    if not data_dir.exists():
        pytest.skip(
            f"Test data directory not found at: {data_dir}\n"
            "Run `git lfs pull` to download test data."
        )

    return data_dir


@pytest.fixture(scope="function")
def require_golden_data(test_data_dir, test_dataset_name, test_camera_prefix):
    """
    Ensure golden dataset exists with all required files.
    Skip test if data is not available.

    Tests using this fixture will be automatically skipped if the data
    directory doesn't exist or is missing required files.

    NOTE: This shadows the top-level conftest's require_golden_data
    within integration/. Same purpose, different fixture chain (uses
    test_data_dir instead of golden_session_path).
    """
    # Check required files exist
    required_files = [
        f"{test_dataset_name}.pickle",
        f"{test_dataset_name}.npy",
        f"{test_camera_prefix}_{test_dataset_name}_DLC.hdf5",
        f"{test_camera_prefix}_{test_dataset_name}_TS.npy",
        f"{test_camera_prefix}_{test_dataset_name}_PROC",
    ]

    missing = [f for f in required_files if not (test_data_dir / f).exists()]
    if missing:
        pytest.skip(
            f"Golden dataset incomplete at: {test_data_dir}\n"
            f"Missing files: {missing}"
        )

    return test_data_dir


@pytest.fixture(scope="session")
def test_dataset_name():
    """Name of the test dataset."""
    return "Flamingo_2026-02-05_1"


@pytest.fixture(scope="session")
def test_camera_prefix():
    """Camera prefix for test dataset files."""
    return "Imagingsource"


# ==============================================================================
# Real Data Loading Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def integration_pickle_data(test_data_dir, test_dataset_name):
    """Load pickle data from golden dataset."""
    import pickle

    pickle_path = test_data_dir / f"{test_dataset_name}.pickle"
    if not pickle_path.exists():
        pytest.skip(f"Pickle file not found: {pickle_path}")

    with open(pickle_path, "rb") as f:
        return pickle.load(f)


@pytest.fixture(scope="session")
def integration_json_metadata(test_data_dir, test_dataset_name):
    """Load session metadata from golden dataset (.npy or .json)."""
    npy_path = test_data_dir / f"{test_dataset_name}.npy"
    json_path = test_data_dir / f"{test_dataset_name}.json"

    if npy_path.exists():
        return np.load(npy_path, allow_pickle=True).item()
    elif json_path.exists():
        with open(json_path) as f:
            return json.load(f)
    else:
        pytest.skip(f"Metadata file not found: {npy_path} or {json_path}")


@pytest.fixture(scope="session")
def integration_dlc_dataframe(test_data_dir, test_dataset_name, test_camera_prefix):
    """Load DLC DataFrame from golden dataset."""
    import pandas as pd

    dlc_path = test_data_dir / f"{test_camera_prefix}_{test_dataset_name}_DLC.hdf5"
    if not dlc_path.exists():
        pytest.skip(f"DLC HDF5 file not found: {dlc_path}")

    return pd.read_hdf(dlc_path)


@pytest.fixture(scope="session")
def integration_timestamp_array(test_data_dir, test_dataset_name, test_camera_prefix):
    """Load timestamp array from golden dataset."""
    import numpy as np

    ts_path = test_data_dir / f"{test_camera_prefix}_{test_dataset_name}_TS.npy"
    if not ts_path.exists():
        pytest.skip(f"Timestamp file not found: {ts_path}")

    return np.load(ts_path)


@pytest.fixture(scope="session")
def integration_proc_data(test_data_dir, test_dataset_name, test_camera_prefix):
    """Load processed DLC data from golden dataset."""
    import numpy as np

    proc_path = test_data_dir / f"{test_camera_prefix}_{test_dataset_name}_PROC"
    if not proc_path.exists():
        pytest.skip(f"PROC file not found: {proc_path}")

    return np.load(proc_path, allow_pickle=True)
