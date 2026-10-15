"""178 mm long drain tube, 57 mm OD and 53 mm ID."""

import cadquery as cq


solid = (
    cq.Workplane("YZ", origin=(-220.0, -162.0, 0.0))
    .circle(28.5)
    .circle(26.5)
    .extrude(178.0)
)
