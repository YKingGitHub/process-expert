"""
CAD JSON Parser — 从 CAD 模型导出的 JSON 提取精确几何特征

支持格式: Fusion 360 / 类似 B-Rep 导出格式，包含:
- Sketch (草图) + profiles (轮廓曲线)
- ExtrudeFeature (拉伸)
- FilletFeature (圆角)
- manufacturing_info (加工信息/公差)
- bounding_box (包围盒)

所有数值从米(m)转换为毫米(mm)。
"""

import json
from pathlib import Path


def _m_to_mm(value: float) -> float:
    """Convert meters to millimeters, rounded to 3 decimal places."""
    return round(value * 1000, 3)


def _extract_dimensions_from_entity(entity: dict) -> dict | None:
    """Extract dimensional info from a single CAD entity."""
    etype = entity.get("type", "")
    name = entity.get("name", "")

    if etype == "ExtrudeFeature":
        distance = 0.0
        ext_one = entity.get("extent_one", {})
        if ext_one:
            dist_obj = ext_one.get("distance", {})
            distance = abs(dist_obj.get("value", 0.0))

        operation = entity.get("operation", "")
        return {
            "name": name,
            "type": "拉伸" if "NewBody" in operation else "切除",
            "distance_mm": _m_to_mm(distance),
            "operation": operation,
        }

    elif etype == "FilletFeature":
        radius_obj = entity.get("radius", {})
        radius = radius_obj.get("value", 0.0) if isinstance(radius_obj, dict) else 0.0
        return {
            "name": name,
            "type": "圆角",
            "radius_mm": _m_to_mm(radius),
        }

    return None


def _extract_profiles(entity: dict) -> list[dict]:
    """Extract profile curves with manufacturing info from a Sketch entity."""
    results = []
    profiles = entity.get("profiles", {})

    for profile_id, profile_data in profiles.items():
        loops = profile_data.get("loops", [])
        for loop in loops:
            is_outer = loop.get("is_outer", False)
            for curve in loop.get("profile_curves", []):
                curve_type = curve.get("type", "")
                mfg_info = curve.get("manufacturing_info", {})

                info = {
                    "profile_id": profile_id,
                    "curve_type": curve_type,
                    "is_outer": is_outer,
                }

                if curve_type == "Circle3D":
                    radius = curve.get("radius", 0)
                    info["diameter_mm"] = _m_to_mm(radius * 2)
                    info["description"] = f"Φ{info['diameter_mm']}"

                elif curve_type == "Arc3D":
                    radius = curve.get("radius", 0)
                    info["diameter_mm"] = _m_to_mm(radius * 2)
                    info["description"] = f"Φ{info['diameter_mm']} (弧)"

                elif curve_type == "Line3D":
                    sp = curve.get("start_point", {})
                    ep = curve.get("end_point", {})
                    dx = ep.get("x", 0) - sp.get("x", 0)
                    dy = ep.get("y", 0) - sp.get("y", 0)
                    dz = ep.get("z", 0) - sp.get("z", 0)
                    length = (dx**2 + dy**2 + dz**2) ** 0.5
                    info["length_mm"] = _m_to_mm(length)
                    info["description"] = f"线段 L={info['length_mm']}mm"

                if mfg_info:
                    info["tolerance_description"] = mfg_info.get("description", "")
                    info["tolerance_grade"] = mfg_info.get("tolerance_grade", "")
                    if "tolerance_value_mm" in mfg_info:
                        info["tolerance_value"] = mfg_info["tolerance_value_mm"]

                results.append(info)

    return results


