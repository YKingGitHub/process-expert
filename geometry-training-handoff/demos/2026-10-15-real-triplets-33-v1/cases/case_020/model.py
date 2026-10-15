import cadquery as cq
import math

outer_radius = 98.0
length = 141.0
solid = cq.Workplane("XY").circle(outer_radius).extrude(length)

# Stepped axial passage and forty-tooth internal gear region.
solid = solid.cut(cq.Workplane("XY").circle(42.5).extrude(length))
solid = solid.cut(cq.Workplane("XY").circle(57.0).extrude(53.0))
tooth_spaces = None
for index in range(40):
    angle = 2.0 * math.pi * index / 40.0
    half = math.pi / 40.0 * 0.42
    points = [
        (57.0 * math.cos(angle - half), 57.0 * math.sin(angle - half)),
        (63.75 * math.cos(angle - half * 0.50), 63.75 * math.sin(angle - half * 0.50)),
        (63.75 * math.cos(angle + half * 0.50), 63.75 * math.sin(angle + half * 0.50)),
        (57.0 * math.cos(angle + half), 57.0 * math.sin(angle + half)),
    ]
    cutter = cq.Workplane("XY").polyline(points).close().extrude(45.0)
    tooth_spaces = cutter if tooth_spaces is None else tooth_spaces.union(cutter)
solid = solid.cut(tooth_spaces)
solid = solid.cut(
    cq.Workplane("XY").workplane(offset=61.0).circle(65.0).extrude(70.0)
)
solid = solid.cut(
    cq.Workplane("XY").workplane(offset=131.0).circle(70.0).extrude(10.0)
)

# Eight blind M8 tapping-drill holes on the 155 mm pitch circle.
hole_points = []
for index in range(8):
    angle = 2.0 * math.pi * index / 8.0 + math.pi / 8.0
    hole_points.append((77.5 * math.cos(angle), 77.5 * math.sin(angle)))
solid = solid.cut(
    cq.Workplane("XY").pushPoints(hole_points).circle(3.4).extrude(22.0)
)

# Radial M12 port at the indicated z=53 level, simplified to its tap drill.
radial = (
    cq.Workplane("XZ")
    .workplane(offset=-98.0)
    .center(0.0, 53.0)
    .circle(5.1)
    .extrude(196.0)
)
solid = solid.cut(radial)
