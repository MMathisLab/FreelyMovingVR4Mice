"""
Integration tests for base_schemas table population.

Validates that base schema tables (Mouse, Session, MouseScoreSheet, etc.)
can be populated from the Flamingo .npy metadata via check_keys() + populate(),
the same code path used by populate_rig() with GUI=true.

Requested by @lecriste (PR #289, Mar 30):
> "The test I would write, beyond the file presence check, is a validation
> of the populated base_schemas tables against the .npy file."

Test Strategy:
- Extend Lookup tables with values matching the Flamingo dataset
- Insert Mouse manually (not part of the base tables dict)
- Run check_keys() + populate() for all base tables
- Verify row counts via golden baseline JSON files
- Verify every field in every populated table against the .npy metadata
"""

import json
from pathlib import Path

import numpy as np
import pytest


# ==============================================================================
# Golden Baseline
# ==============================================================================

@pytest.fixture(scope="module")
def golden_baseline_dir():
    """Path to golden baseline files for base schema tests."""
    return Path(__file__).parent.parent / "golden_baseline" / "base_schema"


@pytest.fixture(scope="module")
def golden_baseline(golden_baseline_dir, request):
    """
    Golden baseline comparison fixture (same pattern as test_run_modes.py).

    Use --regenerate-golden flag to regenerate golden files.
    """
    try:
        regenerate = request.config.getoption("--regenerate-golden")
    except ValueError:
        regenerate = False

    class GoldenBaseline:
        def __init__(self, base_dir, should_regenerate):
            self.base_dir = Path(base_dir)
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.regenerate = should_regenerate

        def check_row_count(self, table_name, actual_count):
            """Compare row count against golden value."""
            golden_path = self.base_dir / f"{table_name}_row_count.json"

            if self.regenerate:
                with open(golden_path, "w") as f:
                    json.dump({"row_count": actual_count}, f, indent=2)
                    f.write("\n")
                return True

            if not golden_path.exists():
                pytest.fail(
                    f"Golden file not found: {golden_path}\n"
                    f"Run with --regenerate-golden to create it.\n"
                    f"Actual count: {actual_count}"
                )

            with open(golden_path) as f:
                expected = json.load(f)["row_count"]

            assert actual_count == expected, \
                f"{table_name}: row count {actual_count} != {expected}"
            return True

        def check_fields(self, table_name, actual_dict):
            """
            Compare all fields in a single-row table against golden values.

            Args:
                table_name: Name for the golden file
                actual_dict: Dictionary of {field: value} from fetch(as_dict=True)[0]
            """
            golden_path = self.base_dir / f"{table_name}_fields.json"

            # Serialize values for JSON storage
            serialized = {}
            for k, v in actual_dict.items():
                if hasattr(v, "isoformat"):  # date/datetime
                    serialized[k] = str(v)
                elif hasattr(v, "item"):  # numpy scalar
                    serialized[k] = v.item()
                else:
                    serialized[k] = v

            if self.regenerate:
                with open(golden_path, "w") as f:
                    json.dump(serialized, f, indent=2, default=str)
                    f.write("\n")
                return True

            if not golden_path.exists():
                pytest.fail(
                    f"Golden file not found: {golden_path}\n"
                    f"Run with --regenerate-golden to create it."
                )

            with open(golden_path) as f:
                expected = json.load(f)

            for key, expected_val in expected.items():
                actual_val = serialized.get(key)
                assert actual_val == expected_val, \
                    f"{table_name}.{key}: {actual_val!r} != {expected_val!r}"

            return True

    return GoldenBaseline(golden_baseline_dir, regenerate)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(scope="module")
def base_schema_modules(dj_config):
    """Import base schema modules after DataJoint is configured."""
    from base_schemas.schemas import exp, mice
    return {"exp": exp, "mice": mice}


@pytest.fixture(scope="module")
def npy_metadata(test_data_dir, test_dataset_name):
    """Load .npy metadata for the Flamingo session."""
    npy_path = test_data_dir / f"{test_dataset_name}.npy"
    return np.load(npy_path, allow_pickle=True).item()


