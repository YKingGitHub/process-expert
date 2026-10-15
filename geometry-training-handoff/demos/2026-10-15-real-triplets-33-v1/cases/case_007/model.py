"""100 x 100 x 8 rounded square tube, 480 mm long."""

import cadquery as cq


length = 480.0
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
