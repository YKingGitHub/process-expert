import cadquery as cq
import math

left_end = cq.Workplane("XY").circle(15.0).extrude(50.0)
left_collar = cq.Workplane("XY").workplane(offset=50.0).circle(16.5).extrude(7.5)
center = cq.Workplane("XY").workplane(offset=57.5).circle(17.5).extrude(105.0)
right_collar = cq.Workplane("XY").workplane(offset=162.5).circle(16.5).extrude(7.5)
right_end = cq.Workplane("XY").workplane(offset=170.0).circle(15.0).extrude(50.0)
solid = left_end.union(left_collar).union(center).union(right_collar).union(right_end)

# Two 1.6 mm-wide undercut reliefs at the shoulder transitions.
left_relief = cq.Workplane("XY").workplane(offset=55.9).circle(17.6).circle(14.0).extrude(1.6)
right_relief = cq.Workplane("XY").workplane(offset=162.5).circle(17.6).circle(14.0).extrude(1.6)
solid = solid.cut(left_relief).cut(right_relief).translate((0.0, 0.0, -50.0))
