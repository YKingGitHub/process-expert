#!/usr/bin/env python3
"""形状族建模器:变径实心锥杆 + 端部深镗孔(tapered rod)

Stage 2 的第二个形状族。适用:锥杆、顶杆、心轴、阶梯轴类——即
"实心变径回转体 + 从一端钻入的深孔 + 两端中心孔/倒角"这一族。

设计要点(针对实测失败模式):
  旧 AI 重建把"实心锥杆 + 大端深镗孔"误解成了"薄壁套管 + 阶梯轴 + 侧向孔",
  丢掉了 294mm 的主锥段,体积 −44%。本模板把构造关系写死:
    1) 外轮廓 profile 是一串"实心"回转段(cyl/cone/torus_fillet),必须从 x=0 累加到 L;
    2) 内腔 bores 是"必定被减去"的分段孔,永远不可能变成外圆;
    3) 内外用两个独立列表表达,结构上做不出"把内孔直径当外圆"的错误。

图纸轮廓约定:
  图纸以实线表示焊前加工轮廓、虚线表示零件最终(焊后)轮廓。
  本模板下方 ZHUIGAN 复现的是**实线,即焊前加工轮廓**。
  参数出处逐条标注见 ZHUIGAN 上方注释。

用法(自检):
  cd 实验-工艺规程Loop && ./.venv/bin/python ../training_loop/tools/geometry_truth/builders/tapered_rod.py
"""
from __future__ import annotations
import os, json
import warnings; warnings.filterwarnings("ignore")
from build123d import (Cylinder, Cone, Torus, Pos, Rot, Align, Plane,
                       export_step, import_step, revolve, Polyline, Line, make_face)
from build123d import Vector

MINZ = (Align.CENTER, Align.CENTER, Align.MIN)


def _seg_solid(seg):
    """把一个外轮廓分段变成一个沿 +Z、底面在 z=0 的实心回转体。"""
    h = seg['x1'] - seg['x0']
    if h <= 0:
        return None
    t = seg['type']
    if t == 'cyl':
        return Cylinder(radius=seg['d0'] / 2, height=h, align=MINZ)
    if t == 'cone':
        return Cone(bottom_radius=seg['d0'] / 2, top_radius=seg['d1'] / 2,
                    height=h, align=MINZ)
    raise ValueError(f'unknown outer seg type: {t}')


def build_tapered_rod(spec: dict):
    """按 spec 造一根实心变径锥杆(带内腔)。轴向沿 +Z,从 z=0(小端)到 z=L。

    spec 字段:
      length      总长(用于校验 profile 是否首尾连续)
      profile     外轮廓分段列表(实心),按 x 从小到大:
                    {'type':'cyl','d0':D,'x0':..,'x1':..}
                    {'type':'cone','d0':D0,'d1':D1,'x0':..,'x1':..}
      fillets     外轮廓上的环面圆角(凸圆角 = 从外轮廓上减去一圈环外料):
                    {'r_major':Rmaj,'r_minor':Rmin,'x':中心圆轴向位置}
                  实现:先把该处补成 (Rmaj+Rmin) 的圆柱段,再减去"环外的料"。
                  这里采用更直接的做法:在 profile 里已用直圆柱占位,
                  然后减去 (圆柱环 − 环面) 的差集。
      bores       内腔分段列表(必定被减去),每段:
                    {'type':'cyl'|'cone','d0':..,'d1':..,'x0':..,'x1':..}
    """
    L = spec['length']

    # ── 1. 外形:分段实心回转体累加(结构上保证"实心") ──
    part = None
    for seg in spec['profile']:
        s = _seg_solid(seg)
        if s is None:
            continue
        s = Pos(0, 0, seg['x0']) * s
        part = s if part is None else part + s
    if part is None:
        raise ValueError('profile 为空,造不出实体')

    # ── 2. 外圆角(环面):profile 里该段用 r=r_major 的圆柱占位,这里减去环面 ──
    #   环面占据 r ∈ [Rmaj−s, Rmaj+s](s=sqrt(Rmin²−u²)),
    #   所以 圆柱(Rmaj) − 环面 = r < Rmaj−s,正是真值那条内凹母线。
    for f in spec.get('fillets', []):
        tor = Pos(0, 0, f['x']) * Torus(major_radius=f['r_major'],
                                        minor_radius=f['r_minor'])
        part -= tor

    # ── 3. 内腔:必定减去(结构上保证"做不出实心") ──
    for seg in spec.get('bores', []):
        h = seg['x1'] - seg['x0']
        if h <= 0:
            continue
        if seg['type'] == 'cyl':
            cut = Cylinder(radius=seg['d0'] / 2, height=h, align=MINZ)
        elif seg['type'] == 'cone':
            cut = Cone(bottom_radius=seg['d0'] / 2, top_radius=seg['d1'] / 2,
                       height=h, align=MINZ)
        else:
            raise ValueError(f"unknown bore seg type: {seg['type']}")
        part -= Pos(0, 0, seg['x0']) * cut

    # ── 4. 径向孔(本族一般没有,保留接口) ──
    rh = spec.get('radial_holes')
    if rh and rh.get('count'):
        rmax = max(s.get('d0', 0) for s in spec['profile']) + 10
        for i in range(rh['count']):
            probe = Rot(0, 90, 0) * Cylinder(radius=rh['dia'] / 2, height=rmax * 2)
            part -= Pos(0, 0, rh['x']) * Rot(0, 0, i * (360.0 / rh['count'])) * probe
    return part


