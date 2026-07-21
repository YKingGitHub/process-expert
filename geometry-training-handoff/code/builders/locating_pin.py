#!/usr/bin/env python3
"""形状族建模器:阶梯回转销轴 + 侧面铣扁(stepped pin with milled flats)

适用族:定位销、支承销、导向柱、带球头/锥头的阶梯轴——即
"沿一根轴逐段变径 + 倒角/圆角 + 端部锥或球 + 可选侧面铣扁"这一族。

设计要点(针对实测失败模式):
  1) 旧 AI 重建把"每一段有多长"全靠感觉:总长 92 做成 54,细颈整段丢失。
     本模板把回转体定义成 **沿轴的 (x, r) 断点序列**,总长 = 序列最后一个 x,
     任何一段缺失都会立刻在总长上暴露出来,不可能"悄悄少一段"。
  2) 旧重建把 R 圆角/过渡用 BSpline 糊弄。本模板用 **草图顶点 fillet**,
     生成的一定是解析环面(Torus),半径就是参数本身。
  3) 旧重建把球头做成了平头。本模板的端部球头由 **与锥面相切** 解析求出,
     只要给总长和锥半角,球半径自动算出,做不出平顶。
  4) 侧面铣扁不是"切个方块",而是按 **刀具半径 + 刀心轨迹** 建模,
     自带 R 退刀圆弧,做不出理想尖角。

用法(自检):
  cd 实验-工艺规程Loop && ./.venv/bin/python ../training_loop/tools/geometry_truth/builders/locating_pin.py
"""
from __future__ import annotations
import os, json, math
import warnings; warnings.filterwarnings("ignore")
from build123d import (
    BuildSketch, BuildLine, Polyline, Line, TangentArc, make_face, fillet,
    revolve, Plane, Axis, Box, Cylinder, Pos, export_step, import_step,
)


# ────────────────────────────────────────────────────────────────────
# 通用建模器
# ────────────────────────────────────────────────────────────────────
def _ball_radius_tangent_to_cone(cone_pt, half_angle_deg, total_len):
    """求与锥面相切、且最右点正好落在 x=total_len 的球头半径。

    cone_pt = (x0, r0) 锥面母线上任一点;球心在轴上,x = total_len - R。
    几何条件:球心到母线距离 = R  =>  R = (r0·cos a - sin a·(L - x0)) / (1 - sin a)
    """
    x0, r0 = cone_pt
    a = math.radians(half_angle_deg)
    return (r0 * math.cos(a) - math.sin(a) * (total_len - x0)) / (1.0 - math.sin(a))


