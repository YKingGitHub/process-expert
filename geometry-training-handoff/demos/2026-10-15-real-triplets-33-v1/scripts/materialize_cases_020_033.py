#!/usr/bin/env python3
"""Materialize editable CadQuery reconstructions for cases 020 through 033."""

from __future__ import annotations

import json
import math
from pathlib import Path
import runpy
import shutil
import textwrap

import cadquery as cq


ROOT = Path(__file__).resolve().parents[1]
CASES_ROOT = Path(
    "/hpc2hdd/home/lwang592/projects/.cache/process-expert/"
    "drawing_20260810_single/cases"
)


MODELS: dict[str, str] = {}
NOTES: dict[str, dict[str, object]] = {}


def register(
    case_id: str,
    source: str,
    *,
    part_name: str,
    fidelity: str,
    method: str,
    gt_assistance: list[str],
    approximations: list[str],
    omissions: list[str],
) -> None:
    cleaned_source = textwrap.dedent(source).lstrip()
    cleaned_source = cleaned_source.replace(
        "\n    def toothed_plate(", "\ndef toothed_plate("
    )
    MODELS[case_id] = cleaned_source
    NOTES[case_id] = {
        "part_name": part_name,
        "fidelity": fidelity,
        "method": method,
        "ground_truth_assistance": gt_assistance,
        "approximations": approximations,
        "omitted_features": omissions,
    }


register(
    "case_020",
    '''
    import cadquery as cq
    import math

    outer_radius = 98.0
    length = 141.0
    solid = cq.Workplane("XY").circle(outer_radius).extrude(length)

    # Stepped axial passage and forty-tooth internal gear region.
    solid = solid.cut(cq.Workplane("XY").circle(42.5).extrude(length))
    solid = solid.cut(cq.Workplane("XY").circle(57.0).extrude(53.0))
    tooth_spaces = None
    for index in range(40):
        angle = 2.0 * math.pi * index / 40.0
        half = math.pi / 40.0 * 0.42
        points = [
            (57.0 * math.cos(angle - half), 57.0 * math.sin(angle - half)),
            (63.75 * math.cos(angle - half * 0.50), 63.75 * math.sin(angle - half * 0.50)),
            (63.75 * math.cos(angle + half * 0.50), 63.75 * math.sin(angle + half * 0.50)),
            (57.0 * math.cos(angle + half), 57.0 * math.sin(angle + half)),
        ]
        cutter = cq.Workplane("XY").polyline(points).close().extrude(45.0)
        tooth_spaces = cutter if tooth_spaces is None else tooth_spaces.union(cutter)
    solid = solid.cut(tooth_spaces)
    solid = solid.cut(
        cq.Workplane("XY").workplane(offset=61.0).circle(65.0).extrude(70.0)
    )
    solid = solid.cut(
        cq.Workplane("XY").workplane(offset=131.0).circle(70.0).extrude(10.0)
    )

    # Eight blind M8 tapping-drill holes on the 155 mm pitch circle.
    hole_points = []
    for index in range(8):
        angle = 2.0 * math.pi * index / 8.0 + math.pi / 8.0
        hole_points.append((77.5 * math.cos(angle), 77.5 * math.sin(angle)))
    solid = solid.cut(
        cq.Workplane("XY").pushPoints(hole_points).circle(3.4).extrude(22.0)
    )

    # Radial M12 port at the indicated z=53 level, simplified to its tap drill.
    radial = (
        cq.Workplane("XZ")
        .workplane(offset=-98.0)
        .center(0.0, 53.0)
        .circle(5.1)
        .extrude(196.0)
    )
    solid = solid.cut(radial)
    ''',
    part_name="STKJ-MT01-0046 内直齿轮套 M3 Z40",
    fidelity="approximate_feature_reconstruction",
    method="Parametric sleeve with stepped bores, 40-tooth internal profile, eight blind holes, and radial port.",
    gt_assistance=["STEP bbox 196 x 196 x 141 mm", "STEP radii and face-type audit", "drawing dimensions and tooth count"],
    approximations=["Internal involute teeth are editable four-point tooth spaces rather than exact involutes.", "Radial threaded port is represented by its tap-drill cylinder."],
    omissions=["Thread helices, heat-treatment detail, micro-chamfers, and production fillets."],
)


