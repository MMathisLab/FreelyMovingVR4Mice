# Description: Unit tests for the modular task-config / registry setup.
#
# These verify that the per-task YAML configs (configs/common.yaml +
# configs/tasks/<name>.yaml) and the dynamically generated ActiveSensingTask
# subclasses (mouse_task._registry) behave as expected:
#   * every task YAML produces a correctly named, importable subclass;
#   * load_task_config deep-merges common defaults with task overrides;
#   * the generated __init__ keeps a real, introspectable signature (required
#     by the teensyexp GUI, which reads args/defaults via inspect.getargspec);
#   * constructing a task resolves parameters from the merged config, with
#     explicitly-passed arguments taking precedence.

import inspect
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

import mouse_task
from mouse_task.helpers import CONFIG_DIR, load_task_config
from mouse_task.task_active_sensing import ActiveSensingTask

_TASKS_DIR = CONFIG_DIR / "tasks"
_MOCK_CONFIG = {"ar_env_unity_absolute_path": "mock_path"}


def _task_names():
    """All task-config stems (one per configs/tasks/*.yaml)."""
    return sorted(p.stem for p in _TASKS_DIR.glob("*.yaml"))


def _yaml(path):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _signature_defaults(cls):
    """Map of {arg_name: default} for a generated class __init__."""
    spec = inspect.getfullargspec(cls.__init__)
    return dict(zip(spec.args[-len(spec.defaults):], spec.defaults))


class TestTaskRegistry(unittest.TestCase):
    """The registry exposes one class per task YAML."""

    def test_at_least_expected_tasks(self):
        names = _task_names()
        self.assertGreaterEqual(len(names), 20)
        # A few well-known variants must be present.
        for stem in ["mouse_discrim", "shape_mouse_discrim", "shape_mouse_discrim_occluders"]:
            self.assertIn(stem, names)

    def test_every_yaml_yields_an_exposed_subclass(self):
        for stem in _task_names():
            with self.subTest(task=stem):
                class_name = _yaml(_TASKS_DIR / f"{stem}.yaml")["class_name"]
                self.assertTrue(
                    hasattr(mouse_task, class_name),
                    f"{class_name} not exposed on mouse_task",
                )
                cls = getattr(mouse_task, class_name)
                self.assertTrue(issubclass(cls, ActiveSensingTask))
                self.assertEqual(cls.__name__, class_name)
                self.assertIn(class_name, mouse_task.__all__)

    def test_class_names_are_unique(self):
        names = [_yaml(_TASKS_DIR / f"{s}.yaml")["class_name"] for s in _task_names()]
        self.assertEqual(len(names), len(set(names)), "duplicate class_name across task YAMLs")

    def test_docstring_comes_from_yaml(self):
        cls = mouse_task.ShapeDiscrim
        expected = _yaml(_TASKS_DIR / "shape_mouse_discrim.yaml")["description"].strip()
        self.assertIn(expected.splitlines()[0], (cls.__doc__ or ""))


class TestLoadTaskConfig(unittest.TestCase):
    """common.yaml + tasks/<name>.yaml merge behaviour."""

    def test_task_without_overrides_equals_common(self):
        common = _yaml(CONFIG_DIR / "common.yaml")
        merged = load_task_config("mouse_discrim")  # has an empty params block
        self.assertEqual(merged, common)

    def test_overrides_win_over_common(self):
        merged = load_task_config("shape_mouse_discrim")
        # overridden in the task YAML
        self.assertEqual(merged["target_selection"], 13.0)
        self.assertEqual(merged["slit_depth"], 0.02)
        self.assertEqual(merged["velocity_threshold"], 5.0)
        # NOT overridden -> falls back to common.yaml
        self.assertEqual(merged["reward_size"], 100)
        self.assertEqual(merged["camera_type"], 1.0)

    def test_every_merged_config_has_all_common_keys(self):
        common_keys = set(_yaml(CONFIG_DIR / "common.yaml"))
        for stem in _task_names():
            with self.subTest(task=stem):
                merged = load_task_config(stem)
                self.assertEqual(set(merged), common_keys)

    def test_unknown_task_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_task_config("does_not_exist")


