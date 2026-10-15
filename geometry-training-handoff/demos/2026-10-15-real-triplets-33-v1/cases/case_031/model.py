import cadquery as cq
import math

base = cq.Workplane("XY").circle(77.5).extrude(15.5)
raised_face = cq.Workplane(
    cq.Solid.makeCone(55.0, 53.0, 2.0, cq.Vector(0, 0, 15.5))
)
solid = base.union(raised_face)
solid = solid.cut(cq.Workplane("XY").circle(29.5).extrude(17.5))
holes = [(62.5, 0.0), (-62.5, 0.0), (0.0, 62.5), (0.0, -62.5)]
solid = solid.cut(
    cq.Workplane("XY").pushPoints(holes).circle(9.0).extrude(17.5)
)
