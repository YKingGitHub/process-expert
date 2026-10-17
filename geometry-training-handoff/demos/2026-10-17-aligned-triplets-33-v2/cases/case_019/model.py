"""Stepped nylon grease-seal cap, 105 mm flange and 85 mm locating boss."""

import cadquery as cq


boss = cq.Workplane("XY").circle(42.5).extrude(5.0)
boss = boss.edges("<Z").chamfer(1.0)
flange = cq.Workplane("XY", origin=(0.0, 0.0, 5.0)).circle(52.5).extrude(5.0)
solid = boss.union(flange)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[-1, 0, 0, -0.0], [0, 1, 0, -0.0], [0, 0, -1, 5.0], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [0.0, 1.0, 0.0], 180.0).translate([-0.0, -0.0, 5.0])
