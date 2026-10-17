"""M30 connecting screw with a two-ear clevis head."""

import cadquery as cq


shaft = cq.Workplane("XY").circle(15.0).extrude(185.0)
shaft = shaft.edges("<Z").chamfer(2.0)


def ear(y_origin: float) -> cq.Workplane:
    return (
        cq.Workplane("XZ", origin=(0.0, y_origin, 0.0))
        .moveTo(-15.0, 200.0)
        .lineTo(15.0, 200.0)
        .lineTo(15.0, 230.0)
        .threePointArc((0.0, 245.0), (-15.0, 230.0))
        .close()
        .extrude(27.0)
    )


lower_head = (
    cq.Workplane("YZ", origin=(-15.0, 0.0, 0.0))
    .moveTo(-22.0, 185.0)
    .lineTo(22.0, 185.0)
    .lineTo(37.0, 200.0)
    .lineTo(37.0, 205.0)
    .lineTo(-37.0, 205.0)
    .lineTo(-37.0, 200.0)
    .close()
    .extrude(30.0)
)
head = lower_head.union(ear(37.0)).union(ear(-10.0))
pin_hole = (
    cq.Workplane("XZ", origin=(0.0, 38.0, 0.0))
    .center(0.0, 230.0)
    .circle(7.5)
    .extrude(76.0)
)
solid = shaft.union(head).cut(pin_hole)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[0, 0, -1, 122.5], [0, 1, 0, -3.552713678800501e-15], [1, 0, 0, -0.0], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [0.0, -1.0, 0.0], 90.0).translate([122.5, -3.552713678800501e-15, -0.0])
