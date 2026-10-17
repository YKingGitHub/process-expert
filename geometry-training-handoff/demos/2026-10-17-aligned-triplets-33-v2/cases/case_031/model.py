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

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[1, 0, 0, -0.0], [0, 1, 0, 2.2026824808563106e-13], [0, 0, 1, -8.749999999999158], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [1, 0, 0], 0.0).translate([-0.0, 2.2026824808563106e-13, -8.749999999999158])
