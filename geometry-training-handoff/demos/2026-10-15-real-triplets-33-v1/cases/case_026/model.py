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

left_teeth = toothed_plate(17, 69.0, 93.246405, 17.58, 0.0)
right_teeth = toothed_plate(17, 69.0, 93.246405, 17.58, 57.18)
body = cq.Workplane("XY").circle(69.0).extrude(74.76)
solid = body.union(left_teeth).union(right_teeth)
solid = solid.cut(cq.Workplane("XY").circle(30.0).extrude(74.76))

# 18 mm keyway extending radially from the 60 mm nominal bore.
keyway = (
    cq.Workplane("XY")
    .workplane(offset=0.0)
    .center(0.0, 34.5)
    .rect(18.0, 9.0)
    .extrude(74.76)
)
solid = solid.cut(keyway)
solid = solid.rotate((0, 0, 0), (0, 1, 0), 90)
