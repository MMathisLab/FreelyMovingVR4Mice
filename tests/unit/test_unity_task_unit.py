import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np


def _load_unity_task_with_stubs():
    class FakeActionTuple:
        def __init__(self):
            self.continuous = None

        def add_continuous(self, arr):
            self.continuous = arr

    class FakeChannel:
        def __init__(self):
            self._props = {}

        def list_properties(self):
            return list(self._props.keys())

        def get_property(self, name):
            return self._props[name]

    class FakeFloatChannel:
        pass

    env_module = types.ModuleType("mlagents_envs.environment")
    env_module.ActionTuple = FakeActionTuple
    env_module.UnityEnvironment = object

    params_module = types.ModuleType(
        "mlagents_envs.side_channel.environment_parameters_channel"
    )
    params_module.EnvironmentParametersChannel = FakeChannel

    float_module = types.ModuleType("mlagents_envs.side_channel.float_properties_channel")
    float_module.FloatPropertiesChannel = FakeFloatChannel

    side_channel_module = types.ModuleType("mlagents_envs.side_channel")
    mlagents_module = types.ModuleType("mlagents_envs")

    stubs = {
        "cv2": MagicMock(),
        "mlagents_envs": mlagents_module,
        "mlagents_envs.environment": env_module,
        "mlagents_envs.side_channel": side_channel_module,
        "mlagents_envs.side_channel.environment_parameters_channel": params_module,
        "mlagents_envs.side_channel.float_properties_channel": float_module,
    }

    with patch.dict(sys.modules, stubs):
        module = importlib.import_module("teensyexp.tasks_abc.unity_task")
        module = importlib.reload(module)

    return module, FakeActionTuple


def _build_fake_env(terminal=False):
    class FakeActionSpec:
        continuous_size = 4
        discrete_size = []

        @staticmethod
        def is_continuous():
            return True

        @staticmethod
        def is_discrete():
            return False

    class FakeStepResult:
        def __init__(self):
            self.obs = [np.array([[1.0, 2.0, 3.0]], dtype=np.float32)]
            self.reward = 1.5

    class FakeDecisionSteps:
        def __init__(self):
            self.obs = [np.array([[0.1, 0.2, 0.3]], dtype=np.float32)]
            self._step = FakeStepResult()

        def __getitem__(self, _idx):
            return self._step

    class FakeTerminalSteps:
        def __init__(self, done):
            self.agent_id = [0] if done else []
            self._step = FakeStepResult()

        def __getitem__(self, _idx):
            return self._step

    class FakeEnv:
        def __init__(self):
            self.behavior_specs = {
                "MockBehavior": SimpleNamespace(
                    observation_specs=[SimpleNamespace(shape=(3,))],
                    action_spec=FakeActionSpec(),
                )
            }
            self.reset_calls = 0
            self.step_calls = 0
            self.closed = False
            self.last_action = None

        def reset(self):
            self.reset_calls += 1

        def get_steps(self, _agent):
            return FakeDecisionSteps(), FakeTerminalSteps(terminal)

        def set_actions(self, _agent, action_tuple):
            self.last_action = action_tuple

        def step(self):
            self.step_calls += 1

        def close(self):
            self.closed = True

    return FakeEnv()


def test_unity_task_start_loop_stop_without_mlagents_runtime():
    module, fake_action_tuple_cls = _load_unity_task_with_stubs()
    UnityTask = module.UnityTask

    teensy = MagicMock()
    fake_env = _build_fake_env(terminal=False)

    with patch.object(module, "UnityEnvironment", return_value=fake_env):
        task = UnityTask(teensy=teensy, env="fake_unity_build", epochs=[10])
        task.start()

        assert task.episode == 1
        assert task.agent == "MockBehavior"
        teensy.write.assert_any_call("start")

        keep_running, info = task.loop()

        assert keep_running is True
        assert "episode" in info
        assert fake_env.step_calls == 1
        assert isinstance(fake_env.last_action, fake_action_tuple_cls)
        assert fake_env.last_action.continuous.shape == (1, 4)

        task.stop()
        teensy.write.assert_any_call("stop")
        assert fake_env.closed is True