register(
    "case_021",
    '''
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
    ''',
    part_name="STKJ-MT01-0047 销",
    fidelity="dimensionally_faithful_simplification",
    method="Three coaxial turned diameters plus a blind hexagonal socket, rotated into the source STEP axis frame.",
    gt_assistance=["STEP bbox 76 x 200 x 76 mm", "STEP principal radii 38, 29.5, and 25 mm", "drawing axial dimensions"],
    approximations=["M50x1.5 threaded region is represented by the nominal 50 mm cylinder."],
    omissions=["Thread helix, C1.5 edge chamfers, and tiny relief grooves."],
)


register(
    "case_022",
    '''
    import cadquery as cq
    import math

    # Turned rail wheel: central barrel and the right-end running flange.
    barrel = cq.Workplane("XY").circle(53.0).extrude(100.0)
    right_flange = cq.Workplane("XY").workplane(offset=93.0).circle(75.0).extrude(22.0)
    solid = barrel.union(right_flange)

    solid = solid.cut(cq.Workplane("XY").circle(31.0).extrude(115.0))
    solid = solid.cut(cq.Workplane("XY").circle(36.0).extrude(22.0))
    solid = solid.cut(
        cq.Workplane("XY").workplane(offset=93.0).circle(37.5).extrude(22.0)
    )
    ''',
    part_name="STKJ-MT01-0048 轨道轮",
    fidelity="approximate_feature_reconstruction",
    method="Editable coaxial barrel/right-flange union with a stepped through-bore.",
    gt_assistance=["STEP bbox 150 x 150 x 115 mm", "STEP radii 75, 53, 37.5, 36, 31 mm", "drawing end-plane stations"],
    approximations=["The right running flange and barrel use nominal cylindrical stations; no unsupported left flange is added.", "Counterbore depths use the main drawing stations rather than reverse-engineering every imported seam."],
    omissions=["2.3/2.7 mm lip reliefs, C1 chamfers, and edge blends."],
)


register(
    "case_023",
    '''
    import cadquery as cq
    import math

    left_end = cq.Workplane("XY").circle(15.0).extrude(50.0)
    left_collar = cq.Workplane("XY").workplane(offset=50.0).circle(16.5).extrude(7.5)
    center = cq.Workplane("XY").workplane(offset=57.5).circle(17.5).extrude(105.0)
    right_collar = cq.Workplane("XY").workplane(offset=162.5).circle(16.5).extrude(7.5)
    right_end = cq.Workplane("XY").workplane(offset=170.0).circle(15.0).extrude(50.0)
    solid = left_end.union(left_collar).union(center).union(right_collar).union(right_end)

    # Two 1.6 mm-wide undercut reliefs at the shoulder transitions.
    left_relief = cq.Workplane("XY").workplane(offset=55.9).circle(17.6).circle(14.0).extrude(1.6)
    right_relief = cq.Workplane("XY").workplane(offset=162.5).circle(17.6).circle(14.0).extrude(1.6)
    solid = solid.cut(left_relief).cut(right_relief).translate((0.0, 0.0, -50.0))
    ''',
    part_name="STKJ-MT01-0049 轨道轮轴",
    fidelity="dimensionally_faithful_simplification",
    method="Turned five-station shaft profile with shoulder relief grooves in the source z frame.",
    gt_assistance=["STEP bbox 35 x 35 x 220 mm at z=-50..170", "STEP radii 17.5, 16.5, 15, 14 mm", "drawing lengths 220, 120, 105, 57.5, 49 mm"],
    approximations=["Axial shoulder placement is reconciled from the dimension chain; small CAD seam offsets are ignored."],
    omissions=["M30 thread helices and C1 end chamfers."],
)


register(
    "case_024",
    '''
    import cadquery as cq
    import math

    solid = cq.Workplane("XY").circle(40.0).circle(5.5).extrude(8.0)
    ''',
    part_name="STKJ-MT01-0050 链轮压板",
    fidelity="exact_nominal_reconstruction",
    method="Single annular extrusion from the drawing and STEP nominal dimensions.",
    gt_assistance=["STEP bbox 80 x 80 x 8 mm", "STEP radii 40 and 5.5 mm"],
    approximations=[],
    omissions=["Unspecified microscopic edge breaks."],
)


