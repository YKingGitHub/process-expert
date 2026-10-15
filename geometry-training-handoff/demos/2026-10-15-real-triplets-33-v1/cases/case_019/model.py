"""Stepped nylon grease-seal cap, 105 mm flange and 85 mm locating boss."""

import cadquery as cq


boss = cq.Workplane("XY").circle(42.5).extrude(5.0)
boss = boss.edges("<Z").chamfer(1.0)
flange = cq.Workplane("XY", origin=(0.0, 0.0, 5.0)).circle(52.5).extrude(5.0)
solid = boss.union(flange)