# ── 锥杆(CHL-RVI-DR32B11A)的参数 ──
#
# 【本模板复现的是哪条轮廓】图纸用实线/虚线区分两种轮廓:
#   实线 = 焊前加工轮廓,虚线 = 零件最终(焊后)轮廓。
#   下面这套参数复现的是**实线,即焊前加工轮廓**。
#
# 【参数出处】除单独注明者外,全部来自图纸标注或由图纸标注唯一推出:
#   - 总长 577、⌀46、⌀96、⌀78、⌀72、⌀38、⌀5/⌀9.5 中心孔、R3、
#     30° 锪窝、锥段起止 202/496  → [图纸] 直接标注。
#   - 锥段半顶角 4.8604°           → [图纸推导] atan(((96−46)/2)/(496−202))。
#   - 倒角段 x570.624→573.181、端半径 48→40.974(即 ⌀81.948)
#                                  → [图纸推导] 由 ⌀96 端面倒角 20°(半顶角 70°)
#                                    与 3±0.05 台阶、R3 相切关系解出;
#                                    (48−40.974)/(573.181−570.624)=tan70°。
#   - R3 圆角中心圆 x=576、r=42     → [图纸推导] x=577−1(⌀78 端台厚 1),
#                                    r=(78+2·3)/2=42,即 R3 与 ⌀78 端台相切。
#   - 内腔 x520                    → [图纸推导] ⌀72 沉孔深度标注(577−520=57)。
#   - 内腔 x490.555                → [图纸推导] 30° 锥过渡:
#                                    520−((72−38)/2)/tan30°。
#   - 内腔 x341                    → [图纸推导] ⌀38 深孔深度标注(577−341=236)。
#
# 【依赖惯例/工程判断,非图纸唯一确定】
#   - 内腔 x330.030(钻尖锥底):依赖**未标注的 120° 标准麻花钻钻尖惯例**
#     (341−19/tan60°)。图上只画了 V 形,未注角度;真值 STEP 实测约 120.6°。
#   - 577(min)、⌀9.5(max)、⌀5(max)、14(max) 在图纸上是**极限值而非名义值**,
#     本模板直接取极限值作名义值,属工程判断。
#   - ⌀72 是**配制尺寸**(技术要求第 6 条,随中间柱内径浮动),此处取标称 72。
ZHUIGAN = {
    'name': '锥杆',
    'length': 577.0,
    'profile': [
        {'type': 'cyl',  'd0': 46.0, 'x0': 0.0,       'x1': 202.0},      # ⌀46 直杆
        {'type': 'cone', 'd0': 46.0, 'd1': 96.0, 'x0': 202.0, 'x1': 496.0},  # 主锥段(占 73.7% 体积)
        {'type': 'cyl',  'd0': 96.0, 'x0': 496.0,     'x1': 570.624},    # ⌀96 直段
        {'type': 'cone', 'd0': 96.0, 'd1': 81.948, 'x0': 570.624, 'x1': 573.181},  # 70° 半顶角倒角
        {'type': 'cyl',  'd0': 84.0, 'x0': 573.181, 'x1': 576.0},        # R3 圆角占位圆柱(d=2*Rmaj)
        {'type': 'cyl',  'd0': 78.0, 'x0': 576.0,     'x1': 577.0},      # ⌀78 端台
    ],
    'fillets': [
        {'r_major': 42.0, 'r_minor': 3.0, 'x': 576.0},                   # R3 凸圆角
    ],
    'bores': [
        # 小端 B 型中心孔(x=0 钻入)
        {'type': 'cone', 'd0': 9.5, 'd1': 5.0, 'x0': 0.0,    'x1': 3.897},
        {'type': 'cyl',  'd0': 5.0,            'x0': 3.897,  'x1': 12.557},
        {'type': 'cone', 'd0': 5.0, 'd1': 0.0, 'x0': 12.557, 'x1': 14.0},
        # 大端深镗腔(x=577 钻入,方向朝 −x,故按 x 升序写成)
        {'type': 'cone', 'd0': 0.0,  'd1': 38.0, 'x0': 330.030, 'x1': 341.0},   # 钻尖锥:依赖未标注的 120° 标准钻尖惯例(图纸只画 V 形)
        {'type': 'cyl',  'd0': 38.0,             'x0': 341.0,   'x1': 490.555}, # ⌀38 深孔
        {'type': 'cone', 'd0': 38.0, 'd1': 72.0, 'x0': 490.555, 'x1': 520.0},   # 30° 锥过渡
        {'type': 'cyl',  'd0': 72.0,             'x0': 520.0,   'x1': 577.0},   # ⌀72 沉孔(配制尺寸,技术要求第6条)
    ],
    'radial_holes': None,
}