SPROCKET_HELPER = textwrap.indent(textwrap.dedent('''
def toothed_plate(teeth, root_radius, tip_radius, width, z0):
    points = []
    for index in range(teeth):
        center = 2.0 * math.pi * index / teeth
        half_pitch = math.pi / teeth
        for fraction, radius in (
            (-1.00, root_radius),
            (-0.58, root_radius),
            (-0.30, tip_radius),
            (0.30, tip_radius),
            (0.58, root_radius),
        ):
            angle = center + fraction * half_pitch
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return cq.Workplane("XY").workplane(offset=z0).polyline(points).close().extrude(width)
''').lstrip(), "    ")


register(
    "case_025",
    '''
    import cadquery as cq
    import math

    ''' + SPROCKET_HELPER + '''
    # 22-tooth, double-row 28A sprocket; axial source span is -8.065..81.935.
    left_teeth = toothed_plate(22, 132.5, 166.57977, 25.42, 0.0)
    right_teeth = toothed_plate(22, 132.5, 166.57977, 25.42, 64.58)
    web = cq.Workplane("XY").workplane(offset=10.0).circle(105.0).extrude(70.0)
    hub = cq.Workplane("XY").circle(72.5).extrude(90.0)
    solid = left_teeth.union(right_teeth).union(web).union(hub)

    solid = solid.cut(cq.Workplane("XY").circle(65.0).extrude(90.0))
    solid = solid.cut(cq.Workplane("XY").circle(72.5).extrude(10.0))
    solid = solid.cut(
        cq.Workplane("XY").workplane(offset=70.0).circle(72.5).extrude(20.0)
    )
    solid = solid.rotate((0, 0, 0), (0, 1, 0), 90).translate((-8.065, 0, 0))
    ''',
    part_name="STKJ-MT01-0053 双排链轮 28A 齿数22",
    fidelity="approximate_feature_reconstruction",
    method="Two parametric 22-tooth plates, web and hub, stepped 130/145 mm bore, placed in the STEP x-axis frame.",
    gt_assistance=["STEP bbox 90 x 333.15954 x 330.56943 mm", "STEP axial/radial audit", "drawing tooth count, OD, web, bore, and row widths"],
    approximations=["Roller-chain tooth flanks and root arcs are represented by editable trapezoidal radial teeth.", "Axial web transitions are simplified to cylinders."],
    omissions=["R166.58 involute-equivalent arcs, toroidal tooth fillets, 0.5 mm chamfers, and small edge breaks."],
)


register(
    "case_026",
    '''
    import cadquery as cq
    import math

    ''' + SPROCKET_HELPER + '''
    left_teeth = toothed_plate(17, 69.0, 93.246405, 17.58, 0.0)
    right_teeth = toothed_plate(17, 69.0, 93.246405, 17.58, 57.18)
    body = cq.Workplane("XY").circle(69.0).extrude(74.76)
    solid = body.union(left_teeth).union(right_teeth)
    solid = solid.cut(cq.Workplane("XY").circle(30.0).extrude(74.76))

    # 18 mm keyway extending radially from the 60 mm nominal bore.
    keyway = (
        cq.Workplane("XY")
        .workplane(offset=0.0)
        .center(0.0, 34.5)
        .rect(18.0, 9.0)
        .extrude(74.76)
    )
    solid = solid.cut(keyway)
    solid = solid.rotate((0, 0, 0), (0, 1, 0), 90)
    ''',
    part_name="STKJ-MT01-0057 双排链轮 20A 齿数17",
    fidelity="approximate_feature_reconstruction",
    method="Double-row 17-tooth parametric sprocket with 138 mm body, 60 mm keyed bore, and drawing axial spacing.",
    gt_assistance=["STEP bbox 74.76 x 185.71464 x 186.49281 mm", "STEP body/bore radii", "drawing dimensions and chain parameters"],
    approximations=["Roller-chain tooth flanks, roots, and axial crowns are simplified to trapezoidal teeth.", "Keyway depth is inferred from the section and STEP envelope."],
    omissions=["Toroidal tooth blends, tolerance-only detail, and micro-chamfers."],
)


