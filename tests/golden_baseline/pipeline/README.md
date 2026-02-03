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
1. Run the full pipeline with the Nightingale test dataset
2. Capture actual outputs as new golden files
3. Overwrite existing golden files

## Initial Setup Notes

The initial values in these files are placeholders based on the Nightingale golden dataset specification:
- 339,045 steps in pickle data
- 281,748 frames in DLC DataFrame
- 281,876 frames in PROC data
- 455,965 timestamps

Sample values (first, middle, last) are set to 0.0 as placeholders and should be updated
by running `--regenerate-golden` after the first successful pipeline run.

## Dataset Info

- **Dataset**: Nightingale_2024-08-16_1
- **Camera**: Imagingsource
- **Session**: golden_dataset