def measure(obj):
    bb = obj.bounding_box()
    return {'volume': float(obj.volume), 'area': float(obj.area),
            'bbox': sorted([round(float(bb.size.X), 2), round(float(bb.size.Y), 2), round(float(bb.size.Z), 2)])}


def pct(a, b):
    return round((a - b) / b * 100, 2) if b else None


if __name__ == '__main__':
    PROJ = '/Users/macsean/Desktop/AI 工艺'
    truth_p = os.path.join(PROJ, '图纸及数模20250310', '3D数模', '锥杆.STEP')
    recon_p = os.path.join(PROJ, '实验-工艺规程Loop', 'baseline', '锥杆', 'model.step')

    built = build_tapered_rod(ZHUIGAN)
    m_new = measure(built)
    m_tru = measure(import_step(truth_p))
    m_old = measure(import_step(recon_p))

    out_dir = os.path.join(PROJ, 'training_loop', 'tools', 'geometry_truth', 'out')
    os.makedirs(out_dir, exist_ok=True)
    export_step(built, os.path.join(out_dir, '锥杆_template_v1.step'))

    print('=== 锥杆:模板重建 vs 旧 AI 重建 vs 真值 ===')
    print(f"{'':16}{'体积 mm³':>14}{'体积偏差':>12}{'表面积':>12}{'面积偏差':>12}  bbox")
    print(f"{'真值':16}{m_tru['volume']:>14.1f}{'—':>12}{m_tru['area']:>12.1f}{'—':>12}  {m_tru['bbox']}")
    print(f"{'旧 AI 重建':14}{m_old['volume']:>14.1f}{pct(m_old['volume'], m_tru['volume']):>11}%{m_old['area']:>12.1f}{pct(m_old['area'], m_tru['area']):>11}%  {m_old['bbox']}")
    print(f"{'新模板 v1':15}{m_new['volume']:>14.1f}{pct(m_new['volume'], m_tru['volume']):>11}%{m_new['area']:>12.1f}{pct(m_new['area'], m_tru['area']):>11}%  {m_new['bbox']}")

    json.dump({'truth': m_tru, 'old_recon': m_old, 'template_v1': m_new,
               'vol_dev_old_pct': pct(m_old['volume'], m_tru['volume']),
               'vol_dev_new_pct': pct(m_new['volume'], m_tru['volume']),
               'spec': ZHUIGAN},
              open(os.path.join(out_dir, '锥杆_template_v1.json'), 'w'), ensure_ascii=False, indent=1)
    print('\nSTEP + 指标已导出:', os.path.relpath(out_dir, PROJ))
