"""Editable GT-assisted reconstruction of the 40602-3 cylinder frame.

The dimensions below are millimetres.  The source drawing is dimensioned in
inches, while the supplied STEP uses millimetres.  No STEP/BREP is imported by
this program; every feature is an editable CadQuery primitive or boolean.
"""

import math

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


def beam_yz(y0, z0, y1, z1, x_width, section_depth):
    """Rectangular forged rail joining two points in the YZ elevation."""
    dy, dz = y1 - y0, z1 - z0
    length = math.hypot(dy, dz)
    angle = math.degrees(math.atan2(dz, dy))
    return (
        cq.Workplane("XY")
        .box(x_width, length, section_depth)
        .rotate((0, 0, 0), (1, 0, 0), angle)
        .translate((3.4, (y0 + y1) / 2.0, (z0 + z1) / 2.0))
    )


def fuse(parts):
    result = parts[0]
    for part in parts[1:]:
        result = result.union(part, clean=False)
    return result.clean()


# Reference datum: dominant cylinder axis is Z.  The two transverse pivots set
# the full X span; their Y positions retain the measured reference extents.
parts = [
    # Main long pressure member and machined end collars.
    tube(38.119, 25.400, 669.235833, (3.4, 0.0, -634.408533), (0, 0, 1)),
    tube(41.288, 25.400, 62.0, (3.4, 0.0, -634.408533), (0, 0, 1)),
    tube(51.943, 25.400, 42.0, (3.4, 0.0, -7.1727), (0, 0, 1)),
    # Full-depth pivot bosses at the frame corners.
    tube(25.400, 12.700, 106.36852, (-49.78402, 307.17571, -93.0), (1, 0, 0)),
    tube(25.400, 12.700, 106.36852, (-49.78402, -110.452676, -568.0), (1, 0, 0)),
    # Primary triangular forged load path.
    beam_yz(-102.0, -568.0, 297.0, -93.0, 31.0, 34.0),
    beam_yz(297.0, -93.0, 5.0, -38.0, 34.0, 38.0),
    beam_yz(-102.0, -568.0, 2.0, -50.0, 34.0, 40.0),
    # Inner reinforcing rails visible in the side elevation.
    beam_yz(-67.0, -500.0, 222.0, -132.0, 19.0, 23.0),
    beam_yz(222.0, -132.0, 30.0, -95.0, 20.0, 25.0),
    # Local pads joining the rails to the tube.
    cq.Workplane("XY").box(66.0, 82.0, 55.0).translate((3.4, 37.0, -88.0)),
    cq.Workplane("XY").box(62.0, 78.0, 54.0).translate((3.4, -70.0, -530.0)),
]

solid = fuse(parts)

# Four explicit lightening holes through the broad triangular frame web.
for y_center, z_center, radius in (
    (64.0, -430.0, 10.0),
    (115.0, -350.0, 8.0),
    (168.0, -265.0, 7.0),
    (225.0, -180.0, 6.0),
):
    solid = solid.cut(
        cylinder(radius, 120.0, (-60.0, y_center, z_center), (1, 0, 0))
    )


if __name__ == "__main__":
    cq.exporters.export(solid, "reconstructed.step")
