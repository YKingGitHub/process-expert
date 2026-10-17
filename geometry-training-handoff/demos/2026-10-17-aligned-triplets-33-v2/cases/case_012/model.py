"""Track-wheel bracket made from an upright profile, base flange, and gusset."""

import cadquery as cq


# Upright front silhouette: 150 mm wide, 150 mm high, R50 crown.
upright = (
    cq.Workplane("XY")
    .moveTo(-100.0, -75.0)
    .lineTo(-25.0, -75.0)
    .lineTo(0.0, -50.0)
    .threePointArc((50.0, 0.0), (0.0, 50.0))
    .lineTo(-25.0, 75.0)
    .lineTo(-100.0, 75.0)
    .close()
    .extrude(15.0)
)
upright_bore = (
    cq.Workplane("XY", origin=(0.0, 0.0, -1.0)).circle(15.5).extrude(17.0)
)
upright = upright.cut(upright_bore)

# Perpendicular mounting flange, including the two 18.5 mm mounting holes.
flange = (
    cq.Workplane("XY")
    .box(15.0, 150.0, 55.0, centered=(False, False, False))
    .translate((-100.0, -75.0, 0.0))
)
mounting_holes = (
    cq.Workplane("YZ", origin=(-101.0, 0.0, 0.0))
    .pushPoints([(-50.0, 35.0), (50.0, 35.0)])
    .circle(9.25)
    .extrude(17.0)
)
flange = flange.cut(mounting_holes)

gusset = (
    cq.Workplane("XZ")
    .moveTo(-85.0, 15.0)
    .lineTo(-35.0, 15.0)
    .lineTo(-35.0, 20.0)
    .lineTo(-75.0, 40.0)
    .lineTo(-85.0, 40.0)
    .close()
    .extrude(10.0)
)

solid = upright.union(flange).union(gusset)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[0, -1, 0, 7.105427357601002e-15], [1, 0, 0, 24.99999999999998], [0, 0, 1, -27.500000000000014], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [0.0, 0.0, 1.0], 90.0).translate([7.105427357601002e-15, 24.99999999999998, -27.500000000000014])
