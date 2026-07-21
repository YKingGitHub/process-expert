#!/usr/bin/env python3
"""U4 校验器回归测试 —— 离线、零成本、几秒跑完。

**存在的理由**:2026-07-18 校验器接连出过三个 bug,每个都制造了"假失败",
浪费了数轮 4 分钟/次的推理模型调用,还差点被当成"模型能力不行":
  bug1  z0=0 被判"缺失",同时又禁止负坐标 → 模型被逼进死角(端盖连续 5 轮假失败)
  bug2  转录的**行号**被当成尺寸(外筒解析出 6~16 一串连号)→ 模型被迫解释不存在的尺寸
  bug3  正则用 \\w 导致 φ63.2 整个被滤掉;修完又把 13.5 拆成 5

**纪律**:任何时候改动 transcript_dims / validate,必须先跑通本文件再去烧模型调用。
  cd 实验-工艺规程Loop && ./.venv/bin/python ../training_loop/tools/geometry_truth/test_u4_validate.py
"""
import os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('u4', os.path.join(HERE, 'u4_pipeline.py'))
u4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u4)

FAILS = []


def check(name, got, want, note=''):
    ok = got == want
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}")
    if not ok:
        print(f"         得到 {got}\n         期望 {want}  {note}")
        FAILS.append(name)


def has(name, viols, keyword, expect=True):
    hit = any(keyword in v for v in viols)
    ok = (hit == expect)
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}")
    if not ok:
        print(f"         期望{'含' if expect else '不含'} {keyword!r},实际违规:{viols}")
        FAILS.append(name)


# ── transcript_dims ───────────────────────────────────────────
print('== transcript_dims ==')
T = u4.transcript_dims

check('bug2 行号不算尺寸', T('12. 10 | I 2:1 | 详图长度'), [10.0], '12 是行号')
check('bug3 行首小数不被拆', T('13.5 | A-A | 零件高度'), [13.5], '不能变成 5')
check('bug3 φ 前缀不吞数字', T('φ63.2-0.2 | 主视图 | 直径'), [63.2])
check('数量前缀 4- 不算尺寸', T('4-φ5 | 主视图 | 四个孔'), [5.0])
check('角度不计入', T('30° | I 2:1 | 倒角角度'), [])
check('R 半径可提取', T('R6.35 | A-A | 圆角'), [6.35])
check('技术要求行跳过', T('1. 未注公差按GB/T 1804-2000执行 | 技术要求 | 文字'), [])
check('粗糙度行跳过', T('其余 3.2 | 主视图 | 表面粗糙度'), [])
check('公差不计入', T('84.5±0.2 | 主视图 | 长度'), [84.5])
check('多行综合', T('1. φ52±0.15 | 主视图 | 外径\n2. 95+0.3 | 主视图 | 总长'), [95.0, 52.0])
# 粗糙度陷阱:同一数值可能既是 Ra 值又是真尺寸,只能靠上下文区分,不能按数值一刀切
check('粗糙度(表面)被跳过', T('1.6 | 主视图 | 中间表面'), [])
check('粗糙度(其余)被跳过', T('3.2 | 其余 | 整体表面（右上角）'), [])
check('同值真尺寸不被误杀', T('3.2 | 主视图 | 左侧垂直尺寸'), [3.2], '外筒凸缘长 3.2 与 Ra3.2 同值')
check('非 Ra 系列的表面描述保留', T('7.5 | 主视图 | 端面'), [7.5])

# ── validate ──────────────────────────────────────────────────
print('\n== validate ==')
TRANS = ('φ52±0.15 | 主视图 | 外径\nφ50+0.1 | 主视图 | 内孔\n'
         '95+0.3 | 主视图 | 总长\n18+0.2 | B-B | 槽宽\n3.5+0.1 | B-B | 槽深')

clean = {'length': 95, 'outer_dia': 52,
         'bore': [{'from_dia': 50, 'to_dia': 50, 'z0': 0, 'z1': 95}],
         'slot': {'width': 18, 'depth': 3.5}}
has('干净 spec 无违规', u4.validate(clean, {'x': 'y'}, TRANS), '', expect=False)

bad_bore = {'length': 95, 'outer_dia': 50,
            'bore': [{'from_dia': 52, 'to_dia': 52, 'z0': 0, 'z1': 95}],
            'slot': {'width': 18, 'depth': 3.5}}
has('内孔大于外径被拦', u4.validate(bad_bore, {'x': 'y'}, TRANS), '物理不可能')

zero_z0 = {'length': 95, 'outer_dia': 52,
           'bore': [{'from_dia': 50, 'to_dia': 50, 'z0': 0, 'z1': 95}],
           'slot': {'width': 18, 'depth': 3.5}}
has('bug1 坐标 z0=0 合法', u4.validate(zero_z0, {'x': 'y'}, TRANS), '不存在/为空', expect=False)

