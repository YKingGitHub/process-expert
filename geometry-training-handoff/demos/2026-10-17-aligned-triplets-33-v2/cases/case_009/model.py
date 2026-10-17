"""178 mm long drain tube, 57 mm OD and 53 mm ID."""

import cadquery as cq


solid = (
    cq.Workplane("YZ", origin=(-220.0, -162.0, 0.0))
    .circle(28.5)
    .circle(26.5)
    .extrude(178.0)
)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[1, 0, 0, 130.99999999999935], [0, 1, 0, 162.00000000000273], [0, 0, 1, -7.993605777301127e-14], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [1, 0, 0], 0.0).translate([130.99999999999935, 162.00000000000273, -7.993605777301127e-14])
