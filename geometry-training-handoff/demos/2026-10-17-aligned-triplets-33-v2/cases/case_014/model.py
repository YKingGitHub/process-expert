"""Hydraulic-cylinder Y clevis with dissimilar fork bores and top eye."""

import cadquery as cq


def fork_arm(x_start: float) -> cq.Workplane:
    return (
        cq.Workplane("YZ", origin=(x_start, 0.0, 0.0))
        .moveTo(30.0, 0.0)
        .lineTo(190.0, 0.0)
        .lineTo(190.0, 110.0)
        .lineTo(30.0, 110.0)
        .threePointArc((8.7867966, 101.2132034), (0.0, 80.0))
        .lineTo(0.0, 30.0)
        .threePointArc((8.7867966, 8.7867966), (30.0, 0.0))
        .close()
        .extrude(35.0)
    )


arms = fork_arm(0.0).union(fork_arm(125.0))
transition = (
    cq.Workplane("XY")
    .moveTo(0.0, 190.0)
    .lineTo(160.0, 190.0)
    .lineTo(160.0, 205.0)
    .lineTo(130.0, 235.0)
    .lineTo(30.0, 235.0)
    .lineTo(0.0, 205.0)
    .close()
    .extrude(110.0)
)
hub = (
    cq.Workplane("XZ", origin=(80.0, 265.0, 55.0))
    .circle(47.5)
    .extrude(30.0)
)

body = arms.union(transition).union(hub)
left_pin_bore = (
    cq.Workplane("YZ", origin=(-1.0, 0.0, 0.0))
    .center(60.0, 55.0)
    .circle(29.5)
    .extrude(37.0)
)
right_pin_bore = (
    cq.Workplane("YZ", origin=(124.0, 0.0, 0.0))
    .center(60.0, 55.0)
    .circle(25.0)
    .extrude(37.0)
)
top_eye = (
    cq.Workplane("XZ", origin=(80.0, 266.0, 55.0))
    .circle(22.5)
    .extrude(77.0)
)
radial_ports = (
    cq.Workplane("XY", origin=(0.0, 0.0, -1.0))
    .pushPoints([(17.5, 60.0), (142.5, 60.0)])
    .circle(2.5)
    .extrude(33.0)
)

solid = (
    body.cut(left_pin_bore).cut(right_pin_bore).cut(top_eye).cut(radial_ports)
)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[1, 0, 0, -79.99999995], [0, 1, 0, -132.5], [0, 0, 1, -54.999999949999996], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [1, 0, 0], 0.0).translate([-79.99999995, -132.5, -54.999999949999996])