def build_stepped_pin(spec: dict):
    """按 spec 造一根阶梯销轴。轴向沿 +X,从 x=0 起。

    spec 字段:
      profile      : [(x, r), ...] 尖角轮廓断点(不含端部球头/锥头的收尾)。
                     第一点必须是 (0, 0) 之后的端面半径,由本函数自动补 (0,0)。
      fillets      : [{'at': (x, r), 'radius': R}, ...] 在指定尖角顶点上倒 R 圆角
      tip          : {'type': 'ball', 'half_angle': 25.0, 'total_len': 92.0}
                     从 profile 最后一点沿 half_angle 半角锥收小,末端接相切球头;
                     球半径由 total_len 解析求出(做不出平顶)。
                     {'type': 'flat'} 则直接把 profile 收到轴线。
      flats        : [{'y_half': 9.5, 'x_end': 50.0, 'cutter_r': 2.0}] 或 []
                     两侧对称铣扁:对边半宽 y_half,铣到 x_end 停刀,
                     刀具半径 cutter_r(刀心走 y = ±(y_half+cutter_r),轴向沿 Z),
                     末端自带 R=cutter_r 退刀圆弧。
    """
    prof = list(spec['profile'])
    tip = spec.get('tip', {'type': 'flat'})

    # ── 1. 尖角轮廓(母线),先不倒圆角 ──
    pts = [(0.0, 0.0)] + prof

    if tip['type'] == 'ball':
        a = math.radians(tip['half_angle'])
        L = tip['total_len']
        vx, vr = prof[-1]                      # 锥面母线与前一圆柱的尖角交点
        R = _ball_radius_tangent_to_cone((vx, vr), tip['half_angle'], L)
        cx = L - R                             # 球心(在轴上)
        # 锥面母线方向(向右下)
        d = (math.cos(a), -math.sin(a))
        # 球心到母线的垂足 = 锥/球相切点
        t = (cx - vx) * d[0] + (0.0 - vr) * d[1]
        T = (vx + d[0] * t, vr + d[1] * t)
        cone_dir = d
    else:
        R = cx = None
        T = None
        cone_dir = None

    with BuildSketch(Plane.XZ) as sk:
        with BuildLine():
            if tip['type'] == 'ball':
                Polyline(*pts, T)
                TangentArc([T, (tip['total_len'], 0.0)], tangent=cone_dir)
                Line((tip['total_len'], 0.0), (0.0, 0.0))
            else:
                Polyline(*pts, close=True)
        make_face()
        # ── 2. 指定顶点倒圆角(生成解析环面,不是 BSpline)──
        for f in spec.get('fillets', []):
            tx, tr = f['at']
            vs = sk.vertices()
            v = min(vs, key=lambda p: (p.X - tx) ** 2 + (p.Z - tr) ** 2)
            fillet(v, radius=f['radius'])

    part = revolve(sk.sketch, axis=Axis.X)

    # ── 3. 侧面铣扁:按刀心轨迹建模,自带退刀圆弧 ──
    for fl in spec.get('flats', []):
        yh, xe, cr = fl['y_half'], fl['x_end'], fl['cutter_r']
        yc = yh + cr                      # 刀心 y
        big = 4 * max(p[1] for p in prof) # 足够大的 Z 向贯穿高度
        for sgn in (+1, -1):
            slot = Pos(xe / 2, sgn * yc, 0) * Box(xe, 2 * cr, big)
            relief = Pos(xe, sgn * yc, 0) * Cylinder(radius=cr, height=big)
            part -= slot
            part -= relief
    return part


# ────────────────────────────────────────────────────────────────────
# 定位销 的参数
# ────────────────────────────────────────────────────────────────────
# 参数来源标注:
#   [图]    = 图纸直接标注的尺寸(总长/直径/倒角/对边宽/圆角代号等)
#   [图推导] = 图纸上没有直接给这个数,但可由若干直标尺寸算出;算式写在注释里
#   [惯例]   = 图纸未标注,依赖制造惯例或工程判断
#   [量]    = 只能从真值 STEP 实测得到
#
# 本零件 18 个参数的出处结论(经交叉复核):10 个 [图] + 8 个 [图推导],
# **没有任何一个参数依赖真值 STEP 实测**。以下两处曾被写错,现已更正:
#   · r=10.570 的出处不是 A-A 视图的 (10.57) 标注。那个 (10.57) 标的是铣扁弦宽,
#     数值相同纯属巧合。正确出处是 F 向的 C0.3max 倒角:21.74/2 − 0.3 = 10.570。
#   · x=75.971 不是真值实测尾巴,而是由 (SR5.33) + 25° 半角锥 + ⌀21.74 + 总长 92
#     解球锥相切方程精确得出。反过来若取 x=76.00,反算球半径为 5.351,与图纸
#     标注的 SR5.33 不符,可见 75.971 才是图纸自洽解。
LOCATING_PIN = {
    'name': '定位销',
    'profile': [
        (0.00,   5.500),   # [图] x=0 端面 ⌀11 → r=11/2
        (1.50,   7.000),   # [图推导] 1.5×45° 倒角(直标)+ ⌀14(直标):x=1.5, r=14/2
        (19.00,  7.000),   # [图推导] ⌀14 段长 17.5(直标):x = 1.5 + 17.5 = 19.00
        (20.75,  5.250),   # [图推导] 45° 倒角落到 ⌀10.5(直标):r=10.5/2=5.25,
                           #          x = 19.00 + (7.000 − 5.250) = 20.75(45° 故 Δx=Δr)
        (38.00,  5.250),   # [图] ⌀10.5 颈段,台阶端面轴向位置 38 为直标尺寸
        (38.00, 10.570),   # [图推导] ★更正:出处**不是** A-A 的 (10.57) 标注(那是铣扁弦宽,
                           #          数值巧合)。正确出处是 F 向的 C0.3max 倒角:
                           #          21.74/2 − 0.3 = 10.870 − 0.300 = 10.570
        (38.30, 10.870),   # [图推导] 同一 C0.3max 倒角的另一端 + ⌀21.74(直标):
                           #          x = 38.00 + 0.30,r = 21.74/2 = 10.870
        (75.971, 10.870),  # [图推导] ★更正:非真值实测。由 (SR5.33)+25° 半角+⌀21.74+总长 92
                           #          解球锥相切方程得:R(1−sin25°) = 10.87·cos25° − sin25°·(92−x₀)
                           #          → x₀ = 75.971。(取 76.00 反算球半径 5.351,与 SR5.33 不符)
    ],
    'fillets': [
        {'at': (20.75,  5.250), 'radius': 1.00},   # [图] R1 凹圆角(直标)
        {'at': (38.00,  5.250), 'radius': 1.00},   # [图] ★更正:R1 在图纸上是**直接标注**——
                                                   #      R1 的双箭头引线同时指向颈部两端圆角。
                                                   #      原注释按"惯例推断"标注,偏保守。
        {'at': (75.971, 10.870), 'radius': 6.35},  # [图] R6.35 过渡(直标)
    ],
    # [图] 25° 半角锥(直标)+ 总长 92(直标);球头半径由相切条件解析求出,
    # 解得 R≈5.33,与图纸参考尺寸 (SR5.33) 相符 —— 这也反证了上面 x=75.971 的正确性。
    'tip': {'type': 'ball', 'half_angle': 25.0, 'total_len': 92.0},
    'flats': [
        # [图] 对边宽 19(直标)→ y_half=9.5;铣扁终止 x=50(直标);退刀 R2(直标)
        {'y_half': 9.50, 'x_end': 50.0, 'cutter_r': 2.0},
    ],
}


