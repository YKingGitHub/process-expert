import cadquery as cq
import math

solid = cq.Workplane("XY").circle(40.0).circle(5.5).extrude(8.0)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[1, 0, 0, -0.0], [0, 1, 0, -0.0], [0, 0, 1, -4.0], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [1, 0, 0], 0.0).translate([-0.0, -0.0, -4.0])
