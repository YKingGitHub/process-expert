"""Plain 90 mm diameter, 660 mm long transmission shaft."""

import cadquery as cq


solid = cq.Workplane("XY").circle(45.0).extrude(660.0)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[0, 0, 1, -330.0], [0, 1, 0, -0.0], [-1, 0, 0, -0.0], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [0.0, 1.0, 0.0], 90.0).translate([-330.0, -0.0, -0.0])
