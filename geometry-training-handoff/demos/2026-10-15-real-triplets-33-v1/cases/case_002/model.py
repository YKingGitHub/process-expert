"""Editable GT-assisted reconstruction of the 41602-3 cylinder housing.

All dimensions are millimetres and the original STEP coordinate frame is kept.
The reference STEP is not read or embedded at runtime.
"""

import cadquery as cq


def _shape(value):
    return cq.Workplane("XY").newObject([value])


def cylinder(radius, length, start, direction):
    return _shape(
        cq.Solid.makeCylinder(
            radius, length, cq.Vector(*start), cq.Vector(*direction)
        )
    )


def tube(radius, bore_radius, length, start, direction):
    outer = cylinder(radius, length, start, direction)
    unit = cq.Vector(*direction).normalized()
    bore_start = cq.Vector(*start) - unit
    bore = cylinder(
        bore_radius,
        length + 2.0,
        (bore_start.x, bore_start.y, bore_start.z),
        direction,
    )
    return outer.cut(bore)


def fuse(parts):
    result = parts[0]
    for part in parts[1:]:
        result = result.union(part, clean=False)
    return result.clean()


# Reference datum: cylinder axis X, 21.970 in overall.  The paired transverse
# lugs account for the full 9.450 in Y span in the production drawing.
parts = [
    tube(41.224, 29.0, 558.038221, (-500.38022, 0.0, 0.0), (1, 0, 0)),
    tube(53.975, 31.0, 48.0, (-500.38022, 0.0, 0.0), (1, 0, 0)),
    tube(54.007, 29.0, 42.0, (15.658001, 0.0, 0.0), (1, 0, 0)),
    tube(45.968, 29.0, 36.0, (-35.0, 0.0, 0.0), (1, 0, 0)),
    # Broad cast ribs along the upper and lower sides of the barrel.
    cq.Workplane("XY").box(330.0, 23.0, 20.0).translate((-255.0, 46.0, 20.0)),
    cq.Workplane("XY").box(330.0, 23.0, 20.0).translate((-255.0, -46.0, 20.0)),
    cq.Workplane("XY").box(255.0, 30.0, 24.0).translate((-205.0, 0.0, -48.0)),
    # Full-span lower trunnion.  Outer and bore radii come from cylindrical
    # faces measured in the STEP.
    tube(27.686, 12.706, 240.030002, (-255.0, -120.015001, -78.486), (0, 1, 0)),
    cq.Workplane("XY").box(74.0, 62.0, 54.0).translate((-255.0, 0.0, -62.0)),
    # Upper mounting eye fixes the maximum Z extent.
    tube(27.686, 12.706, 82.0, (-430.0, -41.0, 41.022), (0, 1, 0)),
    cq.Workplane("XY").box(68.0, 64.0, 49.0).translate((-430.0, 0.0, 34.0)),
    # Smaller service bosses and their support pads.
    tube(19.05, 8.0, 66.0, (-92.0, -33.0, 34.0), (0, 1, 0)),
    cq.Workplane("XY").box(54.0, 54.0, 42.0).translate((-92.0, 0.0, 24.0)),
    tube(17.0, 7.0, 62.0, (-365.0, -31.0, -40.0), (0, 1, 0)),
]

solid = fuse(parts)

# Shallow relief pockets retain the editable cast-housing intent without trying
# to counterfeit the original free-form fillets.
for x_center in (-330.0, -180.0):
    pocket = (
        cq.Workplane("XY")
        .box(82.0, 130.0, 22.0)
        .translate((x_center, 0.0, -3.0))
    )
    solid = solid.cut(pocket)


if __name__ == "__main__":
    cq.exporters.export(solid, "reconstructed.step")
