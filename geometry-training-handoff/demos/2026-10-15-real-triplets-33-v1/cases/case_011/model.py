"""Welded lifting-lug hinge: perforated back plate, foot, and centre rib."""

import cadquery as cq


x_min = -878.3012701892171
x_max = -573.3012701892169
x_mid = (x_min + x_max) / 2.0

back_plate = (
    cq.Workplane("XY")
    .box(305.0, 200.0, 22.0, centered=(False, False, False))
    .translate((x_min, -100.0, 0.0))
)
hole_centers = [
    (x, y)
    for x in (x_min + 45.0, x_max - 45.0)
    for y in (-72.0, -1.0, 70.0)
]
back_holes = (
    cq.Workplane("XY", origin=(0.0, 0.0, -1.0))
    .pushPoints(hole_centers)
    .circle(9.0)
    .extrude(24.0)
)
back_plate = back_plate.cut(back_holes)

foot = (
    cq.Workplane("XY")
    .box(305.0, 15.0, 40.0, centered=(False, False, False))
    .translate((x_min, -115.0, -18.0))
)

# The rib outline follows the dimensioned side-view envelope.  The two long
# transitions are kept planar; the reference uses blended R10/R20 corners.
rib = (
    cq.Workplane("YZ", origin=(x_mid - 30.0, 0.0, 0.0))
    .moveTo(-100.0, 22.0)
    .lineTo(100.0, 22.0)
    .lineTo(100.0, 92.0)
    .threePointArc((94.1421356, 106.1421356), (80.0, 112.0))
    .lineTo(30.0, 112.0)
    .lineTo(-90.0, 55.0)
    .lineTo(-100.0, 50.0)
    .close()
    .extrude(60.0)
)
rib_hole = (
    cq.Workplane("YZ", origin=(x_mid - 31.0, 0.0, 0.0))
    .center(60.0, 67.0)
    .circle(12.5)
    .extrude(62.0)
)
rib = rib.cut(rib_hole)

solid = back_plate.union(foot).union(rib)
