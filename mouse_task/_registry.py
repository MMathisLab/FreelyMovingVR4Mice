"""Dynamic task-class registry.

Each task variant is described by ``configs/tasks/<name>.yaml`` (class name,
docstring, and only the parameters that differ from ``configs/common.yaml``).
This module generates one ``ActiveSensingTask`` subclass per YAML, with a
real, introspectable ``__init__`` signature (required by the teensyexp GUI,
which reads args/defaults via ``inspect.getargspec`` to build its editable
parameter form).

Generated classes are re-exported from ``mouse_task/__init__.py`` as
``mouse_task.<ClassName>``.
"""

import pathlib

from mouse_task.helpers import CONFIG_DIR, _load_yaml, load_task_config
from mouse_task.task_active_sensing import _DEFAULT_CONFIG_FILE, ActiveSensingTask

_TASKS_DIR = CONFIG_DIR / "tasks"


def _build_task_class(task_name: str) -> type:
    """Generate an ``ActiveSensingTask`` subclass from ``tasks/<task_name>.yaml``."""
    meta = _load_yaml(_TASKS_DIR / f"{task_name}.yaml")
    class_name = meta["class_name"]
    doc = meta.get("description") or ""
    params = load_task_config(task_name)  # common.yaml + task overrides

    # Build a real __init__ source so inspect.getargspec sees every param.
    arg_lines = [f"        {name}={value!r}," for name, value in params.items()]
    fwd_lines = [f"            {name}={name}," for name in params]
    src = (
        "def __init__(\n"
        "        self,\n"
        "        teensy,\n"
        + "\n".join(arg_lines) + "\n"
        "        config_file_path=_DEFAULT_CONFIG_FILE,\n"
        "        **kwargs,\n"
        "):\n"
        "    ActiveSensingTask.__init__(\n"
        "        self,\n"
        "        teensy,\n"
        f"        task_config={task_name!r},\n"
        "        config_file_path=config_file_path,\n"
        + "\n".join(fwd_lines) + "\n"
        "        **kwargs,\n"
        "    )\n"
    )
    namespace = {
        "ActiveSensingTask": ActiveSensingTask,
        "_DEFAULT_CONFIG_FILE": _DEFAULT_CONFIG_FILE,
    }
    exec(src, namespace)  # noqa: S102 - trusted, generated from in-repo configs

    return type(
        class_name,
        (ActiveSensingTask,),
        {"__init__": namespace["__init__"], "__doc__": doc, "__module__": "mouse_task"},
    )


def build_task_classes() -> dict[str, type]:
    """Generate every task class, keyed by class name."""
    classes = {}
    for path in sorted(_TASKS_DIR.glob("*.yaml")):
        cls = _build_task_class(path.stem)
        classes[cls.__name__] = cls
    return classes
