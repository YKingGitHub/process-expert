"""Limit nylon wheel with rounded tread and symmetric stepped bore."""

import cadquery as cq


outer = cq.Workplane("XY").circle(80.0).extrude(97.0)
outer = outer.edges("%Circle").fillet(5.0)

through_bore = (
    cq.Workplane("XY", origin=(0.0, 0.0, -1.0)).circle(31.0).extrude(99.0)
)
left_counterbore = (
    cq.Workplane("XY", origin=(0.0, 0.0, -1.0)).circle(36.0).extrude(23.0)
)
right_counterbore = (
    cq.Workplane("XY", origin=(0.0, 0.0, 75.0)).circle(36.0).extrude(23.0)
)
left_retainer_recess = (
    cq.Workplane("XY", origin=(0.0, 0.0, 2.3)).circle(37.5).extrude(2.7)
)
right_retainer_recess = (
    cq.Workplane("XY", origin=(0.0, 0.0, 92.0)).circle(37.5).extrude(2.7)
)

solid = (
    outer
    .cut(through_bore)
    .cut(left_counterbore)
    .cut(right_counterbore)
    .cut(left_retainer_recess)
    .cut(right_retainer_recess)
)

# Training-coordinate calibration: proper rigid transform, millimetres retained.
RAW_TO_CANONICAL = [[1, 0, 0, -0.0], [0, 1, 0, -0.0], [0, 0, 1, -48.5], [0, 0, 0, 1]]
_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid
solid = _raw_shape.rotate((0, 0, 0), [1, 0, 0], 0.0).translate([-0.0, -0.0, -48.5])
