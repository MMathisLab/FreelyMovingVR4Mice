#!/usr/bin/env bash
set -euo pipefail

# Restrict downstream CUDA-aware commands to GPU 2 by default.
CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-2}"
export CUDA_VISIBLE_DEVICES

# Load credentials from .env_aws file (not tracked in git)
if [[ -f .env_aws ]]; then
  set -a
  source .env_aws
  set +a
elif [[ -z "${DJ_HOST:-}" || -z "${DJ_USER:-}" || -z "${DJ_PWD:-}" ]]; then
  echo "Error: Database credentials not found. Please set DJ_HOST, DJ_USER, and DJ_PWD environment variables or create a .env_aws file." >&2
  exit 1
fi

HOST_ONLY="${DJ_HOST%%:*}"
PORT="3306"
if [[ "$DJ_HOST" == *:* ]]; then
  PORT="${DJ_HOST##*:}"
fi

# Restrictions for the Benquet, Sainsbury et al. paper
SESSION_LABELS=(
  "ar_detection_no_velthr"
  "ar_detection_velthr"
  "ar_discrim"
  "ar_discrim_5_occluders"
  "ar_discrim_occluders"
  "ar_det_no_velthr_inv"
  "ar_detection_velthr_inv"
  "ar_discrim_inv"
  "ar_discrim_5_occluders_inv"
  "ar_discrim_occluders_inv"
)

SET_LABELS=(
  "contrast_white_target"
  "contrast_black_target"
)

SCHEMA_SUFFIXES=(
  "vr4mice"
  "base"
  "base_analysis"
  "decision"
  "dlc"
  #"inputs_videos"
  "interpolated_trajectories"
  "latency_tests"
  "session_metrics"
)

# Minimal list of tables included in the figure notebooks
# These names are stored without deployment-specific prefixes; the script adds
# the detected prefix before matching against live schemas.
INCLUDED_TABLES_DEFAULT=(
  '`base_analysis`.`__box_data_frame`'
  '`base_analysis`.`__data_frame`'
  '`decision`.`#label_set`'
  '`decision`.`#label_set__member`'
  '`decision`.`#label`'
  '`decision`.`__decision_points`'
  '`decision`.`__inclusion_status`'
  '`decision`.`__prediction_model__session_prediction`'
  '`decision`.`__prediction_model`'
  '`decision`.`_experiment_member`'
  '`dlc`.`__offline_kinematics`'
  '`interpolated_trajectories`.`__interpolated_trials`'
  '`interpolated_trajectories`.`__mean_velocities`'
  '`interpolated_trajectories`.`__mean_x_y_trajectory`'
  '`interpolated_trajectories`.`__y_binned_x_y_trajectory`'
  '`latency_tests`.`__all_latencies`'
  '`latency_tests`.`__signals_photodiode_aligned`'
  '`session_metrics`.`__session_metrics`'
  '`session_metrics`.`__trial_metrics`'
  '`vr4mice`.`#labels`'
  '`vr4mice`.`#labs`'
  '`vr4mice`.`__collab`'
  '`vr4mice`.`dataset`'
  '`vr4mice`.`groups`'
  '`vr4mice`.`signals_photodiode`'
)

# A few tables are intentionally narrowed to a single dataset instead of the
# broader dataset list derived from session_label/set_name.
declare -A TABLE_DATASET_OVERRIDES=(
  ["dlc.__offline_kinematics"]="Pheasant_2024-08-21_1"
  ["latency_tests.__signals_photodiode_aligned"]="Latencytest1_2024-10-31_2"
)

sql_quote_list() {
  local out=""
  for item in "$@"; do
    item="${item//\'/\'\'}"
    out+="'${item}',"
  done
  echo "${out%,}"
}

csv_escape() {
  local s="${1:-}"
  s="${s//\"/\"\"}"
  printf '"%s"' "$s"
}

bytes_to_go() {
  local bytes="${1:-0}"
  awk -v b="$bytes" 'BEGIN { printf "%.3f", b / (1024 * 1024 * 1024) }'
}

