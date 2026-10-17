import cadquery as cq
import math

# Turned rail wheel: central barrel and the right-end running flange.
barrel = cq.Workplane("XY").circle(53.0).extrude(100.0)
right_flange = cq.Workplane("XY").workplane(offset=93.0).circle(75.0).extrude(22.0)
solid = barrel.union(right_flange)

solid = solid.cut(cq.Workplane("XY").circle(31.0).extrude(115.0))
solid = solid.cut(cq.Workplane("XY").circle(36.0).extrude(22.0))
solid = solid.cut(
    cq.Workplane("XY").workplane(offset=93.0).circle(37.5).extrude(22.0)
)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[1, 0, 0, -0.0], [0, 1, 0, -0.0], [0, 0, 1, -57.5], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [1, 0, 0], 0.0).translate([-0.0, -0.0, -57.5])
