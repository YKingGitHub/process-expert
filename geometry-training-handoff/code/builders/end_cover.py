#!/usr/bin/env python3
"""形状族建模器:门形截面板类盖(channel-section plate cover)

Stage 2 的第二个形状族。适用:端盖、压板、槽形垫块——即"矩形板 + 底部通长凹槽
+ 贯穿厚度方向的中心孔 + 长棱倒圆"这一族。零件截面呈倒扣的 Π 形(门形),沿长度拉伸。

设计要点(针对实测失败模式):
  旧 AI 重建把端盖做成了"实心长方体 + 角上切一个 1/4 圆柱",
  完全漏掉了底部 18 x 3.5 x 40 的通长凹槽(占真值体积 31%),偏差 +41.98%。
  本模板把"挖槽"和"打孔"变成结构性的必然:
    先造带圆角的外形板 → 必定减去底部通槽 → 必定减去中心孔。
  slot 与 bore 是 build_channel_plate 的必需字段,缺失即抛错,做不出实心板。

局部坐标(建模用):
  X = 板宽 width,居中 [-W/2, +W/2]
  Y = 板长 length,居中 [-L/2, +L/2]
  Z = 板厚 thickness,从 0(带槽的底面)到 T(顶面)
导出前统一旋转到真值 STEP 的原生坐标系:X 宽 / Y 厚 / Z 长。

用法(自检):用 实验-工艺规程Loop/.venv 跑本文件,会用端盖参数建模并与真值 + 旧重建比对。
  cd 实验-工艺规程Loop && ./.venv/bin/python ../training_loop/tools/geometry_truth/builders/end_cover.py
"""
from __future__ import annotations
import os, json
import warnings; warnings.filterwarnings("ignore")
from build123d import (Rectangle, Box, Cylinder, Pos, Rot, Align, extrude, fillet,
                       export_step, import_step)

ZMIN = (Align.CENTER, Align.CENTER, Align.MIN)


def build_channel_plate(spec: dict):
    """按 spec 造一个门形截面板类盖。

    spec 字段:
      width       板宽(局部 X)
      length      板长(局部 Y,凹槽通长方向)
      thickness   板厚(局部 Z,底面 z=0 → 顶面 z=T)
      corner_r    沿厚度方向的 4 条长棱圆角半径(0 表示不倒圆)
      slot   【必需】底部通长凹槽 {'width': 槽宽(X), 'depth': 槽深(Z,自 z=0 向上)}
                    通长方向恒为 Y 全通。depth<=0 视为无槽需显式写 0。
      bore   【必需】中心孔列表,每项 {'dia','x','y','z0','z1'};z 为局部厚度坐标。
                    空列表表示确实无孔,必须显式给出。
    """
    W, L, T = spec['width'], spec['length'], spec['thickness']
    r = spec.get('corner_r', 0.0)

    if 'slot' not in spec or 'bore' not in spec:
        raise ValueError("channel_plate 必须显式声明 slot 与 bore(哪怕为 0/空),"
                         "以防退化成实心板")

    # --- 1) 外形:带圆角的矩形截面沿厚度拉伸 ---
    sk = Rectangle(W, L)
    if r > 0:
        sk = fillet(sk.vertices(), radius=r)
    part = extrude(sk, amount=T)                      # z: 0 → T

    # --- 2) 底部通长凹槽(结构上必然掏空)---
    sl = spec['slot']
    sw, sd = sl['width'], sl['depth']
    if sd > 0:
        part -= Pos(0, 0, 0) * Box(sw, L * 2, sd, align=ZMIN)

    # --- 3) 中心孔(结构上必然打穿)---
    for h in spec['bore']:
        z0, z1 = h['z0'], h['z1']
        if z1 <= z0:
            continue
        part -= Pos(h.get('x', 0.0), h.get('y', 0.0), z0) * \
            Cylinder(radius=h['dia'] / 2, height=z1 - z0, align=ZMIN)

    # --- 4) 转到真值原生坐标:局部(宽,长,厚) → 全局(X宽, Y厚, Z长) ---
    part = Rot(90, 0, 0) * part
    return part