zero_size = {'length': 95, 'outer_dia': 52,
             'bore': [{'from_dia': 50, 'to_dia': 50, 'z0': 0, 'z1': 95}],
             'slot': {'width': 0, 'depth': 0}}
has('尺寸为 0 被拦', u4.validate(zero_size, {'x': 'y'}, TRANS), '不存在/为空')

nulls = {'length': 95, 'outer_dia': 52,
         'bore': [{'from_dia': 50, 'to_dia': 50, 'z0': None, 'z1': 95}],
         'slot': {'width': 18, 'depth': 3.5}}
has('null 被拦', u4.validate(nulls, {'x': 'y'}, TRANS), 'null')

rev = {'length': 95, 'outer_dia': 52,
       'bore': [{'from_dia': 50, 'to_dia': 50, 'z0': 90, 'z1': 90}],
       'slot': {'width': 18, 'depth': 3.5}}
has('零高度分段被拦', u4.validate(rev, {'x': 'y'}, TRANS), '零高度')

unused = {'length': 95, 'outer_dia': 52,
          'bore': [{'from_dia': 50, 'to_dia': 50, 'z0': 0, 'z1': 95}],
          'slot': {'width': 18, 'depth': 99}}
has('转录里没用到的尺寸被指出', u4.validate(unused, {'x': 'y'}, TRANS), '没有把它们用在')

has('缺 evidence 被拦', u4.validate(clean, {}, TRANS), 'evidence')

degen = {'length': 95, 'outer_dia': 52,
         'bore': [{'type': 'cone', 'from_dia': 50, 'to_dia': 50, 'z0': 0, 'z1': 95}],
         'slot': {'width': 18, 'depth': 3.5}}
has('退化的锥被拦', u4.validate(degen, {'x': 'y'}, TRANS), '两端直径相同')

okcone = {'length': 95, 'outer_dia': 52,
          'bore': [{'type': 'cone', 'from_dia': 50, 'to_dia': 46, 'z0': 0, 'z1': 95}],
          'slot': {'width': 18, 'depth': 3.5}}
has('正常锥不误伤', u4.validate(okcone, {'x': 'y'}, TRANS), '两端直径相同', expect=False)

over = {'length': 95, 'outer_dia': 52,
        'bore': [{'from_dia': 50, 'to_dia': 50, 'z0': 0, 'z1': 120}],
        'slot': {'width': 18, 'depth': 3.5}}
has('分段超出总长被指出', u4.validate(over, {'x': 'y'}, TRANS), '超出了总长')

# ── 盲测守卫 ──────────────────────────────────────────────────
print('\n== 盲测守卫 ==')
try:
    u4.assert_feedback_safe('请复核 77.7 这个尺寸', TRANS, [], [])
    print('  [FAIL] 注入外部数值未被拦'); FAILS.append('feedback_leak')
except RuntimeError:
    print('  [OK ] 注入外部数值被拦')
try:
    u4.assert_feedback_safe('你读到的 95 没有用上', TRANS, [], [])
    print('  [OK ] 回放模型自己的数不误伤')
except RuntimeError as e:
    print(f'  [FAIL] 误伤模型自己的数:{e}'); FAILS.append('feedback_false_positive')

# ── 模板允许缺失的特征 ──────────────────────────────────────────
print('\n== 允许缺失的特征 ==')
EX = {'length': 0, 'outer_dia': 0, 'radial_holes': None}   # 模板示例:本族无径向孔
nohole = {'length': 95, 'outer_dia': 52, 'radial_holes': None}
has('模板本就为空 → 不判缺失', u4.validate(nohole, {'x':'y'}, TRANS, EX), '不存在/为空', expect=False)
has('模板非空 → 仍判缺失', u4.validate({'length':95,'outer_dia':52,'slot':{}}, {'x':'y'}, TRANS,
                                    {'length':0,'outer_dia':0,'slot':{'width':1}}), '不存在/为空')
print('\n' + ('全部通过 ✅' if not FAILS else f'失败 {len(FAILS)} 项 ❌ {FAILS}'))
# ── 结构完整性 ──────────────────────────────────────────────
print('\n== 结构完整性 ==')
EX2 = {'length':0, 'profile':[{'d0':0,'d1':0,'x0':0,'x1':0}]}
miss = {'length':95, 'profile':[{'d0':46,'x0':0,'x1':100}]}          # 少了 d1
has('漏写必填字段被拦', u4.validate(miss, {'x':'y'}, TRANS, EX2), '必填字段缺失')
full = {'length':95, 'profile':[{'d0':46,'d1':38,'x0':0,'x1':100}]}
has('字段齐全不误伤', u4.validate(full, {'x':'y'}, TRANS, EX2), '必填字段缺失', expect=False)

print('\n' + ('全部通过 ✅' if not FAILS else f'失败 {len(FAILS)} 项 ❌ {FAILS}'))
sys.exit(1 if FAILS else 0)
