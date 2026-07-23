"""
Run in Blender's Scripting tab.

Each tail is the exact tangent cone from an apex point to the shared sphere
(cone's slant surface meets the sphere along one tangent circle -> smooth
join, no bevel pass needed). Given center O, radius R, apex P, D=|P-O|>R:
    axis   = normalize(O - P)
    L      = sqrt(D^2 - R^2)      tangent length
    r_base = R * L / D
    h_cone = L^2 / D

Tail directions are built by rotating +Z around the X axis only, so every
apex has X = center.x exactly -- tails on one object stay coplanar with no
separate check (tail_direction_x_rotation).

True tangency is zero-volume contact and Boolean solvers need real overlap,
so the cone is computed against a hair-smaller phantom radius (TANGENT_EPSILON)
while the apex stays exactly where specified.
"""

import bpy
import math
import os
from mathutils import Vector

SPHERE_RADIUS = 1.0
SPHERE_SEGMENTS = 64
SPHERE_RINGS = 32
TAIL_VERTS = 64

TANGENT_EPSILON = SPHERE_RADIUS * 1e-4
DEFAULT_TAIL_LENGTH = SPHERE_RADIUS * 2.1

EXPORT_DIR = "/absolute/path/to/export/folder"  # <-- change this before running


def create_shared_sphere(name, location):
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=SPHERE_RADIUS, location=location,
        segments=SPHERE_SEGMENTS, ring_count=SPHERE_RINGS,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_tangent_tail(name, sphere_center, apex_point):
    O, P = Vector(sphere_center), Vector(apex_point)
    D = (P - O).length
    if D <= SPHERE_RADIUS:
        raise ValueError(f"{name}: apex point (D={D:.4f}) must be strictly "
                          f"outside the sphere (R={SPHERE_RADIUS}).")

    R_eff = SPHERE_RADIUS - TANGENT_EPSILON
    axis_dir = (O - P).normalized()
    L = math.sqrt(D * D - R_eff * R_eff)
    r_base = R_eff * L / D
    h_cone = L * L / D

    center_location = P + axis_dir * (h_cone / 2)
    tip_dir = -axis_dir  # cone's local +Z (apex) must aim sphere-center -> apex

    bpy.ops.mesh.primitive_cone_add(
        vertices=TAIL_VERTS, radius1=r_base, radius2=0.0,
        depth=h_cone, location=center_location,
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = tip_dir.to_track_quat('Z', 'Y')
    return obj


def boolean_union_and_merge(target, *parts):
    for part in parts:
        mod = target.modifiers.new(name="Union_" + part.name, type='BOOLEAN')
        mod.operation = 'UNION'
        mod.object = part
        mod.solver = 'EXACT'
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(part, do_unlink=True)


def apply_auto_smooth(obj, angle_deg=30):
    """Blender 4.1+: Shade Auto Smooth is a modifier, not a mesh flag."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_auto_smooth(use_auto_smooth=True, angle=math.radians(angle_deg))


def export_fbx(obj):
    """Unity is -Z forward / Y up; location is zeroed so the exported pivot
    is world origin, then restored so the Blender-side layout is unaffected."""
    os.makedirs(EXPORT_DIR, exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    original_location = obj.location.copy()
    obj.location = (0.0, 0.0, 0.0)

    filepath = os.path.join(EXPORT_DIR, obj.name + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=True,
        axis_forward='-Z',
        axis_up='Y',
        use_space_transform=True,
        bake_space_transform=True,   # "Apply Transform"
        apply_unit_scale=True,       # "Apply Unit"
        apply_scale_options='FBX_SCALE_ALL',
    )
    print(f"Exported: {filepath}")

    obj.location = original_location


def build_object(name, location, apex_points):
    sphere = create_shared_sphere(name, location)
    parts = [create_tangent_tail(f"{name}_tail{i}", location, apex)
             for i, apex in enumerate(apex_points)]
    boolean_union_and_merge(sphere, *parts)
    apply_auto_smooth(sphere)
    return sphere


def tail_direction_x_rotation(angle_deg):
    """+Z tilted angle_deg around X -- keeps direction.x == 0 (see module docstring)."""
    a = math.radians(angle_deg)
    return Vector((0, -math.sin(a), math.cos(a)))


def apex_from_length(center, direction, length):
    """Inverts length = (D^2 - R^2) / D for D, i.e. D^2 - length*D - R^2 = 0."""
    R = SPHERE_RADIUS
    D = (length + math.sqrt(length ** 2 + 4 * R ** 2)) / 2
    return Vector(center) + direction * D


def build_from_specs(name, location, tail_specs):
    """tail_specs entries: bare angle_deg, or (angle_deg, length)."""
    center = Vector(location)
    apexes = []
    for spec in tail_specs:
        angle_deg, length = spec if isinstance(spec, tuple) else (spec, DEFAULT_TAIL_LENGTH)
        direction = tail_direction_x_rotation(angle_deg)
        apexes.append(apex_from_length(center, direction, length))
    return build_object(name, center, apexes)


# ---- define your objects here ----
OBJECTS = {
    "Teardrop":      [0],
    "PacmanNarrow":  [10, -10],
    "PacmanNeutral": [20, -20],
    "PacmanWide":    [30, -30],
    "ThreeTails":    [30, -30, 0],
}

x = 0
for name, tail_specs in OBJECTS.items():
    obj = build_from_specs(name, (x, 0, 0), tail_specs)
    export_fbx(obj)
    x += 4

print(f"Built and exported {len(OBJECTS)} object(s), each with coplanar "
      f"tangent-cone tails on identical {SPHERE_RADIUS}-radius spheres, "
      f"to individual .fbx files in {EXPORT_DIR}")
