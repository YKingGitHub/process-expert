import cadquery as cq
import math

solid = cq.Workplane("XY").circle(40.0).circle(5.5).extrude(8.0)
