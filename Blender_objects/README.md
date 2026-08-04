# main.py

Procedurally builds the teardrop-family game objects and exports each as a
Unity-ready FBX.

## Usage

1. Open a new (or empty-scene) Blender project.
2. Go to the **Scripting** tab, open `main.py`.
3. Edit `EXPORT_DIR` near the top of the file to an absolute path on disk.
4. Run the script (**Run Script**, or Alt+P).
5. One `.fbx` per object in `OBJECTS` lands in `EXPORT_DIR`, ready to drag
   into Unity's `Assets/` folder.

## Customizing objects

Edit the `OBJECTS` dict at the bottom of the file. Each entry is
`"Name": [tail_spec, ...]`, where a tail spec is either:

- a bare angle in degrees — tilt from vertical around the X axis, using the
  default tail length, e.g. `20`
- an `(angle_deg, length)` tuple for a custom tail length, e.g. `(20, 1.8)`

```python
OBJECTS = {
    "Teardrop": [0],           # one tail, straight up
    "PacmanWide": [30, -30],   # two tails, symmetric
}
```

Re-run the script to rebuild and re-export.
