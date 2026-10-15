"""560 x 360 x 25 mounting plate with C5 corners and four 17.5 mm holes."""

import cadquery as cq


x_min = -434.912172353
y_min = -63.134059881
plate = (
    cq.Workplane("XY")
    .box(560.0, 360.0, 25.0, centered=(False, False, False))
    .translate((x_min, y_min, 0.0))
    .edges("|Z")
    .chamfer(5.0)
)
hole_centers = [
    (x, y)
    for x in (x_min + 40.0, x_min + 520.0)
    for y in (y_min + 70.0, y_min + 290.0)
]
holes = (
    cq.Workplane("XY", origin=(0.0, 0.0, -1.0))
    .pushPoints(hole_centers)
    .circle(8.75)
    .extrude(27.0)
)
solid = plate.cut(holes)
