"""Mouse task package.

Task variants are described by ``configs/tasks/<name>.yaml`` (class name,
docstring, and the parameters that differ from ``configs/common.yaml``); the
corresponding ``ActiveSensingTask`` subclass is generated at import time by
:mod:`mouse_task._registry`.

Generated classes are bound into this namespace, so ``mouse_task.<ClassName>``
keeps working (e.g. the teensyexp GUI task list).
"""

from .manual_water import ManualWater
from ._registry import build_task_classes

_TASK_CLASSES = build_task_classes()
globals().update(_TASK_CLASSES)

__all__ = ["ManualWater", *sorted(_TASK_CLASSES)]
