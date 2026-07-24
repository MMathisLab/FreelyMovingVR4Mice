# What happens when you run a session

This page is the developer-facing counterpart to the [step-by-step session guide](../software_installation/run_a_session.md).
It walks through what actually happens in the code across a session, from opening the two GUIs to the data landing on disk.

## The two processes, and what each one owns

A session always involves two independent processes that never share memory — only a live socket connects them:

| | **vr4mice** (`teensyexp/teensy_experiment.py`) | **DeepLabCut-live-GUI** (external repo) |
|---|---|---|
| Owns | The Teensy (water/reward, trial logic), the Unity game, trial/session bookkeeping | The camera, DLC pose inference, the photodiode Teensy |
| Talks to | `DLCClient` — reads position data | `MyProcessor_socket`/`dlc_inference_w_pd(_sync)` — a `Listener` that streams position data |
| Saves | Trial/Teensy/Unity data, via the **"Save Task Data"** button | PROC/HDF5/timestamp/video files, via its own **"Stop"/"Save Video"** buttons |

The socket (`("localhost", 6000)`, `multiprocessing.connection`) only carries **live pose/kinematics data one way**, DLCLiveGUI &rarr; vr4mice,
for driving the Unity game in real time. It is not used for control messages, and it is not the authoritative record of anything —
see [Saving the data](#saving-the-data) below for why.

## Startup

1. **vr4mice**: `Connect` opens `Teensy(...)` ([teensy.py](../../teensyexp/teensy.py)), which starts a background thread polling the serial
   port for reward/lick inputs. `Ready` constructs the task (e.g. `ActiveSensingTask`, [task_active_sensing.py](../../mouse_task/task_active_sensing.py)),
   which in turn constructs `DLCClient` ([dlc_deque_socket.py](../../teensyexp/tasks_abc/dlc_deque_socket.py)) — this immediately tries to
   connect to `("localhost", 6000)` on a background thread, and opens the Unity build via `UnityEnvironment`.
2. **DLCLiveGUI**: `Init Cam` &rarr; `Set Proc` (loads e.g. `dlc_inference_w_pd_sync`, which opens the `Listener` on port 6000 and, if
   `use_teensy=1`, its own `TeensyLatency`/`TeensyLatencySync` serial connection to the photodiode Teensy) &rarr; `Init DLC`.
3. Whichever side starts first just waits/retries until the other side's socket endpoint exists — there's no explicit handshake beyond
   the `multiprocessing.connection` auth key.

## During the run

Every game frame, `UnityTask.loop()` ([unity_task.py](../../teensyexp/tasks_abc/unity_task.py)):
1. Steps the Unity environment and reads back observations/reward.
2. Calls `ActiveSensingTask._get_dlc_on_frame()`, which does `self.dlcClient.read()` to get the latest position/heading from the DLC
   processor (used as an input to the agent/game logic). Note `DLCClient.read()` clears its buffer on every call — it's a live sample,
   not an accumulating log.
3. On a trial boundary (`self.terminal`), increments `self.episode`; once `self.episode` exceeds the current epoch's trial count
   (`epochs` config, default `[250]` — see [common.yaml](../../mouse_task/configs/common.yaml)), advances to the next epoch, or ends the
   task if there isn't one.

Meanwhile, on every camera frame, the DLC processor's `process()` computes position/heading/TTL-signal, buffers it in its own deques
(`self.center_x`, `self.time_stamp`, ...), and streams it to whichever client is connected — tolerating a client that isn't there yet
or has disconnected (see [Failure handling](#failure-handling)).

## Stopping

There are two independent stop actions, and reaching one does **not** trigger the other:

- **The task stops** (250-trial cap reached, or the experimenter hits vr4mice's "Stop"): `run_task_on_thread` exits its loop and calls
  `task.stop()` ([teensy_experiment.py](../../teensyexp/teensy_experiment.py)), which for `ActiveSensingTask` closes the Teensy serial
  connection, the Unity env, and the `DLCClient` socket/thread.
- **The DLC processor stops**: only when the experimenter hits DLCLiveGUI's own "Stop"/"Save Video" — this closes the photodiode
  Teensy and flushes the processor's buffered data to disk. It is not aware of, and does not react to, the vr4mice task stopping.

This is why the [session guide](../software_installation/run_a_session.md#saving-data) has you stop/save on **both** GUIs, in a specific
order — they are not automatically linked.

## Saving the data

Two entirely separate save paths, triggered by two separate manual actions:

- **vr4mice**: "Save Task Data" &rarr; `save_data()` &rarr; `task.get_data()` (trial params, Teensy inputs/outputs, Unity states) &rarr;
  pickled to `<save dir>/<subject>_<date>_<attempt>.pickle`.
- **DLCLiveGUI**: "Stop" + "Save Video" &rarr; `on_recording_stopped()` hook on the processor &rarr; `save()` (PROC pickle),
  `save_legacy_dlc_h5()` (`.h5`), `save_legacy_timestamp_npy()` (`_TS.npy`), plus the GUI's own `.avi` video save.

Neither side has incremental/periodic autosave — both buffer an entire session in RAM and flush once, on that manual trigger. A crash
or force-quit before that trigger loses whatever hasn't been flushed yet on that side.

vr4mice does warn about unsaved data at two points: clicking **"Ready"** to initialize a new task (which replaces `self.task`, making
the previous task's in-memory data unreachable) shows a one-time, dismissible reminder if the current task hasn't been saved yet; and
closing the window (via the "Close" button, the window's `[X]`, or Ctrl+C in the terminal) shows a blocking "did you save?" confirmation
if `saved_ok` is still `False`. Neither is a hard requirement — you can proceed either way — they're just there so an unsaved session
isn't discarded purely by accident.

## Failure handling

A few things worth knowing about how this stack behaves under partial failure:

- **Closing a serial port while a background reader thread is blocked on it** is a known hazard on Windows/pyserial (a blocked
  `readline()` racing a `close()` from another thread raises `TypeError: byref() argument must be a ctypes instance, not 'NoneType'`).
  Both `TeensyLatency.close_serial()` and `Teensy.close()` avoid this by using a read timeout and joining the reader thread before
  closing the port.
- **`DLCClient`/socket disconnects are expected and handled on the processor side** — `MyProcessor_socket.process()` catches send
  failures and just resets `self.conn`; it re-`accept()`s a fresh client on the next frame. `ActiveSensingTask.stop()` closes its
  `dlcClient` (and joins its reader thread) so the socket/thread don't linger past the task's lifetime; this is safe precisely because
  the processor side already tolerates a client disconnecting at any time.
- **Neither side's save is atomic** — both write pickle/HDF5/npy files directly to their final path. A crash or disk-full condition
  mid-write can leave a truncated file at that path, including overwriting a previously-good one if re-saving to the same filename.
- **`save_legacy_timestamp_npy()`** (DLC processor side) depends on timestamp JSON files written by DLCLiveGUI's video recorder, a
  separate component. If ever called before that recorder has finished flushing, it degrades gracefully — logs a warning and returns
  `0` — rather than raising, so it's safe to call speculatively, just possibly a no-op in that case.

## Where to look for what

| Concern | File |
|---|---|
| GUI shell, session start/stop/save wiring | `teensyexp/teensy_experiment.py` |
| Generic task lifecycle (`loop`/`stop`/`get_data` contract) | `teensyexp/tasks_abc/task.py` |
| Unity-specific task base (epoch/trial counting, env step) | `teensyexp/tasks_abc/unity_task.py` |
| The concrete task used in practice | `mouse_task/task_active_sensing.py` |
| Task-variant config (per-task YAML overrides) | `mouse_task/configs/` (see `configs/README.md`) |
| Rig Teensy (reward/lick I/O) | `teensyexp/teensy.py` |
| Photodiode Teensy (latency capture) | `mouse_task/latency_tests/Teensy_latency/TeensyLatency*.py` |
| Position-data socket client (task side) | `teensyexp/tasks_abc/dlc_deque_socket.py` |
| Position-data socket server + saving (processor side) | `mouse_task/dlc_utils/dlc_processor_socket*.py` |
