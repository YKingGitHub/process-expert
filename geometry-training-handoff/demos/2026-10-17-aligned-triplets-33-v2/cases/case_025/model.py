import cadquery as cq
import math

def toothed_plate(teeth, root_radius, tip_radius, width, z0):
    points = []
    for index in range(teeth):
        center = 2.0 * math.pi * index / teeth
        half_pitch = math.pi / teeth
        for fraction, radius in (
            (-1.00, root_radius),
            (-0.58, root_radius),
            (-0.30, tip_radius),
            (0.30, tip_radius),
            (0.58, root_radius),
        ):
            angle = center + fraction * half_pitch
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return cq.Workplane("XY").workplane(offset=z0).polyline(points).close().extrude(width)

# 22-tooth, double-row 28A sprocket; axial source span is -8.065..81.935.
left_teeth = toothed_plate(22, 132.5, 166.57977, 25.42, 0.0)
right_teeth = toothed_plate(22, 132.5, 166.57977, 25.42, 64.58)
web = cq.Workplane("XY").workplane(offset=10.0).circle(105.0).extrude(70.0)
hub = cq.Workplane("XY").circle(72.5).extrude(90.0)
solid = left_teeth.union(right_teeth).union(web).union(hub)

solid = solid.cut(cq.Workplane("XY").circle(65.0).extrude(90.0))
solid = solid.cut(cq.Workplane("XY").circle(72.5).extrude(10.0))
solid = solid.cut(
    cq.Workplane("XY").workplane(offset=70.0).circle(72.5).extrude(20.0)
)
solid = solid.rotate((0, 0, 0), (0, 1, 0), 90).translate((-8.065, 0, 0))

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[0, 0, 1, -7.105427357601002e-14], [0, 1, 0, -0.0], [-1, 0, 0, 36.93500000000001], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [0.0, 1.0, 0.0], 90.0).translate([-7.105427357601002e-14, -0.0, 36.93500000000001])