register(
    "case_027",
    '''
    import cadquery as cq
    import math

    ''' + SPROCKET_HELPER + '''
    teeth = toothed_plate(17, 69.0, 93.246405, 17.58, 0.7115)
    web = cq.Workplane("XY").circle(50.0).extrude(50.0)
    solid = web.union(teeth)
    solid = solid.cut(cq.Workplane("XY").circle(21.0).extrude(50.0))

    keyway = (
        cq.Workplane("XY")
        .center(0.0, 24.0)
        .rect(12.0, 6.0)
        .extrude(50.0)
    )
    solid = solid.cut(keyway)
    solid = solid.rotate((0, 0, 0), (0, 1, 0), 90)
    ''',
    part_name="STKJ-MT01-0058 单排链轮 20A 齿数17",
    fidelity="approximate_feature_reconstruction",
    method="Single-row 17-tooth plate with 100 mm hub, 42 mm keyed bore, and 50 mm total axial span.",
    gt_assistance=["STEP bbox 50 x 185.71464 x 186.49281 mm", "STEP radii and source orientation", "drawing tooth count and keyed-bore dimensions"],
    approximations=["Roller-chain tooth profile is a deterministic trapezoidal radial approximation.", "Small 0.7115 mm tooth-row offset is retained from STEP evidence."],
    omissions=["Exact roller-root arcs, toroidal blends, thread-free manufacturing edge breaks."],
)


register(
    "case_028",
    '''
    import cadquery as cq
    import math

    ''' + SPROCKET_HELPER + '''
    left_teeth = toothed_plate(15, 83.5, 116.221975, 23.45, 0.0)
    right_teeth = toothed_plate(15, 83.5, 116.221975, 22.0, 58.0)
    body = cq.Workplane("XY").circle(83.5).extrude(80.0)
    solid = body.union(left_teeth).union(right_teeth)
    solid = solid.cut(cq.Workplane("XY").circle(35.0).extrude(80.0))
    solid = solid.cut(cq.Workplane("XY").circle(40.0).extrude(23.45))
    solid = solid.cut(
        cq.Workplane("XY").workplane(offset=54.58).circle(41.75).extrude(25.42)
    )
    solid = solid.rotate((0, 0, 0), (0, 1, 0), 90).translate((-3.065, 0, 0))
    ''',
    part_name="STKJ-MT01-0059 双排链轮 28A 齿数15",
    fidelity="approximate_feature_reconstruction",
    method="Double-row 15-tooth parametric sprocket with 167 mm body and stepped 70/80/83.5 mm bore.",
    gt_assistance=["STEP bbox 80 x 231.21737 x 232.44395 mm", "STEP radii and x-frame bounds", "drawing tooth count, OD, bore, and axial chain"],
    approximations=["Roller-chain tooth and valley arcs are represented by polygonal editable teeth.", "Web and tooth transitions omit imported toroidal blends."],
    omissions=["R116.56 root construction arcs, tooth-end crowns, 0.5 mm chamfers, and small edge breaks."],
)


register(
    "case_029",
    '''
    import cadquery as cq
    import math

    center_x = -1.5
    center_y = 1741.23876
    solid = (
        cq.Workplane("XY")
        .center(center_x, center_y)
        .rect(85.0, 150.0)
        .extrude(15.0)
    )
    hole_points = [
        (-14.5, 1696.23876),
        (11.5, 1696.23876),
        (-14.5, 1786.23876),
        (11.5, 1786.23876),
    ]
    solid = solid.cut(
        cq.Workplane("XY").pushPoints(hole_points).circle(4.25).extrude(15.0)
    )
    ''',
    part_name="STKJ-MT01-0062 SK4040 安装板",
    fidelity="exact_nominal_reconstruction",
    method="85 x 150 x 15 mm rectangular plate with four 8.5 mm through-holes in the original STEP coordinates.",
    gt_assistance=["STEP exact bounds and hole centers", "STEP radius 4.25 mm", "drawing dimensions"],
    approximations=[],
    omissions=["Unspecified microscopic edge breaks."],
)