# ── 端盖(case: 端盖)的参数 ──
# 参数来源标注:
#   [图纸]     图纸上有直接标注的名义尺寸,照抄即可
#   [图纸推导] 图纸未直接给这一项,但由已标注尺寸 + 对称性/结构关系唯一确定,附算式
#   [惯例]     图纸未标注、需靠工艺惯例或判断补全(本零件目前无此类项)
#   [真值]     只能从 端盖.STEP 实测得到(本零件 12 项参数中为 0 项,不依赖真值)
#
# 复核结论(2026-07):12 项参数 = 8 项图纸直标 + 4 项图纸推导 + 0 项依赖真值。
# 早期版本曾把 corner_r / slot.width / slot.depth / bore.dia 误标为 [真值] 实测,
# 事实上这四项图纸均有直接标注(4-R1、18 +0.2/0、3.5 +0.1/0、φ12.8),已更正。
DUANGAI = {
    'name': '端盖',
    'width': 22.0,        # [图纸] 板宽 22
    'length': 40.0,       # [图纸] 板长 40
    'thickness': 13.5,    # [图纸] 板厚 13.5
    'corner_r': 1.0,      # [图纸] 长棱倒圆,标注 4-R1
    'slot': {
        'width': 18.0,    # [图纸] 槽宽,标注 18 +0.2/0(取名义值 18)
        'depth': 3.5,     # [图纸] 槽深,标注 3.5 +0.1/0(取名义值 3.5)
                          # [图纸] 槽沿板长方向通长(Y 全通),由图纸剖视/视图直接可读
    },
    'bore': [
        # 'dia' [图纸] 中心孔标注 φ12.8
        # 'x','y' [图纸推导] 孔在板宽/板长方向均居中 → x = 0、y = 0
        #         (由图纸对称中心线标注得到,非实测)
        # 'z0'    [图纸推导] 孔自槽底起算 → z0 = slot.depth = 3.5
        # 'z1'    [图纸推导] 孔贯穿至顶面 → z1 = thickness = 13.5
        {'dia': 12.8, 'x': 0.0, 'y': 0.0, 'z0': 3.5, 'z1': 13.5},
    ],
}


def measure(obj):
    bb = obj.bounding_box()
    return {'volume': float(obj.volume), 'area': float(obj.area),
            'bbox': sorted([round(float(bb.size.X), 2), round(float(bb.size.Y), 2),
                            round(float(bb.size.Z), 2)])}


def pct(a, b):
    return round((a - b) / b * 100, 2) if b else None


if __name__ == '__main__':
    PROJ = '/Users/macsean/Desktop/AI 工艺'
    truth_p = os.path.join(PROJ, '图纸及数模20250310', '3D数模', '端盖.STEP')
    recon_p = os.path.join(PROJ, '实验-工艺规程Loop', 'baseline', '端盖', 'model.step')

    built = build_channel_plate(DUANGAI)
    m_new = measure(built)
    m_tru = measure(import_step(truth_p))
    m_old = measure(import_step(recon_p))

    out_dir = os.path.join(PROJ, 'training_loop', 'tools', 'geometry_truth', 'out')
    os.makedirs(out_dir, exist_ok=True)
    export_step(built, os.path.join(out_dir, '端盖_template_v1.step'))

    print('=== 端盖:模板重建 vs 旧 AI 重建 vs 真值 ===')
    print(f"{'':16}{'体积 mm³':>14}{'体积偏差':>12}{'表面积':>12}{'面积偏差':>12}  bbox")
    print(f"{'真值':16}{m_tru['volume']:>14.1f}{'—':>12}{m_tru['area']:>12.1f}{'—':>12}  {m_tru['bbox']}")
    print(f"{'旧 AI 重建':14}{m_old['volume']:>14.1f}{pct(m_old['volume'], m_tru['volume']):>11}%{m_old['area']:>12.1f}{pct(m_old['area'], m_tru['area']):>11}%  {m_old['bbox']}")
    print(f"{'新模板 v1':15}{m_new['volume']:>14.1f}{pct(m_new['volume'], m_tru['volume']):>11}%{m_new['area']:>12.1f}{pct(m_new['area'], m_tru['area']):>11}%  {m_new['bbox']}")

    json.dump({'truth': m_tru, 'old_recon': m_old, 'template_v1': m_new,
               'vol_dev_old_pct': pct(m_old['volume'], m_tru['volume']),
               'vol_dev_new_pct': pct(m_new['volume'], m_tru['volume']),
               'spec': DUANGAI},
              open(os.path.join(out_dir, '端盖_template_v1.json'), 'w'),
              ensure_ascii=False, indent=1)
    print('\nSTEP + 指标已导出:', os.path.relpath(out_dir, PROJ))
