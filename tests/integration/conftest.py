"""
Database integration test fixtures using testcontainers.

Provides:
- MySQL container that automatically starts/stops for tests
- Pipeline fixture with access to all vr4mice schema modules
- File manifest tracking for documenting required test data files

Uses 'test_' schema prefix to isolate from any real data.

NOTE: Mocks from parent conftest.py are cleared INSIDE the pipeline fixture,
not at module level. This allows non-database integration tests (like
test_data_roundtrips.py) to use the mocked modules while database tests
use real DataJoint connections.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

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
# File Manifest Tracking
# ==============================================================================

# Global list to track file accesses during tests
_FILE_MANIFEST = []


def track_file_access(file_path: Path, context: str = ""):
    """
    Record a file access for manifest generation.

    Args:
        file_path: Path to the file being accessed
        context: Optional context (e.g., test name) for the access
    """
    if file_path.is_file():
        _FILE_MANIFEST.append({
            "path": str(file_path),
            "filename": file_path.name,
            "size_bytes": file_path.stat().st_size,
            "context": context,
            "timestamp": datetime.now().isoformat(),
        })


@pytest.fixture(scope="module", autouse=True)
def save_file_manifest(request):
    """
    Auto-save file manifest at end of each test module.

    Manifests are saved to tests/fixtures/manifests/{module_name}_manifest.json
    This documents which test data files each module requires.
    """
    # Clear manifest at start of module
    _FILE_MANIFEST.clear()

    yield

    # Save manifest at end of module (if any files were tracked)
    if _FILE_MANIFEST:
        manifest_dir = TESTS_DIR / "fixtures" / "manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        # Get module name from request
        module_name = request.module.__name__.split(".")[-1]
        manifest_path = manifest_dir / f"{module_name}_manifest.json"

        # Deduplicate by path
        unique_files = {}
        for entry in _FILE_MANIFEST:
            path = entry["path"]
            if path not in unique_files:
                unique_files[path] = entry

        manifest_data = {
            "module": request.module.__name__,
            "generated_at": datetime.now().isoformat(),
            "files": list(unique_files.values()),
            "total_size_bytes": sum(f["size_bytes"] for f in unique_files.values()),
        }

        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2)


# ==============================================================================
# MySQL Container Fixture (with external container support)
# ==============================================================================

def _use_external_mysql():
    """Check if we should use an external MySQL container instead of testcontainers."""
    return os.environ.get("DJ_USE_EXTERNAL_CONTAINERS", "").lower() in ("1", "true", "yes")


class ExternalMySqlContainer:
    """
    Wrapper that mimics testcontainers interface for external MySQL.

    Allows using docker-compose MySQL or any external MySQL instance.
    Configure via environment variables:
        DJ_USE_EXTERNAL_CONTAINERS=1
        DJ_HOST=localhost (default)
        DJ_PORT=3306 (default)
        DJ_USER=root (default)
        DJ_PASSWORD=simple (default)
    """

    def __init__(self):
        self.host = os.environ.get("DJ_HOST", "localhost")
        self.port = int(os.environ.get("DJ_PORT", "3306"))
        self.user = os.environ.get("DJ_USER", "root")
        self.password = os.environ.get("DJ_PASSWORD", "simple")

    def get_container_host_ip(self):
        return self.host

    def get_exposed_port(self, port):
        return self.port

    def start(self):
        # External container already running
        pass

    def stop(self):
        # Don't stop external container
        pass


@pytest.fixture(scope="session")
def mysql_container():
    """
    Provide MySQL connection for database integration tests.

    Supports two modes:
    1. testcontainers (default): Automatically starts/stops MySQL container
    2. external: Uses existing MySQL instance (set DJ_USE_EXTERNAL_CONTAINERS=1)

    External mode is useful for:
    - CI environments where Docker-in-Docker is problematic
    - Development with docker-compose already running
    - WSL environments with Docker connectivity issues
    """
    if _use_external_mysql():
        # Use external MySQL (docker-compose or other)
        container = ExternalMySqlContainer()
        container.start()  # No-op for external
        yield container
        container.stop()  # No-op for external
    else:
        # Use testcontainers to start MySQL
        from testcontainers.mysql import MySqlContainer

        container = MySqlContainer(
            image="datajoint/mysql:5.7",
            username="root",
            password="simple",
            dbname="test_db",
        )

        container.start()

        # Wait for MySQL to be ready (datajoint/mysql can take a moment)
        time.sleep(5)

        yield container

        container.stop()


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
    from vr4mice.utils import schema_config

    # Get connection details from container
    host = mysql_container.get_container_host_ip()
    port = mysql_container.get_exposed_port(3306)

    # Configure DataJoint
    dj.config["database.host"] = f"{host}:{port}"
    dj.config["database.user"] = "root"
    dj.config["database.password"] = "simple"
    dj.config["safemode"] = False  # Allow dropping schemas in tests

    # Configure schema prefix (DJ 2.0 compatible - uses module variables)
    schema_config._schema_prefix = "test_"
    schema_config._create_tables = True

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
    # Clear mocks from parent conftest.py so we can import the REAL modules
    # This must happen before importing the real pipeline modules
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
# Test Data Fixtures (with manifest tracking)
# ==============================================================================

@pytest.fixture(scope="session")
def test_data_dir():
    """
    Path to test data directory with graceful skipping.

    Uses PROJECT_ROOT/test_data/golden_dataset/ for development setup.
    Falls back to RAW_ROOT_DATA_DIR if set in environment.
    """
    # Primary location (inside project directory)
    data_dir = PROJECT_ROOT / "test_data" / "golden_dataset"

    if not data_dir.exists():
        # Fallback to RAW_ROOT_DATA_DIR
        raw_root = os.environ.get("RAW_ROOT_DATA_DIR", "")
        if raw_root:
            data_dir = Path(raw_root) / "golden_dataset"

    if not data_dir.exists():
        pytest.skip(
            f"Test data directory not found at: {data_dir}\n"
            "Configure RAW_ROOT_DATA_DIR in .env.test.local to enable integration tests.\n"
            "See .env.test.local.example for configuration instructions."
        )

    return data_dir


@pytest.fixture(scope="function")
def require_nightingale_data(test_data_dir, test_dataset_name, test_camera_prefix):
    """
    Ensure Nightingale golden dataset exists with all required files.
    Skip test if data is not available.

    Tests using this fixture will be automatically skipped if the data
    directory doesn't exist or is missing required files.
    """
    # Check required files exist
    required_files = [
        f"{test_dataset_name}.pickle",
        f"{test_dataset_name}.json",
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
    return "Nightingale_2024-08-16_1"


@pytest.fixture(scope="session")
def test_camera_prefix():
    """Camera prefix for test dataset files."""
    return "Imagingsource"


# ==============================================================================
# Real Data Loading Fixtures (with manifest tracking)
# ==============================================================================

@pytest.fixture(scope="session")
def integration_pickle_data(test_data_dir, test_dataset_name, request):
    """
    Load pickle data from golden dataset with manifest tracking.

    Automatically tracks file access for manifest generation.
    """
    import pickle

    pickle_path = test_data_dir / f"{test_dataset_name}.pickle"
    if not pickle_path.exists():
        pytest.skip(f"Pickle file not found: {pickle_path}")

    # Track file access
    track_file_access(pickle_path, request.node.name if hasattr(request, 'node') else "")

    with open(pickle_path, "rb") as f:
        return pickle.load(f)


@pytest.fixture(scope="session")
def integration_json_metadata(test_data_dir, test_dataset_name, request):
    """
    Load JSON metadata from golden dataset with manifest tracking.
    """
    json_path = test_data_dir / f"{test_dataset_name}.json"
    if not json_path.exists():
        pytest.skip(f"JSON file not found: {json_path}")

    # Track file access
    track_file_access(json_path, request.node.name if hasattr(request, 'node') else "")

    with open(json_path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def integration_dlc_dataframe(test_data_dir, test_dataset_name, test_camera_prefix, request):
    """
    Load DLC DataFrame from golden dataset with manifest tracking.
    """
    import pandas as pd

    dlc_path = test_data_dir / f"{test_camera_prefix}_{test_dataset_name}_DLC.hdf5"
    if not dlc_path.exists():
        pytest.skip(f"DLC HDF5 file not found: {dlc_path}")

    # Track file access
    track_file_access(dlc_path, request.node.name if hasattr(request, 'node') else "")

    return pd.read_hdf(dlc_path)


@pytest.fixture(scope="session")
def integration_timestamp_array(test_data_dir, test_dataset_name, test_camera_prefix, request):
    """
    Load timestamp array from golden dataset with manifest tracking.
    """
    import numpy as np

    ts_path = test_data_dir / f"{test_camera_prefix}_{test_dataset_name}_TS.npy"
    if not ts_path.exists():
        pytest.skip(f"Timestamp file not found: {ts_path}")

    # Track file access
    track_file_access(ts_path, request.node.name if hasattr(request, 'node') else "")

    return np.load(ts_path)


@pytest.fixture(scope="session")
def integration_proc_data(test_data_dir, test_dataset_name, test_camera_prefix, request):
    """
    Load processed DLC data from golden dataset with manifest tracking.
    """
    import numpy as np

    proc_path = test_data_dir / f"{test_camera_prefix}_{test_dataset_name}_PROC"
    if not proc_path.exists():
        pytest.skip(f"PROC file not found: {proc_path}")

    # Track file access
    track_file_access(proc_path, request.node.name if hasattr(request, 'node') else "")

    return np.load(proc_path, allow_pickle=True)