register(
    "case_030",
    '''
    import cadquery as cq
    import math

    base = cq.Workplane("XY").circle(77.5).extrude(15.5)
    raised_face = cq.Workplane(
        cq.Solid.makeCone(55.0, 53.0, 2.0, cq.Vector(0, 0, 15.5))
    )
    solid = base.union(raised_face)
    holes = [(62.5, 0.0), (-62.5, 0.0), (0.0, 62.5), (0.0, -62.5)]
    solid = solid.cut(
        cq.Workplane("XY").pushPoints(holes).circle(9.0).extrude(17.5)
    )
    ''',
    part_name="STKJ-MT01-0063 DN50 闷盖",
    fidelity="dimensionally_faithful_simplification",
    method="155 mm blind cover with 125 mm PCD holes and a 2 mm raised, C2-transitioned 106 mm center face.",
    gt_assistance=["STEP bbox 155 x 155 x 17.5 mm", "STEP four radius-9 holes at PCD 125", "drawing 15.5/17.5 mm axial profile"],
    approximations=["C2 transition is modeled as a 55-to-53 mm conical frustum."],
    omissions=["Unspecified outer edge breaks and surface-finish-only annotations."],
)


register(
    "case_031",
    '''
    import cadquery as cq
    import math

    base = cq.Workplane("XY").circle(77.5).extrude(15.5)
    raised_face = cq.Workplane(
        cq.Solid.makeCone(55.0, 53.0, 2.0, cq.Vector(0, 0, 15.5))
    )
    solid = base.union(raised_face)
    solid = solid.cut(cq.Workplane("XY").circle(29.5).extrude(17.5))
    holes = [(62.5, 0.0), (-62.5, 0.0), (0.0, 62.5), (0.0, -62.5)]
    solid = solid.cut(
        cq.Workplane("XY").pushPoints(holes).circle(9.0).extrude(17.5)
    )
    ''',
    part_name="STKJ-MT01-0064 DN50 法兰",
    fidelity="dimensionally_faithful_simplification",
    method="155 mm flange with 59 mm bore, four 18 mm PCD-125 holes, and 2 mm raised center face.",
    gt_assistance=["STEP bbox 155 x 155 x 17.5 mm", "STEP bore and hole radii/centers", "drawing axial profile"],
    approximations=["C2 transition is modeled as a 55-to-53 mm conical frustum."],
    omissions=["Unspecified outer edge breaks and surface-finish-only annotations."],
)


register(
    "case_032",
    '''
    import cadquery as cq
    import math

    solid = cq.Workplane("XY").circle(75.0).circle(30.0).extrude(3.0)
    hole_points = [(60.35, 0.0), (-60.35, 0.0), (0.0, 60.35), (0.0, -60.35)]
    solid = solid.cut(
        cq.Workplane("XY").pushPoints(hole_points).circle(9.5).extrude(3.0)
    )
    solid = solid.rotate((0, 0, 0), (1, 0, 0), -90)
    ''',
    part_name="STKJ-MT01-0065 石棉橡胶垫片平面型",
    fidelity="exact_nominal_reconstruction",
    method="150/60 x 3 mm annular gasket with four 19 mm holes on PCD 120.70, rotated into the STEP y-thickness frame.",
    gt_assistance=["STEP bbox 150 x 3 x 150 mm", "STEP hole centers at radius 60.35 mm", "drawing nominal dimensions"],
    approximations=[],
    omissions=["Material deformation and rasterized surface texture are not geometric features."],
)