def parse_cad_json(json_path: str) -> dict:
    """
    Parse a CAD model JSON file and extract structured manufacturing features.

    Returns:
        dict with keys:
            main_dimensions: dict of key dimensions (mm)
            features: list of geometric features
            tolerances: list of tolerance specifications
            manufacturing_sequence: ordered list of manufacturing operations
            bounding_box: overall dimensions
    """
    path = Path(json_path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entities = data.get("entities", {})
    properties = data.get("properties", {})
    sequence = data.get("sequence", [])

    # --- Bounding box → overall dimensions ---
    bbox = properties.get("bounding_box", {})
    bounding_box = {}
    if bbox:
        min_pt = bbox.get("min_point", {})
        max_pt = bbox.get("max_point", {})
        dx = _m_to_mm(max_pt.get("x", 0) - min_pt.get("x", 0))
        dy = _m_to_mm(max_pt.get("y", 0) - min_pt.get("y", 0))
        dz = _m_to_mm(max_pt.get("z", 0) - min_pt.get("z", 0))
        bounding_box = {
            "x_mm": dx,
            "y_mm": dy,
            "z_mm": dz,
            "overall": f"{max(dx, dy):.1f} × {min(dx, dy):.1f} × {dz:.1f} mm",
        }

    # --- Extract features from each entity ---
    all_profiles = []
    all_dimensions = []
    tolerances = []
    main_dims = {}

    for entity_id, entity in entities.items():
        etype = entity.get("type", "")

        if etype == "Sketch":
            profiles = _extract_profiles(entity)
            all_profiles.extend(profiles)

            # Collect tolerances
            for p in profiles:
                if p.get("tolerance_description"):
                    tolerances.append({
                        "description": p["tolerance_description"],
                        "grade": p.get("tolerance_grade", ""),
                        "value": p.get("tolerance_value", ""),
                        "dimension": p.get("description", ""),
                    })

                # Collect key dimensions
                if p.get("diameter_mm"):
                    key = f"Φ{p['diameter_mm']}"
                    main_dims[key] = {
                        "value_mm": p["diameter_mm"],
                        "type": "diameter",
                        "tolerance": p.get("tolerance_value", ""),
                    }
                elif p.get("length_mm") and p["length_mm"] > 0.1:
                    key = f"L{p['length_mm']}"
                    main_dims[key] = {
                        "value_mm": p["length_mm"],
                        "type": "length",
                    }

        else:
            dim_info = _extract_dimensions_from_entity(entity)
            if dim_info:
                all_dimensions.append(dim_info)
                if dim_info.get("distance_mm") and dim_info["distance_mm"] > 0:
                    key = f"{dim_info['name']}_{dim_info['distance_mm']}mm"
                    main_dims[key] = {
                        "value_mm": dim_info["distance_mm"],
                        "type": dim_info["type"],
                    }

    # --- Manufacturing sequence ---
    mfg_sequence = []
    for step in sequence:
        entity_id = step.get("entity", "")
        entity = entities.get(entity_id, {})
        etype = step.get("type", "")
        name = entity.get("name", etype)

        dim = _extract_dimensions_from_entity(entity)
        seq_entry = {
            "index": step.get("index", 0),
            "operation": etype,
            "name": name,
        }
        if dim:
            seq_entry["detail"] = dim
        mfg_sequence.append(seq_entry)

    # --- Build structured features list ---
    features = []
    seen_diameters = set()
    for p in all_profiles:
        desc = p.get("description", "")
        if p.get("diameter_mm"):
            d = p["diameter_mm"]
            if d not in seen_diameters:
                seen_diameters.add(d)
                feature = {
                    "name": f"Φ{d} {'外圆' if p.get('is_outer') and d > 50 else '孔/槽'}",
                    "specification": desc,
                    "precise_mm": d,
                }
                if p.get("tolerance_value"):
                    feature["tolerance"] = p["tolerance_value"]
                features.append(feature)

    for dim in all_dimensions:
        features.append({
            "name": dim["name"],
            "specification": f"{dim['type']} {dim.get('distance_mm', dim.get('radius_mm', ''))}mm",
        })

    return {
        "main_dimensions": main_dims,
        "features": features,
        "tolerances": tolerances,
        "manufacturing_sequence": mfg_sequence,
        "bounding_box": bounding_box,
    }
