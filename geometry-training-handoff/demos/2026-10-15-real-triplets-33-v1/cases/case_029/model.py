import cadquery as cq
import math

center_x = -1.5
center_y = 1741.23876
solid = (
    cq.Workplane("XY")
    .center(center_x, center_y)
    .rect(85.0, 150.0)
    .extrude(15.0)
)
hole_points = [
    (-14.5, 1696.23876),
    (11.5, 1696.23876),
    (-14.5, 1786.23876),
    (11.5, 1786.23876),
]
solid = solid.cut(
    cq.Workplane("XY").pushPoints(hole_points).circle(4.25).extrude(15.0)
)