SESSION_SQL_LIST="$(sql_quote_list "${SESSION_LABELS[@]}")"
SET_SQL_LIST="$(sql_quote_list "${SET_LABELS[@]}")"

MYSQL_BASE=(mysql -h "$HOST_ONLY" -P "$PORT" -u "$DJ_USER")
MYSQLDUMP_BASE=(
  mysqldump
  -h "$HOST_ONLY"
  -P "$PORT"
  -u "$DJ_USER"
  --single-transaction
  --skip-lock-tables
  --set-gtid-purged=OFF
  --no-tablespaces
)

export MYSQL_PWD="$DJ_PWD"

BASE_DB="$(${MYSQL_BASE[@]} -Nse "SHOW DATABASES LIKE '%vr4mice'" | head -n1)"
if [[ -z "$BASE_DB" ]]; then
  echo "Could not find a database ending with vr4mice." >&2
  exit 1
fi

# Some deployments prefix every schema name. Infer that once so the embedded
# allowlist and the live database names can be compared consistently.
PREFIX="${BASE_DB%vr4mice}"

declare -A INCLUDED_TABLE_KEYS=()
for full_table_name in "${INCLUDED_TABLES_DEFAULT[@]}"; do
  [[ -z "$full_table_name" ]] && continue
  clean_name="${full_table_name//\`/}"
  if [[ "$clean_name" != *.* ]]; then
    continue
  fi

  schema_name="${clean_name%%.*}"
  table_name="${clean_name#*.}"
  [[ -z "$schema_name" || -z "$table_name" ]] && continue

  # Prepend detected prefix to include-list schema names
  effective_schema="${PREFIX}${schema_name}"
  INCLUDED_TABLE_KEYS["${effective_schema}.${table_name}"]=1
done

INCLUDED_TABLES_FILTER_ENABLED="false"
if [[ "${#INCLUDED_TABLE_KEYS[@]}" -gt 0 ]]; then
  INCLUDED_TABLES_FILTER_ENABLED="true"
fi

DATASET_TABLE_NAME="$(${MYSQL_BASE[@]} -Nse "
  SELECT table_name
  FROM information_schema.tables
  WHERE table_schema='${PREFIX}vr4mice'
    AND table_name LIKE '%dataset'
  ORDER BY table_name
  LIMIT 1
")"

SESSION_LABEL_TABLE_NAME="$(${MYSQL_BASE[@]} -Nse "
  SELECT table_name
  FROM information_schema.tables
  WHERE table_schema='${PREFIX}decision'
    AND table_name LIKE '%session_label'
  ORDER BY table_name
  LIMIT 1
")"

if [[ -z "$DATASET_TABLE_NAME" ]]; then
  echo "Could not find dataset table in ${PREFIX}vr4mice." >&2
  exit 1
fi

if [[ -z "$SESSION_LABEL_TABLE_NAME" ]]; then
  echo "Could not find session_label table in ${PREFIX}decision." >&2
  exit 1
fi

