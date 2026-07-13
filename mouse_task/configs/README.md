# Task configs

Modular configuration for the Active Sensing task variants, mirroring the
`rl_task/configs/` pattern.

```
configs/
├── common.yaml        # parameters shared by every task variant
└── tasks/
    ├── mouse_discrim.yaml
    ├── shape_mouse_discrim.yaml
    └── ...             # one file per variant: only what differs
```

## How it works

- `common.yaml` holds the default value for **every** task parameter.
- Each `tasks/<name>.yaml` declares a `class_name`, a `description`, and a
  `params:` block containing **only the entries that differ** from `common.yaml`.
- `mouse_task.helpers.load_task_config(<name>)` deep-merges the two.
- At import, `mouse_task._registry` generates one `ActiveSensingTask` subclass
  per task YAML. The generated `__init__` keeps a real, introspectable signature
  (every parameter as a keyword arg with its merged default) so the teensyexp
  GUI can still build its editable parameter form, and it passes
  `task_config="<name>"` down to `ActiveSensingTask`.
- Generated classes are exposed as `mouse_task.<ClassName>` (used by the GUI
  task list and the RL pipeline's `task_variant` strings).

## Add a new task

1. Create `tasks/my_task.yaml`:

   ```yaml
   class_name: MyTask
   description: |
     One-line summary of the task.

   params:
     session_label: ["ar_my_task"]
     slit_size: [4.0, 4.0, 1]
     # ...only the parameters that differ from common.yaml
   ```

2. It is picked up automatically — `mouse_task.MyTask` becomes importable and
   appears in the GUI task drop-down. No Python file to write.

## Run a task directly

```python
from mouse_task.task_active_sensing import ActiveSensingTask
task = ActiveSensingTask(teensy, task_config="shape_mouse_discrim")
```

Any parameter passed explicitly overrides the value from the merged config.
The machine-specific `config_file_path` (the `task_config.json` holding the
absolute Unity build path) is separate and defaults to
`mouse_task/task_config.json`.
