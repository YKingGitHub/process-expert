"""Editable GT-assisted reconstruction of rough-machined part 40605-13.

All dimensions are millimetres.  No reference geometry is loaded at runtime.
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


# Same datum orientation as the reference STEP.  This rough-machined variant
# intentionally retains more stock than case_003 at the piston, shoulder and
# transverse end tube.
parts = [
    tube(35.128, 25.464, 616.216, (-966.216, 0.0, 0.0), (1, 0, 0)),
    tube(33.02, 24.384, 72.0, (-966.216, 0.0, 0.0), (1, 0, 0)),
    tube(38.35, 25.464, 27.0, (-941.0, 0.0, 0.0), (1, 0, 0)),
    tube(38.0, 25.464, 36.0, (-384.0, 0.0, 0.0), (1, 0, 0)),
    cylinder(44.0, 49.0, (-352.0, 0.0, 0.0), (1, 0, 0)),
    beam_x(-326.0, -35.0, 41.0, 33.0, z=18.0),
    beam_x(-326.0, -35.0, 41.0, 33.0, z=-18.0),
    beam_x(-315.0, -15.0, 28.0, 33.0),
    cylinder(43.0, 46.0, (-352.0, 0.0, 0.0), (1, 0, 0)),
    cylinder(12.357, 66.0, (-249.0, -33.0, 50.0), (0, 1, 0)),
    cylinder(12.357, 66.0, (-249.0, -33.0, -50.0), (0, 1, 0)),
    tube(26.15, 19.05, 247.051, (13.253, -197.649, 0.0), (0, 1, 0)),
    tube(27.305, 19.05, 25.0, (13.253, -197.649, 0.0), (0, 1, 0)),
    tube(27.305, 19.05, 31.0, (13.253, 18.403, 0.0), (0, 1, 0)),
    cq.Workplane("XY").box(82.0, 60.0, 48.0).translate((-25.0, 0.0, 0.0)),
    # Web-to-ear bridges make the reconstructed part one connected solid.
    cq.Workplane("XY").box(27.0, 36.0, 14.0).translate((-249.0, 0.0, 34.5)),
    cq.Workplane("XY").box(27.0, 36.0, 14.0).translate((-249.0, 0.0, -34.5)),
]

solid = fuse(parts)

for z_center in (-50.0, 50.0):
    solid = solid.cut(
        cylinder(4.8, 72.0, (-249.0, -36.0, z_center), (0, 1, 0))
    )


if __name__ == "__main__":
    cq.exporters.export(solid, "reconstructed.step")