DATASET_SQL="$(${MYSQL_BASE[@]} -Nse "
  SELECT d.dataset
  FROM \`${PREFIX}vr4mice\`.\`${DATASET_TABLE_NAME}\` d
  JOIN \`${PREFIX}decision\`.\`${SESSION_LABEL_TABLE_NAME}\` sl
    ON d.session_label = sl.session_label
  WHERE d.session_label IN (${SESSION_SQL_LIST})
    AND sl.set_name IN (${SET_SQL_LIST})
")"

if [[ -z "$DATASET_SQL" ]]; then
  echo "No datasets matched SESSION_LABELS + SET_LABELS restrictions." >&2
  exit 1
fi

# Convert the selected datasets into a quoted SQL list reused by all tables
# that can be restricted directly on a dataset column.
DATASET_SQL_LIST=""
while IFS= read -r ds; do
  [[ -z "$ds" ]] && continue
  esc="${ds//\'/\'\'}"
  DATASET_SQL_LIST+="'${esc}',"
done <<< "$DATASET_SQL"
DATASET_SQL_LIST="${DATASET_SQL_LIST%,}"

EXPORT_ROOT="${EXPORT_ROOT:-/app/exports}"
mkdir -p "$EXPORT_ROOT"
RUN_TS="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${EXPORT_ROOT}/restricted_dump_${RUN_TS}"
TRACE_TABLES_FILE="${OUT_DIR}/tables.csv"
TRACE_DATASETS_FILE="${OUT_DIR}/datasets.txt"
TRACE_META_FILE="${OUT_DIR}/meta.txt"
TRACE_WITH_ROW_COUNTS="${TRACE_WITH_ROW_COUNTS:-true}"

mkdir -p "$OUT_DIR"

printf "%s\n" "$DATASET_SQL" | sort > "$TRACE_DATASETS_FILE"

echo "db,table,output_file,has_dataset,has_session_label,has_set_name,restriction_mode,dataset_override,where_clause,row_count,table_rows_estimate,table_size_go,estimated_size_go" > "$TRACE_TABLES_FILE"

TOTAL_TABLES=0
DUMPED_TABLES=0
SCHEMAS_DUMPED=0
declare -a SCHEMA_DUMP_FILES=()

for suffix in "${SCHEMA_SUFFIXES[@]}"; do
  DB="${PREFIX}${suffix}"

  EXISTS="$(${MYSQL_BASE[@]} -Nse "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='${DB}'")"
  if [[ "$EXISTS" == "0" ]]; then
    continue
  fi

  SCHEMA_OUT_FILE="${OUT_DIR}/restricted_dump_${DB}_${RUN_TS}.sql"
  {
    echo "-- Restricted export generated on $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "-- Schema: ${DB}"
    echo "-- Prefix: ${PREFIX}"
    echo "-- Session labels: ${SESSION_SQL_LIST}"
    echo "-- Set labels: ${SET_SQL_LIST}"
    echo "-- Included tables filter enabled: ${INCLUDED_TABLES_FILTER_ENABLED}"
    echo "-- Effective included tables count: ${#INCLUDED_TABLE_KEYS[@]}"
    if [[ "${#TABLE_DATASET_OVERRIDES[@]}" -gt 0 ]]; then
      echo "-- Table dataset overrides:"
      for table_key in "${!TABLE_DATASET_OVERRIDES[@]}"; do
        echo "--   ${table_key}=${TABLE_DATASET_OVERRIDES[$table_key]}"
      done
    fi
    echo ""
  } > "$SCHEMA_OUT_FILE"

  SCHEMA_TABLES=0

  mapfile -t TABLES < <(${MYSQL_BASE[@]} -Nse "
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema='${DB}'
    ORDER BY table_name
  ")

  for TBL in "${TABLES[@]}"; do
    [[ -z "$TBL" ]] && continue
    [[ "$TBL" == ~* ]] && continue

    # Skip anything that is not part of the notebook export allowlist.
    TABLE_FULL_KEY="${DB}.${TBL}"
    if [[ "$INCLUDED_TABLES_FILTER_ENABLED" == "true" && -z "${INCLUDED_TABLE_KEYS[$TABLE_FULL_KEY]+x}" ]]; then
      continue
    fi

    TOTAL_TABLES=$((TOTAL_TABLES + 1))

    HAS_DATASET="$(${MYSQL_BASE[@]} -Nse "
      SELECT COUNT(*)
      FROM information_schema.columns
      WHERE table_schema='${DB}'
        AND table_name='${TBL}'
        AND column_name='dataset'
    ")"

    HAS_SESSION_LABEL="$(${MYSQL_BASE[@]} -Nse "
      SELECT COUNT(*)
      FROM information_schema.columns
      WHERE table_schema='${DB}'
        AND table_name='${TBL}'
        AND column_name='session_label'
    ")"

    HAS_SET_NAME="$(${MYSQL_BASE[@]} -Nse "
      SELECT COUNT(*)
      FROM information_schema.columns
      WHERE table_schema='${DB}'
        AND table_name='${TBL}'
        AND column_name='set_name'
    ")"

    # Prefer the most specific restriction available for the current table.
    WHERE_CLAUSE=""
    RESTRICTION_MODE="unrestricted"
    DATASET_OVERRIDE_USED=""
    TABLE_OVERRIDE_KEY="${suffix}.${TBL}"
    TABLE_OVERRIDE_DATASET="${TABLE_DATASET_OVERRIDES[$TABLE_OVERRIDE_KEY]-}"
    if [[ -n "$TABLE_OVERRIDE_DATASET" && "$HAS_DATASET" != "0" ]]; then
      DATASET_OVERRIDE_USED="$TABLE_OVERRIDE_DATASET"
      TABLE_OVERRIDE_DATASET="${TABLE_OVERRIDE_DATASET//\'/\'\'}"
      WHERE_CLAUSE="dataset='${TABLE_OVERRIDE_DATASET}'"
      RESTRICTION_MODE="dataset+dataset_override"
    elif [[ "$HAS_DATASET" != "0" ]]; then
      WHERE_CLAUSE="dataset IN (${DATASET_SQL_LIST})"
      RESTRICTION_MODE="dataset"
    elif [[ "$HAS_SESSION_LABEL" != "0" && "$HAS_SET_NAME" != "0" ]]; then
      WHERE_CLAUSE="session_label IN (${SESSION_SQL_LIST}) AND set_name IN (${SET_SQL_LIST})"
      RESTRICTION_MODE="session_label+set_name"
    elif [[ "$HAS_SESSION_LABEL" != "0" ]]; then
      WHERE_CLAUSE="session_label IN (${SESSION_SQL_LIST})"
      RESTRICTION_MODE="session_label"
    elif [[ "$HAS_SET_NAME" != "0" ]]; then
      WHERE_CLAUSE="set_name IN (${SET_SQL_LIST})"
      RESTRICTION_MODE="set_name"
    fi

    TABLE_ROWS_ESTIMATE=0
    TABLE_DATA_LENGTH=0
    TABLE_INDEX_LENGTH=0
    TABLE_STATS="$(${MYSQL_BASE[@]} -Nse "
      SELECT
        COALESCE(table_rows, 0),
        COALESCE(data_length, 0),
        COALESCE(index_length, 0)
      FROM information_schema.tables
      WHERE table_schema='${DB}'
        AND table_name='${TBL}'
      LIMIT 1
    ")"
    if [[ -n "$TABLE_STATS" ]]; then
      read -r TABLE_ROWS_ESTIMATE TABLE_DATA_LENGTH TABLE_INDEX_LENGTH <<< "$TABLE_STATS"
    fi

    # Keep the full-table storage size plus a restricted-size estimate in Go so
    # the trace file can be compared directly with the notebook summary.
    TABLE_SIZE_BYTES=$((TABLE_DATA_LENGTH + TABLE_INDEX_LENGTH))
    TABLE_SIZE_GO="$(bytes_to_go "$TABLE_SIZE_BYTES")"

    if [[ -n "$WHERE_CLAUSE" ]]; then
      ${MYSQLDUMP_BASE[@]} "$DB" "$TBL" --where="$WHERE_CLAUSE" >> "$SCHEMA_OUT_FILE"
    else
      ${MYSQLDUMP_BASE[@]} "$DB" "$TBL" >> "$SCHEMA_OUT_FILE"
    fi

    ROW_COUNT=""
    if [[ "$TRACE_WITH_ROW_COUNTS" == "true" ]]; then
      if [[ -n "$WHERE_CLAUSE" ]]; then
        ROW_COUNT="$(${MYSQL_BASE[@]} -Nse "SELECT COUNT(*) FROM \`${DB}\`.\`${TBL}\` WHERE ${WHERE_CLAUSE}")"
      else
        ROW_COUNT="$(${MYSQL_BASE[@]} -Nse "SELECT COUNT(*) FROM \`${DB}\`.\`${TBL}\`")"
      fi
    fi

    # Approximate the restricted size the same way as the notebook: scale the
    # full table size by the fraction of selected rows.
    ESTIMATED_SIZE_GO=""
    if [[ -n "$ROW_COUNT" ]]; then
      if [[ "$TABLE_ROWS_ESTIMATE" -gt 0 ]]; then
        ESTIMATED_SIZE_BYTES=$(awk -v count="$ROW_COUNT" -v total_bytes="$TABLE_SIZE_BYTES" -v total_rows="$TABLE_ROWS_ESTIMATE" 'BEGIN { printf "%.0f", (count * total_bytes) / total_rows }')
        ESTIMATED_SIZE_GO="$(bytes_to_go "$ESTIMATED_SIZE_BYTES")"
      else
        ESTIMATED_SIZE_GO=""
      fi
    elif [[ "$RESTRICTION_MODE" == "unrestricted" ]]; then
      ESTIMATED_SIZE_GO="$TABLE_SIZE_GO"
    fi

    printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
      "$(csv_escape "$DB")" \
      "$(csv_escape "$TBL")" \
      "$(csv_escape "$SCHEMA_OUT_FILE")" \
      "$(csv_escape "$HAS_DATASET")" \
      "$(csv_escape "$HAS_SESSION_LABEL")" \
      "$(csv_escape "$HAS_SET_NAME")" \
      "$(csv_escape "$RESTRICTION_MODE")" \
      "$(csv_escape "$DATASET_OVERRIDE_USED")" \
      "$(csv_escape "$WHERE_CLAUSE")" \
      "$(csv_escape "$ROW_COUNT")" \
      "$(csv_escape "$TABLE_ROWS_ESTIMATE")" \
      "$(csv_escape "$TABLE_SIZE_GO")" \
      "$(csv_escape "$ESTIMATED_SIZE_GO")" \
      >> "$TRACE_TABLES_FILE"

    SCHEMA_TABLES=$((SCHEMA_TABLES + 1))
    DUMPED_TABLES=$((DUMPED_TABLES + 1))
  done

  if [[ "$SCHEMA_TABLES" -gt 0 ]]; then
    SCHEMAS_DUMPED=$((SCHEMAS_DUMPED + 1))
    SCHEMA_DUMP_FILES+=("$SCHEMA_OUT_FILE")
  else
    rm -f "$SCHEMA_OUT_FILE"
  fi

done

# Write a compact run summary so the output directory is self-describing.
{
  echo "generated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "dump_dir=${OUT_DIR}"
  echo "tables_trace_file=${TRACE_TABLES_FILE}"
  echo "datasets_trace_file=${TRACE_DATASETS_FILE}"
  echo "db_prefix=${PREFIX}"
  echo "included_tables_filter_enabled=${INCLUDED_TABLES_FILTER_ENABLED}"
  echo "included_tables_effective_count=${#INCLUDED_TABLE_KEYS[@]}"
  echo "dataset_table=${DATASET_TABLE_NAME}"
  echo "session_label_table=${SESSION_LABEL_TABLE_NAME}"
  echo "tables_considered=${TOTAL_TABLES}"
  echo "tables_dumped=${DUMPED_TABLES}"
  echo "schemas_dumped=${SCHEMAS_DUMPED}"
  echo "trace_with_row_counts=${TRACE_WITH_ROW_COUNTS}"
  if [[ "${#SCHEMA_DUMP_FILES[@]}" -gt 0 ]]; then
    echo "dump_files=$(IFS=,; echo \"${SCHEMA_DUMP_FILES[*]}\")"
  fi
} > "$TRACE_META_FILE"

echo "Dump directory: ${OUT_DIR}"
for schema_file in "${SCHEMA_DUMP_FILES[@]}"; do
  echo "Schema dump: ${schema_file}"
done
echo "Tables considered: ${TOTAL_TABLES}"
echo "Tables dumped: ${DUMPED_TABLES}"
echo "Schemas dumped: ${SCHEMAS_DUMPED}"
echo "Trace tables: ${TRACE_TABLES_FILE}"
echo "Trace datasets: ${TRACE_DATASETS_FILE}"
echo "Trace meta: ${TRACE_META_FILE}"