@pytest.fixture(scope="module")
def populated_base_tables(dj_config, base_schema_modules, npy_metadata):
    """
    Populate base schema tables from .npy metadata.

    Extends Lookup tables to match Flamingo data, inserts Mouse,
    then runs check_keys + populate for all base tables.
    """
    exp = base_schema_modules["exp"]
    mice = base_schema_modules["mice"]

    from vr4mice.actions.populate_rig import check_keys, populate
    from vr4mice.actions.keys2tables_base import base as base_schema_dict

    metadata = dict(npy_metadata)  # copy so we don't mutate the fixture

    # --- Extend Lookup tables to match Flamingo data ---
    # These values are in the .npy but not in the hardcoded Lookup contents.

    exp.Experimenter.insert1(
        {"experimenter_name": "celia", "full_name": "Celia Benquet", "mail": ""},
        skip_duplicates=True,
    )
    exp.Rig.insert1(
        {"rig_id": 12, "details": "AR"},
        skip_duplicates=True,
    )
    mice.Strain.insert1(
        {"strain": "WT", "formal_name": "Wild Type", "stock_number": "N/A"},
        skip_duplicates=True,
    )
    mice.MouseLicensingGeneva.insert1(
        {"license": "GE367", "informal_title": "Geneva license GE367"},
        skip_duplicates=True,
    )

    # --- Insert Mouse (Manual table, not in base tables dict) ---
    mice.Mouse.insert1(
        {
            "mouse_name": metadata["mouse_name"],
            "mouse_id": int(metadata["mouse_id"]),
            "dob": metadata["dob"],
            "sex": metadata["sex"],
            "strain": metadata["strain"],
        },
        skip_duplicates=True,
    )

    # --- Run check_keys + populate for each base table ---
    populated_tables = []
    skipped_tables = []

    for table_name, attributes in base_schema_dict["tables"].items():
        flag, none_vals = check_keys(
            attributes, metadata, table_name, schema=base_schema_dict
        )
        if flag:
            metadata = {**metadata, **none_vals}
            populate(
                table_name,
                attributes,
                metadata,
                schema=base_schema_dict,
                srcf="/data",
                dstf="processed",
                move=False,
            )
            populated_tables.append(table_name)
        else:
            skipped_tables.append(table_name)

    return {
        "exp": exp,
        "mice": mice,
        "metadata": npy_metadata,
        "populated": populated_tables,
        "skipped": skipped_tables,
    }


# ==============================================================================
# Population Verification
# ==============================================================================

class TestBaseSchemaPopulation:
    """Verify all base tables populated without errors."""

    def test_no_tables_skipped(self, populated_base_tables):
        """All base tables should populate successfully."""
        assert populated_base_tables["skipped"] == [], \
            f"Tables skipped: {populated_base_tables['skipped']}"

    def test_all_expected_tables_populated(self, populated_base_tables):
        """All 5 base tables should be in the populated list."""
        expected = {
            "Optogenetics", "Session", "MouseScoreSheet",
            "MouseScoreSheet_WaterRestriction", "SessionScoreSheet",
        }
        assert set(populated_base_tables["populated"]) == expected


# ==============================================================================
# Mouse Table (manually inserted, not via populate())
# ==============================================================================

class TestMouseTable:
    """Verify Mouse table round-trip against .npy metadata."""

    def test_mouse_row_count(self, populated_base_tables, golden_baseline):
        """Mouse table should have exactly 1 row."""
        mice = populated_base_tables["mice"]
        golden_baseline.check_row_count("mouse", len(mice.Mouse()))

    def test_mouse_fields(self, populated_base_tables, golden_baseline):
        """Verify all Mouse fields match .npy metadata."""
        mice = populated_base_tables["mice"]
        row = mice.Mouse.fetch(as_dict=True)[0]
        golden_baseline.check_fields("mouse", row)

    def test_mouse_values_match_npy(self, populated_base_tables):
        """Verify Mouse fields directly against .npy source data."""
        mice = populated_base_tables["mice"]
        metadata = populated_base_tables["metadata"]

        row = mice.Mouse.fetch(as_dict=True)[0]
        assert row["mouse_name"] == metadata["mouse_name"]
        assert row["mouse_id"] == int(metadata["mouse_id"])
        assert str(row["dob"]) == metadata["dob"]
        assert row["sex"] == metadata["sex"]
        assert row["strain"] == metadata["strain"]


