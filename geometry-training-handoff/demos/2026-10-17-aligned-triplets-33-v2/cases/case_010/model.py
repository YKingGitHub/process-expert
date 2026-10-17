"""32/28 mm cold-bent level tube with a 40 mm centreline bend radius."""

import cadquery as cq


path = cq.Wire.assembleEdges(
    [
        cq.Edge.makeLine(cq.Vector(0.0, 0.0, 0.0), cq.Vector(160.0, 0.0, 0.0)),
        cq.Edge.makeThreePointArc(
            cq.Vector(160.0, 0.0, 0.0),
            cq.Vector(188.2842712475, 11.7157287525, 0.0),
            cq.Vector(200.0, 40.0, 0.0),
        ),
        cq.Edge.makeLine(
            cq.Vector(200.0, 40.0, 0.0), cq.Vector(200.0, 900.0, 0.0)
        ),
    ]
)
solid = (
    cq.Workplane("YZ")
    .circle(16.0)
    .circle(14.0)
    .sweep(path, isFrenet=True, transition="round")
)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[0, 1, 0, -442.0000000000005], [1, 0, 0, -107.99999999999989], [0, 0, -1, 1.7763568394002505e-15], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [0.7071067811865476, 0.7071067811865475, 0.0], 180.0).translate([-442.0000000000005, -107.99999999999989, 1.7763568394002505e-15])