def measure(obj):
    bb = obj.bounding_box()
    return {'volume': float(obj.volume), 'area': float(obj.area),
            'bbox': sorted([round(float(bb.size.X), 2), round(float(bb.size.Y), 2), round(float(bb.size.Z), 2)])}


def pct(a, b):
    return round((a - b) / b * 100, 2) if b else None


if __name__ == '__main__':
    PROJ = '/Users/macsean/Desktop/AI 工艺'
    truth_p = os.path.join(PROJ, '图纸及数模20250310', '3D数模', '定位销.STEP')
    recon_p = os.path.join(PROJ, '实验-工艺规程Loop', 'baseline', '定位销', 'model.step')

    built = build_stepped_pin(LOCATING_PIN)
    m_new = measure(built)
    m_tru = measure(import_step(truth_p))
    m_old = measure(import_step(recon_p))

    out_dir = os.path.join(PROJ, 'training_loop', 'tools', 'geometry_truth', 'out')
    os.makedirs(out_dir, exist_ok=True)
    step_out = os.path.join(out_dir, '定位销_template_v1.step')
    export_step(built, step_out)

    print('=== 定位销:模板重建 vs 旧 AI 重建 vs 真值 ===')
    print(f"{'':16}{'体积 mm³':>14}{'体积偏差':>12}{'表面积':>12}{'面积偏差':>12}  bbox")
    print(f"{'真值':16}{m_tru['volume']:>14.1f}{'—':>12}{m_tru['area']:>12.1f}{'—':>12}  {m_tru['bbox']}")
    print(f"{'旧 AI 重建':14}{m_old['volume']:>14.1f}{pct(m_old['volume'], m_tru['volume']):>11}%{m_old['area']:>12.1f}{pct(m_old['area'], m_tru['area']):>11}%  {m_old['bbox']}")
    print(f"{'新模板 v1':15}{m_new['volume']:>14.1f}{pct(m_new['volume'], m_tru['volume']):>11}%{m_new['area']:>12.1f}{pct(m_new['area'], m_tru['area']):>11}%  {m_new['bbox']}")

    json.dump({'truth': m_tru, 'old_recon': m_old, 'template_v1': m_new,
               'vol_dev_old_pct': pct(m_old['volume'], m_tru['volume']),
               'vol_dev_new_pct': pct(m_new['volume'], m_tru['volume']),
               'spec': LOCATING_PIN},
              open(os.path.join(out_dir, '定位销_template_v1.json'), 'w'), ensure_ascii=False, indent=1)
    print('\nSTEP + 指标已导出:', step_out)
