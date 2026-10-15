"""Plain 90 mm diameter, 660 mm long transmission shaft."""

import cadquery as cq


solid = cq.Workplane("XY").circle(45.0).extrude(660.0)