class TestGeneratedSignatures(unittest.TestCase):
    """The teensyexp GUI introspects __init__ via inspect — keep it real."""

    def test_signature_lists_every_param_with_merged_default(self):
        for stem in _task_names():
            cls = getattr(mouse_task, _yaml(_TASKS_DIR / f"{stem}.yaml")["class_name"])
            merged = load_task_config(stem)
            defaults = _signature_defaults(cls)
            with self.subTest(task=stem):
                for key, value in merged.items():
                    self.assertIn(key, defaults)
                    self.assertEqual(
                        defaults[key], value, f"{stem}.{key} default mismatch"
                    )

    def test_signature_shape(self):
        spec = inspect.getfullargspec(mouse_task.ShapeDiscrim.__init__)
        self.assertEqual(spec.args[:2], ["self", "teensy"])
        self.assertEqual(spec.varkw, "kwargs")          # forwards extra kwargs
        self.assertIn("config_file_path", spec.args)    # machine-specific config kept separate

    def test_all_args_after_teensy_have_defaults(self):
        # The GUI (teensyexp) reads defaults positionally from the introspected
        # signature, so every arg except self/teensy must carry a default.
        spec = inspect.getfullargspec(mouse_task.ShapeDiscrim.__init__)
        self.assertEqual(len(spec.defaults), len(spec.args) - 2)  # all but self, teensy default


class TestTaskConstruction(unittest.TestCase):
    """End-to-end parameter resolution onto a real instance (no Unity launch)."""

    def _build(self, factory, **kwargs):
        # use_dlc=False avoids opening the DLC socket; process_config is mocked
        # so no real Unity build path is required.
        kwargs.setdefault("use_dlc", False)
        with patch(
            "mouse_task.task_active_sensing.process_config", return_value=_MOCK_CONFIG
        ):
            return factory(teensy=MagicMock(), **kwargs)

    def test_generated_class_resolves_merged_params(self):
        task = self._build(mouse_task.ShapeDiscrim)
        self.assertEqual(task.session_label, ["ar_shape_discrimination"])
        self.assertEqual(task.velocity_threshold, 5.0)
        self.assertEqual(task.target_selection_param, 13.0)
        self.assertEqual(task.slit_depth_param, 0.02)
        self.assertEqual(task.target_distance_param, 4.0)
        self.assertEqual(task.reward_size, [100])  # common default, wrapped by as_list
        self.assertFalse(task.use_dlc)

    def test_base_class_task_config_argument(self):
        # The main class can be driven directly by task_config alone.
        task = self._build(ActiveSensingTask, task_config="shape_mouse_discrim")
        self.assertEqual(task.velocity_threshold, 5.0)
        self.assertEqual(task.target_selection_param, 13.0)

    def test_explicit_argument_overrides_config(self):
        task = self._build(
            ActiveSensingTask, task_config="shape_mouse_discrim", velocity_threshold=99.0
        )
        self.assertEqual(task.velocity_threshold, 99.0)         # explicit wins
        self.assertEqual(task.target_selection_param, 13.0)     # rest from config

    def test_generated_class_forwards_gui_edit(self):
        # The GUI passes every signature param as a kwarg; an edited value must win.
        task = self._build(mouse_task.ShapeDiscrim, velocity_threshold=42.0)
        self.assertEqual(task.velocity_threshold, 42.0)

    def test_missing_params_without_task_config_raises(self):
        with patch(
            "mouse_task.task_active_sensing.process_config", return_value=_MOCK_CONFIG
        ):
            with self.assertRaises(ValueError):
                ActiveSensingTask(teensy=MagicMock(), use_dlc=False)  # no task_config, no params


class TestTeensyGuiTaskLoading(unittest.TestCase):
    """Regression tests for teensyexp task discovery and parameter introspection."""

    def test_update_tasks_ignores_non_task_symbols(self):
        from teensyexp.tasks_abc.task import Task
        from teensyexp.teensy_experiment import TeensyExperimentGUI

        class GoodTask(Task):
            def __init__(self, teensy, velocity_threshold=7.5, optional=None):
                super().__init__(teensy)

        class NotATask:
            def __init__(self, teensy, ignored=1):
                self.teensy = teensy

        class _Loader:
            def exec_module(self, module):
                module.GoodTask = GoodTask
                module.NotATask = NotATask
                module._TASK_CLASSES = {"GoodTask": GoodTask}
                module.some_constant = 123

        fake_spec = types.SimpleNamespace(loader=_Loader())
        fake_module = types.ModuleType("fake_tasks_pkg")

        gui = TeensyExperimentGUI.__new__(TeensyExperimentGUI)

        with patch("teensyexp.teensy_experiment.importlib.util.find_spec", return_value=fake_spec), \
             patch("teensyexp.teensy_experiment.importlib.util.module_from_spec", return_value=fake_module):
            gui.update_tasks("C:/tmp/fake_tasks_pkg")

        self.assertIn("GoodTask", gui.task_params)
        self.assertNotIn("NotATask", gui.task_params)
        self.assertEqual(gui.task_params["GoodTask"]["velocity_threshold"], 7.5)
        self.assertIsNone(gui.task_params["GoodTask"]["optional"])


if __name__ == "__main__":
    unittest.main()
