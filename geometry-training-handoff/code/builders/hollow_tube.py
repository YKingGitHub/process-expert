#!/usr/bin/env python3
"""形状族建模器:空心回转筒(hollow tube)

Stage 2 的第一个形状族。适用:外筒、套、环、管类——即"薄壁 + 内孔 + 端部台阶"这一族。

设计要点(针对实测失败模式):
  AI 直接建模时尺寸读得对、却把"薄壁空心筒"做成了实心棒(外筒实测 +845%)。
  本模板把"掏空"变成结构性的必然:先造外形回转体,再必定减去内孔回转体。
  内孔由分段列表定义,做不出实心棒。

用法(自检):用 实验-工艺规程Loop/.venv 跑本文件,会用外筒真值参数建模并与真值比对。
  cd 实验-工艺规程Loop && ./.venv/bin/python ../training_loop/tools/geometry_truth/builders/hollow_tube.py
"""
from __future__ import annotations
import os, json
import warnings; warnings.filterwarnings("ignore")
from build123d import Cylinder, Cone, Pos, Rot, Align, export_step, import_step

MIN = (Align.CENTER, Align.CENTER, Align.MIN)


def build_hollow_tube(spec: dict):
    """按 spec 造一个空心回转筒。轴向沿 +Z,从 z=0 起。

    spec 字段:
      length            总长
      outer_dia         主体外径
      collar_dia/len    端部凸缘外径/轴向长(无凸缘则 collar_len=0)
      bore              内孔分段列表,每段 {'type':'cyl'|'cone','from_dia','to_dia','z0','z1'}
      radial_holes      {'count','dia','z'} 或 None
    """
    L = spec['length']
    od = spec['outer_dia']
    cd = spec.get('collar_dia', od)
    cl = spec.get('collar_len', 0.0)

    # --- 外形:凸缘 + 主体 ---
    part = None
    if cl > 0:
        part = Cylinder(radius=cd / 2, height=cl, align=MIN)
    body = Pos(0, 0, cl) * Cylinder(radius=od / 2, height=L - cl, align=MIN)
    part = body if part is None else part + body

    # --- 内孔:分段减除(结构上保证"必然空心")---
    for seg in spec.get('bore', []):
        z0, z1 = seg['z0'], seg['z1']
        h = z1 - z0
        if h <= 0:
            continue
        if seg['type'] == 'cyl':
            cut = Cylinder(radius=seg['from_dia'] / 2, height=h, align=MIN)
        else:  # cone frustum
            cut = Cone(bottom_radius=seg['from_dia'] / 2, top_radius=seg['to_dia'] / 2,
                       height=h, align=MIN)
        part -= Pos(0, 0, z0) * cut

    # --- 径向孔 ---
    rh = spec.get('radial_holes')
    if rh and rh.get('count'):
        n, hd, hz = rh['count'], rh['dia'], rh['z']
        for i in range(n):
            probe = Rot(0, 90, 0) * Cylinder(radius=hd / 2, height=max(cd, od) * 2)
            part -= Pos(0, 0, hz) * Rot(0, 0, i * (360.0 / n)) * probe
    return part


# ── 外筒(case 002)的参数:全部来自图纸可读尺寸 ──
WAITONG = {
    'name': '外筒',
    'length': 95.0,
    'outer_dia': 52.0,
    'collar_dia': 63.2,
    'collar_len': 3.2,
    'bore': [
        {'type': 'cone', 'from_dia': 52.31, 'to_dia': 50.0, 'z0': 0.0,   'z1': 2.0},    # 孔口 30° 倒角
        {'type': 'cyl',  'from_dia': 50.0,  'to_dia': 50.0, 'z0': 2.0,   'z1': 87.7},   # 主内孔(壁厚 1.0)
        {'type': 'cone', 'from_dia': 50.0,  'to_dia': 46.2, 'z0': 87.7,  'z1': 89.31},  # 收口
        {'type': 'cyl',  'from_dia': 46.2,  'to_dia': 46.2, 'z0': 89.31, 'z1': 94.0},   # 端部小孔
        {'type': 'cone', 'from_dia': 46.2,  'to_dia': 48.2, 'z0': 94.0,  'z1': 95.0},   # 端口张开(近似圆角)
    ],
    'radial_holes': {'count': 4, 'dia': 5.0, 'z': 13.2},
}


def measure(obj):
    bb = obj.bounding_box()
    return {'volume': float(obj.volume), 'area': float(obj.area),
            'bbox': sorted([round(float(bb.size.X), 2), round(float(bb.size.Y), 2), round(float(bb.size.Z), 2)])}


def pct(a, b):
    return round((a - b) / b * 100, 2) if b else None


if __name__ == '__main__':
    PROJ = '/Users/macsean/Desktop/AI 工艺'
    truth_p = os.path.join(PROJ, '图纸及数模20250310', '3D数模', '外筒.STEP')
    recon_p = os.path.join(PROJ, '实验-工艺规程Loop', 'baseline', '外筒', 'model.step')

    built = build_hollow_tube(WAITONG)
    m_new = measure(built)
    m_tru = measure(import_step(truth_p))
    m_old = measure(import_step(recon_p))

    out_dir = os.path.join(PROJ, 'training_loop', 'tools', 'geometry_truth', 'out')
    os.makedirs(out_dir, exist_ok=True)
    export_step(built, os.path.join(out_dir, '外筒_template_v1.step'))

    print('=== 外筒:模板重建 vs 旧 AI 重建 vs 真值 ===')
    print(f"{'':16}{'体积 mm³':>14}{'体积偏差':>12}{'表面积':>12}{'面积偏差':>12}  bbox")
    print(f"{'真值':16}{m_tru['volume']:>14.1f}{'—':>12}{m_tru['area']:>12.1f}{'—':>12}  {m_tru['bbox']}")
    print(f"{'旧 AI 重建':14}{m_old['volume']:>14.1f}{pct(m_old['volume'], m_tru['volume']):>11}%{m_old['area']:>12.1f}{pct(m_old['area'], m_tru['area']):>11}%  {m_old['bbox']}")
    print(f"{'新模板 v1':15}{m_new['volume']:>14.1f}{pct(m_new['volume'], m_tru['volume']):>11}%{m_new['area']:>12.1f}{pct(m_new['area'], m_tru['area']):>11}%  {m_new['bbox']}")

    json.dump({'truth': m_tru, 'old_recon': m_old, 'template_v1': m_new,
               'vol_dev_old_pct': pct(m_old['volume'], m_tru['volume']),
               'vol_dev_new_pct': pct(m_new['volume'], m_tru['volume']),
               'spec': WAITONG},
              open(os.path.join(out_dir, '外筒_template_v1.json'), 'w'), ensure_ascii=False, indent=1)
    print('\nSTEP + 指标已导出:', os.path.relpath(out_dir, PROJ))
