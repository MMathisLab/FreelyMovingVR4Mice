"""Helpers for DataJoint populate with FailedSession filtering."""

from __future__ import annotations

from typing import Any, List, Union


def _table_class(table: Union[type, Any]) -> type:
    if isinstance(table, type):
        return table
    return table.__class__


def _table_instance(table: Union[type, Any]):
    return table() if isinstance(table, type) else table


def _key_tuples(table, primary_key: List[str]) -> set[tuple]:
    rows = table.fetch(*primary_key, as_dict=True)
    return {tuple(row[k] for k in primary_key) for row in rows}


def pending_keys(source, target, *, exclude_failed: bool = True) -> List[dict]:
    """
    Return keys present in source but not yet in target (and not failed).

    Uses explicit fetches instead of table subtraction so DataJoint 2.x does
    not reject joins on attributes with incompatible lineages.
    """
    target_cls = _table_class(target)
    target_table = target_cls()
    source_table = _table_instance(source)

    primary_key = list(target_table.primary_key)
    missing = [field for field in primary_key if field not in source_table.heading.names]
    if missing:
        raise ValueError(
            f"Source table {source_table.__class__.__name__} is missing primary-key "
            f"fields required by {target_cls.__name__}: {missing}"
        )

    pending = _key_tuples(source_table, primary_key) - _key_tuples(
        target_table, primary_key
    )

    if exclude_failed and pending and "dataset" in primary_key:
        from vr4mice.schema import vr4mice

        failed_datasets = {
            row["dataset"]
            for row in vr4mice.FailedSession().fetch("dataset", as_dict=True)
            if row.get("dataset")
        }
        if failed_datasets:
            dataset_idx = primary_key.index("dataset")
            pending = {
                key for key in pending if key[dataset_idx] not in failed_datasets
            }

    return [dict(zip(primary_key, key)) for key in pending]


def populate_pending(
    table: Union[type, Any],
    source,
    *,
    logger=None,
    exclude_failed: bool = True,
) -> int:
    """Populate a computed table only for pending keys."""
    cls = _table_class(table)
    pending = pending_keys(source, cls, exclude_failed=exclude_failed)
    count = len(pending)
    if logger is not None:
        logger.info("%s: %d pending keys", cls.__name__, count)
    if count:
        cls.populate(pending, display_progress=False)
    return count
