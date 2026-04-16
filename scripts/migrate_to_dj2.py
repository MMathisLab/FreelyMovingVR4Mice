#!/usr/bin/env python
"""
DataJoint 2.x Migration Script

This script migrates DataJoint 1.x schemas to DataJoint 2.x format by adding
type labels to column comments. This is a metadata-only migration - the actual
blob data format remains unchanged.

The migration process:
1. Analyzes columns in the specified schema(s)
2. Identifies columns needing type labels (longblob, int unsigned, etc.)
3. Adds appropriate type label prefixes to column comments:
   - longblob -> adds :<blob>: prefix
   - int unsigned -> adds :uint32: prefix
   - etc.

Usage:
    # Migrate all schemas in the database:
    python migrate_to_dj2.py

    # Dry run (preview changes without applying):
    python migrate_to_dj2.py --dry-run

    # Migrate a specific schema:
    python migrate_to_dj2.py --schema test_vr4mice

    # Migrate multiple schemas:
    python migrate_to_dj2.py --schema test_vr4mice --schema test_mice

    # Migrate all schemas with a prefix:
    python migrate_to_dj2.py --prefix test_

    # Analyze only, don't migrate:
    python migrate_to_dj2.py --analyze-only

Environment Variables:
    DJ_HOST: Database host (default: localhost)
    DJ_PORT: Database port (default: 3306)
    DJ_USER: Database user (default: root)
    DJ_PASSWORD: Database password (default: simple)

Requirements:
    - DataJoint 2.x installed
    - MySQL database accessible with the schemas to migrate
"""

import argparse
import os
import sys


def configure_datajoint():
    """Configure DataJoint connection from environment variables."""
    import datajoint as dj

    host = os.environ.get("DJ_HOST", "localhost")
    port = os.environ.get("DJ_PORT", "3306")
    user = os.environ.get("DJ_USER", "root")
    password = os.environ.get("DJ_PASSWORD", "simple")

    dj.config["database.host"] = f"{host}:{port}"
    dj.config["database.user"] = user
    dj.config["database.password"] = password
    dj.config["safemode"] = False

    return dj


def get_schemas_to_migrate(dj, schema_names=None, prefix=None):
    """
    Get list of schema names to migrate.

    Args:
        dj: DataJoint module
        schema_names: List of specific schema names to migrate
        prefix: Prefix to filter schemas (e.g., 'test_')

    Returns:
        List of schema names
    """
    if schema_names:
        return schema_names

    # Get all schemas and filter by prefix
    all_schemas = dj.list_schemas()

    if prefix:
        return [s for s in all_schemas if s.startswith(prefix)]

    return all_schemas


def analyze_schema(dj, schema_name):
    """
    Analyze a schema to identify columns needing migration.

    Args:
        dj: DataJoint module
        schema_name: Name of the schema to analyze

    Returns:
        dict with analysis results
    """
    from datajoint.migrate import analyze_columns

    schema = dj.Schema(schema_name)
    analysis = analyze_columns(schema)

    return {
        "schema_name": schema_name,
        "analysis": analysis,
        "columns_to_migrate": len(analysis) if analysis else 0,
    }


def migrate_schema(dj, schema_name, dry_run=True):
    """
    Migrate a schema to add type labels to column comments.

    Args:
        dj: DataJoint module
        schema_name: Name of the schema to migrate
        dry_run: If True, only preview changes without applying

    Returns:
        dict with migration results
    """
    from datajoint.migrate import migrate_columns

    schema = dj.Schema(schema_name)

    if dry_run:
        print(f"\n[DRY RUN] Analyzing schema: {schema_name}")
    else:
        print(f"\n[MIGRATING] Schema: {schema_name}")

    result = migrate_columns(schema, dry_run=dry_run)

    return {
        "schema_name": schema_name,
        "dry_run": dry_run,
        "result": result,
    }


def print_analysis_report(analysis_results):
    """Print a formatted analysis report."""
    print("\n" + "=" * 60)
    print("MIGRATION ANALYSIS REPORT")
    print("=" * 60)

    total_columns = 0
    for result in analysis_results:
        schema_name = result["schema_name"]
        columns = result["columns_to_migrate"]
        total_columns += columns

        print(f"\nSchema: {schema_name}")
        print(f"  Columns needing migration: {columns}")

        if result["analysis"]:
            for col_info in result["analysis"]:
                print(f"    - {col_info}")

    print("\n" + "-" * 60)
    print(f"TOTAL: {total_columns} columns across {len(analysis_results)} schemas")
    print("=" * 60)


def print_migration_report(migration_results, dry_run):
    """Print a formatted migration report."""
    print("\n" + "=" * 60)
    if dry_run:
        print("MIGRATION DRY RUN REPORT")
    else:
        print("MIGRATION COMPLETE REPORT")
    print("=" * 60)

    for result in migration_results:
        schema_name = result["schema_name"]
        print(f"\nSchema: {schema_name}")
        print(f"  Result: {result['result']}")

    print("\n" + "-" * 60)
    if dry_run:
        print("This was a DRY RUN. No changes were made.")
        print("Run without --dry-run to apply changes.")
    else:
        print("Migration complete. Column comments have been updated.")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate DataJoint 1.x schemas to 2.x format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--schema",
        action="append",
        dest="schemas",
        help="Schema name to migrate (can be specified multiple times)",
    )

    parser.add_argument(
        "--prefix",
        help="Migrate all schemas with this prefix (e.g., 'test_')",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )

    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only analyze schemas, don't migrate",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Configure DataJoint
    print("Configuring DataJoint connection...")
    dj = configure_datajoint()

    # Test connection
    try:
        conn = dj.conn()
        print(f"Connected to database at {dj.config['database.host']}")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    # Get schemas to migrate
    schemas = get_schemas_to_migrate(dj, args.schemas, args.prefix)

    if not schemas:
        print("No schemas found to migrate.")
        sys.exit(0)

    print(f"\nSchemas to process: {schemas}")

    # Analyze schemas
    print("\nAnalyzing schemas...")
    analysis_results = []
    for schema_name in schemas:
        try:
            result = analyze_schema(dj, schema_name)
            analysis_results.append(result)
        except Exception as e:
            print(f"ERROR analyzing schema {schema_name}: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    print_analysis_report(analysis_results)

    if args.analyze_only:
        print("\n--analyze-only specified. Exiting without migration.")
        sys.exit(0)

    # Check if there are columns to migrate
    total_columns = sum(r["columns_to_migrate"] for r in analysis_results)
    if total_columns == 0:
        print("\nNo columns need migration. Schemas are already DJ 2.x compatible.")
        sys.exit(0)

    # Migrate schemas
    print("\nProceeding with migration...")
    migration_results = []
    for schema_name in schemas:
        try:
            result = migrate_schema(dj, schema_name, dry_run=args.dry_run)
            migration_results.append(result)
        except Exception as e:
            print(f"ERROR migrating schema {schema_name}: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    print_migration_report(migration_results, args.dry_run)


if __name__ == "__main__":
    main()