# ==============================================================================
# Session Table
# ==============================================================================

class TestSessionTable:
    """Verify Session table round-trip against .npy metadata."""

    def test_session_row_count(self, populated_base_tables, golden_baseline):
        """Session table should have exactly 1 row."""
        exp = populated_base_tables["exp"]
        golden_baseline.check_row_count("session", len(exp.Session()))

    def test_session_fields(self, populated_base_tables, golden_baseline):
        """Verify all Session fields against golden baseline."""
        exp = populated_base_tables["exp"]
        row = exp.Session.fetch(as_dict=True)[0]
        # session_ts is CURRENT_TIMESTAMP, different every run
        row = {k: v for k, v in row.items() if k != "session_ts"}
        golden_baseline.check_fields("session", row)

    def test_session_values_match_npy(self, populated_base_tables):
        """Verify Session fields directly against .npy source data."""
        exp = populated_base_tables["exp"]
        metadata = populated_base_tables["metadata"]

        row = exp.Session.fetch(as_dict=True)[0]
        assert row["mouse_name"] == metadata["mouse_name"]
        assert row["experimenter_name"] == metadata["experimenter_name"]
        assert row["rig_id"] == metadata["rig_id"]
        assert row["anesthesia_name"] == metadata["anesthesia_name"]
        assert row["opto_name"] == metadata["opto_name"]
        assert row["task_name"] == metadata["task_name"]
        assert str(row["doe"]) == metadata["doe"]
        assert row["day"] == int(metadata["day"])
        assert row["attempt"] == int(metadata["attempt"])
        assert row["session_notes"] == metadata["session_notes"]

    def test_session_increment_is_zero(self, populated_base_tables):
        """First session for a new mouse should have session_increment=0."""
        exp = populated_base_tables["exp"]
        row = exp.Session.fetch(as_dict=True)[0]
        assert row["session_increment"] == 0


# ==============================================================================
# Optogenetics Table
# ==============================================================================

class TestOptogeneticsTable:
    """Verify Optogenetics table round-trip against .npy metadata."""

    def test_optogenetics_row_count(self, populated_base_tables, golden_baseline):
        """Optogenetics table should have expected row count."""
        exp = populated_base_tables["exp"]
        # Optogenetics is a Lookup with default contents + any new inserts.
        # We only check that the entry matching .npy exists.
        metadata = populated_base_tables["metadata"]
        rows = (exp.Optogenetics & f'opto_name="{metadata["opto_name"]}"').fetch(as_dict=True)
        golden_baseline.check_row_count("optogenetics_match", len(rows))

    def test_optogenetics_fields(self, populated_base_tables, golden_baseline):
        """Verify Optogenetics fields against golden baseline."""
        exp = populated_base_tables["exp"]
        metadata = populated_base_tables["metadata"]
        row = (exp.Optogenetics & f'opto_name="{metadata["opto_name"]}"').fetch(as_dict=True)[0]
        golden_baseline.check_fields("optogenetics", row)

    def test_optogenetics_values_match_npy(self, populated_base_tables):
        """Verify Optogenetics fields against .npy and local_def defaults.

        Note: The Flamingo dataset has opto_name="none", which already exists
        in the Optogenetics Lookup's default contents. So populate() is a no-op
        here (skip_duplicates=True). This test verifies the Lookup's built-in
        values match the .npy, not that populate() inserted a new row.
        """
        exp = populated_base_tables["exp"]
        metadata = populated_base_tables["metadata"]

        row = (exp.Optogenetics & f'opto_name="{metadata["opto_name"]}"').fetch(as_dict=True)[0]
        assert row["opto_name"] == metadata["opto_name"]
        assert row["opto_region_name"] == metadata["opto_region_name"]
        assert row["opto_timing_name"] == metadata["opto_timing_name"]
        assert row["opto_variant_name"] == metadata["opto_variant_name"]
        # pulse_frequency, pulse_length, laser_power come from local_def default() = -1
        assert row["pulse_frequency"] == -1
        assert row["pulse_length"] == -1
        assert row["laser_power"] == -1


