"""Helpers for DataJoint populate with FailedSession filtering."""

from __future__ import annotations

from typing import Any, Optional, Union


def _table_class(table: Union[type, Any]) -> type:
    if isinstance(table, type):
        return table
    return table.__class__


def pending_keys(source, target, *, exclude_failed: bool = True):
    """Return keys in source that are not yet in target (and not failed)."""
    keys = source - target
    if exclude_failed:
        from vr4mice.schema import vr4mice

        keys = keys - vr4mice.FailedSession.proj()
    return keys


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
