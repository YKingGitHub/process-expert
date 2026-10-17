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

left_teeth = toothed_plate(15, 83.5, 116.221975, 23.45, 0.0)
right_teeth = toothed_plate(15, 83.5, 116.221975, 22.0, 58.0)
body = cq.Workplane("XY").circle(83.5).extrude(80.0)
solid = body.union(left_teeth).union(right_teeth)
solid = solid.cut(cq.Workplane("XY").circle(35.0).extrude(80.0))
solid = solid.cut(cq.Workplane("XY").circle(40.0).extrude(23.45))
solid = solid.cut(
    cq.Workplane("XY").workplane(offset=54.58).circle(41.75).extrude(25.42)
)
solid = solid.rotate((0, 0, 0), (0, 1, 0), 90).translate((-3.065, 0, 0))

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[0, 0, 1, -6.394884621840902e-14], [0, 1, 0, -0.953221511796734], [-1, 0, 0, 36.935], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [0.0, 1.0, 0.0], 90.0).translate([-6.394884621840902e-14, -0.953221511796734, 36.935])
