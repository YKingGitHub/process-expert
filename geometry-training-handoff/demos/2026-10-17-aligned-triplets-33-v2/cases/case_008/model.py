"""1000 x 160 x 15 track adapter plate with ten 8.5 mm holes."""

import cadquery as cq


solid = cq.Workplane("XY").box(
    1000.0, 160.0, 15.0, centered=(False, False, False)
)
hole_centers = [
    (x, y)
    for x in (25.0, 260.0, 495.0, 730.0, 965.0)
    for y in (15.0, 145.0)
]
holes = (
    cq.Workplane("XY", origin=(0.0, 0.0, -1.0))
    .pushPoints(hole_centers)
    .circle(4.25)
    .extrude(17.0)
)
solid = solid.cut(holes)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[0, 1, 0, -80.00000000000007], [-1, 0, 0, 499.9999999999998], [0, 0, 1, -7.500000000003393], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [0.0, 0.0, -1.0], 90.0).translate([-80.00000000000007, 499.9999999999998, -7.500000000003393])
