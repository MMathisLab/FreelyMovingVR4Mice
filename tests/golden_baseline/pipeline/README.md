# Golden Baseline - Pipeline Tests

This directory contains expected pipeline outputs for the integration tests (`test_run_modes.py`).
These capture row counts and sample values from database tables after running the full pipeline.

## File Naming Convention

- `{table_name}_row_count.json` - Expected row count for a table
- `{table_name}_samples.json` - Sample values (first, middle, last) for verification
- `{name}_scalar.json` - Expected scalar value

## Regenerating Golden Files

To regenerate all golden baseline files from a fresh pipeline run:

```bash
cd scene/tests
sg docker -c "bash -c 'source ../venv/bin/activate && python -m pytest integration/test_run_modes.py -v --regenerate-golden'"
```

This will:
1. Run the full pipeline with the golden test dataset
2. Capture actual outputs as new golden files
3. Overwrite existing golden files

## Initial Setup Notes

Sample values (first, middle, last) and row counts should be updated
by running `--regenerate-golden` after the first successful pipeline run.

## Dataset Info

- **Dataset**: Flamingo_2026-02-05_1
- **Camera**: Imagingsource
- **Session**: golden_dataset
