"""Double-ended clevis hinge with orthogonal-width fork stages."""

import cadquery as cq


def lower_ear(y_origin: float) -> cq.Workplane:
    return (
        cq.Workplane("XZ", origin=(0.0, y_origin, 0.0))
        .moveTo(-30.0, 95.0)
        .threePointArc((0.0, 65.0), (30.0, 95.0))
        .lineTo(30.0, 165.0)
        .lineTo(-30.0, 165.0)
        .close()
        .extrude(30.0)
    )


lower = lower_ear(60.0).union(lower_ear(-30.0))
lower_pin_hole = (
    cq.Workplane("XZ", origin=(0.0, 61.0, 0.0))
    .center(0.0, 100.0)
    .circle(12.5)
    .extrude(122.0)
)
lower = lower.cut(lower_pin_hole)

# Close the 60 mm lower slot at z=155, then transition in two chamfer stages.
lower_bridge = (
    cq.Workplane("XY", origin=(0.0, 0.0, 155.0))
    .box(60.0, 120.0, 10.0, centered=(True, True, False))
)
transition_lower = (
    cq.Workplane("XY", origin=(0.0, 0.0, 165.0))
    .rect(60.0, 120.0)
    .workplane(offset=5.0)
    .rect(60.0, 110.0)
    .loft(combine=True)
)
transition_upper = (
    cq.Workplane("XY", origin=(0.0, 0.0, 170.0))
    .rect(60.0, 110.0)
    .workplane(offset=15.0)
    .rect(30.0, 80.0)
    .loft(combine=True)
)
transition = transition_lower.union(transition_upper)


def upper_ear(y_origin: float) -> cq.Workplane:
    return (
        cq.Workplane("XZ", origin=(0.0, y_origin, 0.0))
        .moveTo(-15.0, 185.0)
        .lineTo(15.0, 185.0)
        .lineTo(15.0, 225.0)
        .threePointArc((0.0, 240.0), (-15.0, 225.0))
        .close()
        .extrude(27.0)
    )


upper = upper_ear(37.0).union(upper_ear(-10.0))
slot_floor = (
    cq.Workplane("XY", origin=(0.0, 0.0, 185.0))
    .box(30.0, 20.0, 15.0, centered=(True, True, False))
)
upper_pin_hole = (
    cq.Workplane("XZ", origin=(0.0, 38.0, 0.0))
    .center(0.0, 225.0)
    .circle(7.5)
    .extrude(76.0)
)
upper = upper.union(slot_floor).cut(upper_pin_hole)

solid = lower.union(lower_bridge).union(transition).union(upper)
