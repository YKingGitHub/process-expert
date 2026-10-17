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

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[1, 0, 0, 1.4999999999999645], [0, 1, 0, -1741.2387563597404], [0, 0, 1, -7.5], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [1, 0, 0], 0.0).translate([1.4999999999999645, -1741.2387563597404, -7.5])
