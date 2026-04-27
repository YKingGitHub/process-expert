"""Thin Agent-style knowledge need planner for a real drawing sample."""

from __future__ import annotations


def plan_knowledge_needs(drawing: dict, constraints: dict) -> list[dict]:
    needs = [
        need(
            "KN-DATUM-001",
            "principle_query",
            "principle",
            "基准 B、C 相关表面应如何先加工并作为后续定位和检验基准？",
            "图纸含基准 B/C 和位置度要求，工艺路线需要先考虑基准加工。",
            ["datum", "route_planning"],
            required=True,
        ),
        need(
            "KN-GTOL-POSITION-001",
            "unknown_query",
            "candidate",
            "图纸中的位置度 φ0.1 B C 应如何解释、加工保证和检验？",
            "当前知识库可能需要 GD&T/检验类知识，不能用普通尺寸查询替代。",
            ["geometric_tolerance", "inspection"],
            required=True,
            candidate_type="inspection_records",
        ),
        need(
            "KN-GENERAL-TOL-001",
            "unknown_query",
            "candidate",
            "未注公差按 GB/T1804-m 执行时，普通尺寸公差如何查询？",
            "图纸技术要求明确 GB/T1804-m，知识库需要标准条款或参数表。",
            ["standard_clause", "lookup"],
            required=True,
            candidate_type="standard_clause_records",
        ),
        need(
            "KN-RA-001",
            "lookup_query",
            "lookup",
            "精车外圆通常能达到的 Ra 范围是多少？",
            "图纸和对照工艺卡均有 Ra3.2 表面粗糙度要求。",
            ["surface_roughness", "turning"],
            required=True,
        ),
        need(
            "KN-BLANK-ALLOWANCE-001",
            "mixed_query",
            "mixed",
            "毛坯 φ103.5 加工到外圆 φ103 时，车削余量和装夹方案需要哪些知识？",
            "毛坯和外圆尺寸接近，需要判断车削余量、夹持和保护外圆。",
            ["blank", "allowance", "turning"],
            required=True,
            candidate_type="machining_allowance_records",
        ),
        need(
            "KN-EQUIPMENT-001",
            "lookup_query",
            "lookup",
            "数控车床、三轴加工中心、车床分别适合本零件哪些工序？",
            "设备约束来自随图输入，规划需要匹配车、铣、钻/沉孔等工序。",
            ["equipment", "operation_selection"],
            required=True,
            candidate_type="equipment_capability_records",
        ),
        need(
            "KN-WIRECUT-001",
            "unknown_query",
            "candidate",
            "该零件是否需要线切割开料或切断工序，线切割工序如何安排？",
            "参考工艺卡存在线切割，当前知识库未覆盖线切割路线原则。",
            ["wire_cut", "route_planning"],
            required=False,
            candidate_type="wire_cut_process_records",
        ),
        need(
            "KN-MILL-D-SHAPE-001",
            "unknown_query",
            "candidate",
            "D 型孔、2-R4 和位置度要求应如何安排铣削及检验？",
            "图纸含 D 型内轮廓、R4 和位置度，当前知识库需要铣削/检验知识。",
            ["milling", "inspection"],
            required=True,
            candidate_type="milling_process_records",
        ),
        need(
            "KN-CASE-SLEEVE-001",
            "case_query",
            "case",
            "有没有套类或盘套类零件工艺过程卡案例可作为路线组织参考？",
            "案例只用于路线组织参考，不能直接照抄。",
            ["case", "reference_boundary"],
            required=False,
        ),
    ]
    return needs


def route_family_hypothesis(drawing: dict, constraints: dict) -> list[str]:
    families = ["领料", "车", "线切割", "车", "铣", "钳", "检验", "入库"]
    equipment = set(constraints.get("equipment", []))
    if "三轴加工中心" not in equipment:
        families.remove("铣")
    return families


def need(
    need_id: str,
    intent: str,
    expected_knowledge_type: str,
    question: str,
    reason: str,
    tags: list[str],
    required: bool,
    candidate_type: str | None = None,
) -> dict:
    return {
        "id": need_id,
        "expected_intent": intent,
        "expected_knowledge_type": expected_knowledge_type,
        "question": question,
        "reason": reason,
        "tags": tags,
        "required": required,
        "candidate_type": candidate_type,
    }