# ==============================================================================
# MouseScoreSheet Table
# ==============================================================================

class TestMouseScoreSheetTable:
    """Verify MouseScoreSheet table round-trip against .npy metadata."""

    def test_scoresheet_row_count(self, populated_base_tables, golden_baseline):
        """MouseScoreSheet should have exactly 1 row."""
        mice = populated_base_tables["mice"]
        golden_baseline.check_row_count("mousescoresheet", len(mice.MouseScoreSheet()))

    def test_scoresheet_fields(self, populated_base_tables, golden_baseline):
        """Verify all MouseScoreSheet fields against golden baseline."""
        mice = populated_base_tables["mice"]
        row = mice.MouseScoreSheet.fetch(as_dict=True)[0]
        golden_baseline.check_fields("mousescoresheet", row)

    def test_scoresheet_values_match_npy(self, populated_base_tables):
        """Verify MouseScoreSheet fields directly against .npy source data."""
        mice = populated_base_tables["mice"]
        metadata = populated_base_tables["metadata"]

        row = mice.MouseScoreSheet.fetch(as_dict=True)[0]
        assert row["mouse_name"] == metadata["mouse_name"]
        assert row["body_condition"] == metadata["body_condition"]
        assert row["general_assay"] == metadata["general_assay"]
        assert row["housing_assay"] == metadata["housing_assay"]
        assert row["license"] == metadata["license"]
        assert str(row["doc"]) == metadata["doc"]


# ==============================================================================
# MouseScoreSheet_WaterRestriction Table
# ==============================================================================

class TestWaterRestrictionTable:
    """Verify MouseScoreSheet_WaterRestriction round-trip against .npy."""

    def test_water_restriction_row_count(self, populated_base_tables, golden_baseline):
        """WaterRestriction should have exactly 1 row."""
        mice = populated_base_tables["mice"]
        golden_baseline.check_row_count(
            "waterrestriction", len(mice.MouseScoreSheet_WaterRestriction())
        )

    def test_water_restriction_fields(self, populated_base_tables, golden_baseline):
        """Verify all WaterRestriction fields against golden baseline."""
        mice = populated_base_tables["mice"]
        row = mice.MouseScoreSheet_WaterRestriction.fetch(as_dict=True)[0]
        golden_baseline.check_fields("waterrestriction", row)

    def test_water_restriction_values_match_npy(self, populated_base_tables):
        """Verify WaterRestriction fields directly against .npy source data."""
        mice = populated_base_tables["mice"]
        metadata = populated_base_tables["metadata"]

        row = mice.MouseScoreSheet_WaterRestriction.fetch(as_dict=True)[0]
        assert row["mouse_name"] == metadata["mouse_name"]
        assert row["weight_percentage"] == metadata["weight_percentage"]
        assert str(row["doc"]) == metadata["doc"]


# ==============================================================================
# SessionScoreSheet Table
# ==============================================================================

class TestSessionScoreSheetTable:
    """Verify SessionScoreSheet links Session to MouseScoreSheet correctly."""

    def test_session_scoresheet_row_count(self, populated_base_tables, golden_baseline):
        """SessionScoreSheet should have exactly 1 row."""
        exp = populated_base_tables["exp"]
        golden_baseline.check_row_count(
            "sessionscoresheet", len(exp.SessionScoreSheet())
        )

    def test_session_scoresheet_fields(self, populated_base_tables, golden_baseline):
        """Verify all SessionScoreSheet fields against golden baseline."""
        exp = populated_base_tables["exp"]
        row = exp.SessionScoreSheet.fetch(as_dict=True)[0]
        golden_baseline.check_fields("sessionscoresheet", row)

    def test_session_scoresheet_values_match_npy(self, populated_base_tables):
        """Verify SessionScoreSheet FK fields match .npy source data."""
        exp = populated_base_tables["exp"]
        metadata = populated_base_tables["metadata"]

        row = exp.SessionScoreSheet.fetch(as_dict=True)[0]
        assert row["mouse_name"] == metadata["mouse_name"]
        assert row["day"] == int(metadata["day"])
        assert row["attempt"] == int(metadata["attempt"])
        assert str(row["doc"]) == metadata["doc"]