register(
    "case_033",
    '''
    import cadquery as cq
    import math

    solid = cq.Workplane("XY").box(2370.0, 200.0, 20.0, centered=(False, False, False))
    x_positions = [110.0, 260.0, 410.0, 560.0, 960.0, 1110.0,
                   1260.0, 1410.0, 1810.0, 1960.0, 2110.0, 2260.0]
    hole_points = [(x, y) for x in x_positions for y in (50.0, 150.0)]
    solid = solid.cut(
        cq.Workplane("XY").pushPoints(hole_points).circle(4.5).extrude(20.0)
    )
    solid = solid.cut(
        cq.Workplane("XY").pushPoints(hole_points).circle(7.5).extrude(4.5)
    )
    solid = solid.cut(
        cq.Workplane("XY")
        .workplane(offset=15.5)
        .pushPoints(hole_points)
        .circle(7.5)
        .extrude(4.5)
    )
    ''',
    part_name="STKJ-MT01-0066 防划伤垫板",
    fidelity="exact_nominal_reconstruction",
    method="2370 x 200 x 20 mm plate with 24 through-holes and symmetric 15 mm counterbores in the original coordinate frame.",
    gt_assistance=["STEP exact bounds", "STEP 24 hole centers", "STEP cylinder areas confirming 4.5 mm counterbore depth per face", "drawing hole/counterbore diameters"],
    approximations=[],
    omissions=["Material properties and surface roughness are metadata, not B-rep geometry."],
)


def measure(shape: cq.Shape) -> dict[str, object]:
    box = shape.BoundingBox()
    return {
        "valid": bool(shape.isValid()),
        "solid_count": len(shape.Solids()),
        "volume_mm3": float(shape.Volume()),
        "surface_area_mm2": float(shape.Area()),
        "bbox_mm": [float(box.xlen), float(box.ylen), float(box.zlen)],
        "bbox_min_mm": [float(box.xmin), float(box.ymin), float(box.zmin)],
        "bbox_max_mm": [float(box.xmax), float(box.ymax), float(box.zmax)],
    }


def percent_error(predicted: float, reference: float) -> float:
    return (predicted - reference) / reference * 100.0


def materialize(case_id: str) -> None:
    destination = ROOT / "cases" / case_id
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / "model.py"
    model_path.write_text(MODELS[case_id], encoding="utf-8")

    source_reference = CASES_ROOT / case_id / "ground_truth" / "ground_truth.step"
    reference_path = destination / "reference.step"
    shutil.copyfile(source_reference, reference_path)

    namespace = runpy.run_path(str(model_path), run_name="__triplet_validation__")
    value = namespace["solid"]
    reconstructed_shape = value.val() if isinstance(value, cq.Workplane) else value
    if not isinstance(reconstructed_shape, cq.Shape):
        raise TypeError(f"{case_id}: global solid is not a CadQuery shape")
    reconstructed_path = destination / "reconstructed.step"
    cq.exporters.export(reconstructed_shape, str(reconstructed_path))

    reference_shape = cq.importers.importStep(str(reference_path)).val()
    reference_measurement = measure(reference_shape)
    reconstructed_measurement = measure(reconstructed_shape)
    bbox_errors = [
        percent_error(predicted, reference)
        for predicted, reference in zip(
            reconstructed_measurement["bbox_mm"], reference_measurement["bbox_mm"]
        )
    ]
    authoring = {
        "schema_version": 1,
        "case_id": case_id,
        **NOTES[case_id],
        "coordinate_policy": "Preserve the original STEP axis order, physical millimetres, and world-frame bounds; no normalization or rescaling.",
        "reference_measurement": reference_measurement,
        "reconstructed_measurement": reconstructed_measurement,
        "comparison": {
            "volume_deviation_percent": percent_error(
                reconstructed_measurement["volume_mm3"],
                reference_measurement["volume_mm3"],
            ),
            "surface_area_deviation_percent": percent_error(
                reconstructed_measurement["surface_area_mm2"],
                reference_measurement["surface_area_mm2"],
            ),
            "bbox_axis_deviation_percent": bbox_errors,
            "bbox_max_abs_deviation_percent": max(abs(value) for value in bbox_errors),
        },
        "validation": {
            "executor": "runpy.run_path(run_name='__triplet_validation__')",
            "cadquery_version": cq.__version__,
            "global_solid_present": True,
            "reconstructed_step_exported": True,
        },
    }
    (destination / "authoring.json").write_text(
        json.dumps(authoring, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    for case_id in sorted(MODELS):
        materialize(case_id)
        print(case_id, "materialized", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
