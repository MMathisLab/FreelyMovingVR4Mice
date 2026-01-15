"""
Database integration test fixtures using testcontainers.

Provides a MySQL container that automatically starts/stops for tests.
Uses a 'test_' schema prefix to isolate from any real data.

NOTE: This conftest clears the mocks from the parent conftest.py so that
we can test against a real database.
"""

import os
import sys
import time
from pathlib import Path

# ==============================================================================
# Clear mocks from parent conftest.py BEFORE other imports
# ==============================================================================

# Remove mocked modules so we can import the real ones
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

import pytest

# ==============================================================================
# Path Configuration (must happen before DataJoint imports)
# ==============================================================================

# Get paths
TESTS_DIR = Path(__file__).parent.parent
SCENE_ROOT = TESTS_DIR.parent
PROJECT_ROOT = SCENE_ROOT.parent

# Add module paths - need to add the vr4mice parent so imports like "from vr4mice.schema import vr4mice" work
VR4MICE_PARENT = SCENE_ROOT / "dj_pipeline"
VR4MICE_PATH = SCENE_ROOT / "dj_pipeline" / "vr4mice"
BASE_SCHEMAS_PATH = SCENE_ROOT / "dj_pipeline" / "base" / "base_min_schemas"
BASE_ACTIONS_PATH = SCENE_ROOT / "dj_pipeline" / "base" / "base_actions"

for path in [VR4MICE_PARENT, VR4MICE_PATH, BASE_SCHEMAS_PATH, BASE_ACTIONS_PATH]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Set environment variables before any imports
os.environ.setdefault("IMG_SRC", "Imagingsource")
os.environ.setdefault("GUI", "false")
os.environ.setdefault("DJ_LAB", "test")


# ==============================================================================
# MySQL Container Fixture
# ==============================================================================

@pytest.fixture(scope="session")
def mysql_container():
    """
    Start a MySQL container for database integration tests.

    Uses the same datajoint/mysql:5.7 image as the project's docker-compose.
    Container is started once per test session and cleaned up after.
    """
    from testcontainers.mysql import MySqlContainer

    # Use the same MySQL image as the project
    container = MySqlContainer(
        image="datajoint/mysql:5.7",
        username="root",
        password="simple",
        dbname="test_db",
    )

    # Start container
    container.start()

    # Wait for MySQL to be ready (datajoint/mysql can take a moment)
    time.sleep(5)

    yield container

    # Cleanup
    container.stop()


@pytest.fixture(scope="session")
def dj_config(mysql_container):
    """
    Configure DataJoint to connect to the test MySQL container.

    Uses 'test_' schema prefix to isolate test data.
    """
    import datajoint as dj

    # Get connection details from container
    host = mysql_container.get_container_host_ip()
    port = mysql_container.get_exposed_port(3306)

    # Configure DataJoint
    dj.config["database.host"] = f"{host}:{port}"
    dj.config["database.user"] = "root"
    dj.config["database.password"] = "simple"
    dj.config["database.misc.schema_prefix"] = "test_"
    dj.config["database.misc.create_tables"] = True
    dj.config["enable_python_native_blobs"] = True
    dj.config["safemode"] = False  # Allow dropping schemas in tests

    # Test connection
    conn = dj.conn()

    yield dj.config

    # Cleanup: drop all test schemas
    try:
        schemas = dj.list_schemas()
        for schema_name in schemas:
            if schema_name.startswith("test_"):
                schema = dj.schema(schema_name)
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
                schema = dj.schema(schema_name)
                schema.drop(force=True)
            except Exception:
                pass

    yield

    # Cleanup after test (optional, session cleanup handles this too)


@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory."""
    data_dir = PROJECT_ROOT / "test_data" / "Celia_Set_14012026"
    assert data_dir.exists(), f"Test data directory not found: {data_dir}"
    return data_dir


@pytest.fixture(scope="session")
def test_dataset_name():
    """Name of the test dataset."""
    return "Nightingale_2024-08-16_1"
