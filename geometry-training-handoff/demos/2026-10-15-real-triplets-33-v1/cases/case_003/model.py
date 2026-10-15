"""Editable GT-assisted reconstruction of drawing 40605-11.

All dimensions are millimetres.  The original STEP was inspected only while
authoring this file; the program deliberately has no dependency on it.
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
    if bore_radius <= 0:
        return outer
    unit = cq.Vector(*direction).normalized()
    bore_start = cq.Vector(*start) - unit
    bore = cylinder(
        bore_radius,
        length + 2.0,
        (bore_start.x, bore_start.y, bore_start.z),
        direction,
    )
    return outer.cut(bore)


def beam_x(x0, x1, width_y, height_z, y=0.0, z=0.0):
    return (
        cq.Workplane("XY")
        .box(x1 - x0, width_y, height_z)
        .translate(((x0 + x1) / 2.0, y, z))
    )


def fuse(parts):
    result = parts[0]
    for part in parts[1:]:
        result = result.union(part, clean=False)
    return result.clean()


# The reference coordinate system is preserved: the long piston axis is X and
# the transverse end tube runs almost along -Y.  Values were measured from the
# supplied STEP and cross-checked against the inch drawing (38.040 in overall).
parts = [
    # Long hollow piston body and its machined end steps.
    tube(34.801, 25.819, 616.216, (-966.216, 0.0, 0.0), (1, 0, 0)),
    tube(32.77, 24.384, 72.0, (-966.216, 0.0, 0.0), (1, 0, 0)),
    tube(38.10, 25.819, 25.4, (-941.0, 0.0, 0.0), (1, 0, 0)),
    tube(37.60, 25.819, 34.0, (-382.0, 0.0, 0.0), (1, 0, 0)),
    # Shoulder and fork/strap portion between the piston and cross tube.
    cylinder(43.0, 46.0, (-350.0, 0.0, 0.0), (1, 0, 0)),
    beam_x(-326.0, -34.0, 39.0, 31.0, z=17.0),
    beam_x(-326.0, -34.0, 39.0, 31.0, z=-17.0),
    beam_x(-315.0, -15.0, 26.0, 30.0),
    cylinder(42.0, 44.0, (-350.0, 0.0, 0.0), (1, 0, 0)),
    # Four small flange ears around the shoulder.
    cylinder(12.357, 64.0, (-248.0, -32.0, 50.0), (0, 1, 0)),
    cylinder(12.357, 64.0, (-248.0, -32.0, -50.0), (0, 1, 0)),
    # Transverse hollow end tube and two turned collars.
    tube(25.819, 19.164, 245.691, (13.583, -196.289, 0.0), (0, 1, 0)),
    tube(26.975, 19.164, 23.0, (13.583, -196.289, 0.0), (0, 1, 0)),
    tube(26.975, 19.164, 30.0, (13.583, 19.403, 0.0), (0, 1, 0)),
    # Web tying the cross tube to the longitudinal straps.
    cq.Workplane("XY").box(80.0, 58.0, 46.0).translate((-24.0, 0.0, 0.0)),
    # Web-to-ear bridges make the reconstructed part one connected solid.
    cq.Workplane("XY").box(26.0, 34.0, 14.0).translate((-248.0, 0.0, 34.5)),
    cq.Workplane("XY").box(26.0, 34.0, 14.0).translate((-248.0, 0.0, -34.5)),
]

solid = fuse(parts)

# Through apertures in the two shoulder ears; these remain explicit editable
# cuts even though the small forged blends from the production part are omitted.
for z_center in (-50.0, 50.0):
    solid = solid.cut(
        cylinder(5.0, 70.0, (-248.0, -35.0, z_center), (0, 1, 0))
    )


if __name__ == "__main__":
    cq.exporters.export(solid, "reconstructed.step")
