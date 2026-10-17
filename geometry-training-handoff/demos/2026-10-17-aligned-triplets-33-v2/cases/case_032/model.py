import cadquery as cq
import math

solid = cq.Workplane("XY").circle(75.0).circle(30.0).extrude(3.0)
hole_points = [(60.35, 0.0), (-60.35, 0.0), (0.0, 60.35), (0.0, -60.35)]
solid = solid.cut(
    cq.Workplane("XY").pushPoints(hole_points).circle(9.5).extrude(3.0)
)
solid = solid.rotate((0, 0, 0), (1, 0, 0), -90)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[1, 0, 0, -0.0], [0, 0, -1, -0.0], [0, 1, 0, -1.499999949998952], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [1.0, 0.0, 0.0], 90.0).translate([-0.0, -0.0, -1.499999949998952])
