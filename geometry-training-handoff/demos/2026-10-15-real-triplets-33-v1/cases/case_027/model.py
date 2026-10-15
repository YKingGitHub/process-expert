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

teeth = toothed_plate(17, 69.0, 93.246405, 17.58, 0.7115)
web = cq.Workplane("XY").circle(50.0).extrude(50.0)
solid = web.union(teeth)
solid = solid.cut(cq.Workplane("XY").circle(21.0).extrude(50.0))

keyway = (
    cq.Workplane("XY")
    .center(0.0, 24.0)
    .rect(12.0, 6.0)
    .extrude(50.0)
)
solid = solid.cut(keyway)
solid = solid.rotate((0, 0, 0), (0, 1, 0), 90)
