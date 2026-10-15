"""Editable GT-assisted reconstruction of forked cylinder part 41608-3.

Dimensions are millimetres.  The program builds the model from tubes, turned
bosses, rails and cuts; it never reads the supplied STEP/BREP.
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


def beam_3d(point_a, point_b, width_y, height_z):
    """Box rail aligned from point_a to point_b in two Euler rotations."""
    x0, y0, z0 = point_a
    x1, y1, z1 = point_b
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    horizontal = math.hypot(dx, dy)
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = -math.degrees(math.atan2(dz, horizontal))
    return (
        cq.Workplane("XY")
        .box(length, width_y, height_z)
        .rotate((0, 0, 0), (0, 1, 0), pitch)
        .rotate((0, 0, 0), (0, 0, 1), yaw)
        .translate(((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0))
    )


def fuse(parts):
    result = parts[0]
    for part in parts[1:]:
        result = result.union(part, clean=False)
    return result.clean()


parts = [
    # Long hollow barrel and turned left-end details.
    tube(28.477, 20.307, 489.0, (-509.651, 0.0, 0.0), (1, 0, 0)),
    tube(35.024, 20.307, 34.0, (-509.651, 0.0, 0.0), (1, 0, 0)),
    tube(31.5, 20.307, 32.0, (-477.0, 0.0, 0.0), (1, 0, 0)),
    tube(32.5, 20.307, 38.0, (-58.0, 0.0, 0.0), (1, 0, 0)),
    # Central fork root and horizontal pivot eye.
    cq.Workplane("XY").box(72.0, 88.0, 58.0).translate((-18.0, 0.0, 4.0)),
    tube(17.780, 8.0, 58.0, (-24.6, -29.0, 104.676), (0, 1, 0)),
    beam_3d((-18.0, 0.0, 25.0), (-24.6, 0.0, 92.0), 34.0, 20.0),
    # Two forged fork legs: short flare followed by the long nearly parallel run.
    beam_3d((-15.0, 24.0, 6.0), (72.0, 87.0, 12.0), 22.0, 19.0),
    beam_3d((72.0, 87.0, 12.0), (270.0, 101.0, 15.0), 20.0, 19.0),
    beam_3d((-15.0, -24.0, 6.0), (72.0, -87.0, 12.0), 22.0, 19.0),
    beam_3d((72.0, -87.0, 12.0), (270.0, -101.0, 15.0), 20.0, 19.0),
    # Terminal eyes.  Their Y lengths reproduce the measured full fork width.
    tube(15.939, 7.5, 33.329, (272.071, 85.0, 15.0), (0, 1, 0)),
    tube(15.939, 7.5, 33.329, (272.071, -118.329, 15.0), (0, 1, 0)),
    # Root gussets on both sides of the U.
    cq.Workplane("XY").box(90.0, 18.0, 36.0).translate((15.0, 50.0, 7.0)),
    cq.Workplane("XY").box(90.0, 18.0, 36.0).translate((15.0, -50.0, 7.0)),
]

solid = fuse(parts)


if __name__ == "__main__":
    cq.exporters.export(solid, "reconstructed.step")
