"""100 x 100 x 8 rounded square tube, 220 mm long."""

import cadquery as cq


length = 220.0
outer = (
    cq.Workplane("XY")
    .box(length, 100.0, 100.0, centered=(False, True, True))
    .edges("|X")
    .fillet(16.0)
)
inner = (
    cq.Workplane("XY")
    .box(length + 2.0, 84.0, 84.0, centered=(False, True, True))
    .translate((-1.0, 0.0, 0.0))
    .edges("|X")
    .fillet(8.0)
)
solid = outer.cut(inner)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[1, 0, 0, -109.99999999999943], [0, 1, 0, 6.750155989720952e-14], [0, 0, 1, -3.339550858072471e-13], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [1, 0, 0], 0.0).translate([-109.99999999999943, 6.750155989720952e-14, -3.339550858072471e-13])
