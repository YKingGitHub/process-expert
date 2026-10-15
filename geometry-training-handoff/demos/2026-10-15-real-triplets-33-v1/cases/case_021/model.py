import cadquery as cq
import math

flange = cq.Workplane("XY").circle(38.0).extrude(12.0)
shoulder = cq.Workplane("XY").workplane(offset=12.0).circle(29.5).extrude(46.0)
shank = cq.Workplane("XY").workplane(offset=58.0).circle(25.0).extrude(142.0)
solid = flange.union(shoulder).union(shank)

# 12 mm across-flats hexagonal socket, 12 mm deep from the flange end.
circumradius = 12.0 / math.sqrt(3.0)
hex_points = [
    (circumradius * math.cos(math.radians(60 * i + 30)),
     circumradius * math.sin(math.radians(60 * i + 30)))
    for i in range(6)
]
socket = cq.Workplane("XY").polyline(hex_points).close().extrude(12.0)
solid = solid.cut(socket)
solid = solid.rotate((0, 0, 0), (1, 0, 0), -90)
