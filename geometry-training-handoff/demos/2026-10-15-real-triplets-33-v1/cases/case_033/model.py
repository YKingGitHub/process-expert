import cadquery as cq
import math

solid = cq.Workplane("XY").box(2370.0, 200.0, 20.0, centered=(False, False, False))
x_positions = [110.0, 260.0, 410.0, 560.0, 960.0, 1110.0,
               1260.0, 1410.0, 1810.0, 1960.0, 2110.0, 2260.0]
hole_points = [(x, y) for x in x_positions for y in (50.0, 150.0)]
solid = solid.cut(
    cq.Workplane("XY").pushPoints(hole_points).circle(4.5).extrude(20.0)
)
solid = solid.cut(
    cq.Workplane("XY").pushPoints(hole_points).circle(7.5).extrude(4.5)
)
solid = solid.cut(
    cq.Workplane("XY")
    .workplane(offset=15.5)
    .pushPoints(hole_points)
    .circle(7.5)
    .extrude(4.5)
)
