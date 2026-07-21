#!/usr/bin/env python3
"""诚实几何基线:AI 重建(baseline/*/model.step) vs 真实真值(3D数模/*.STEP)。

原则:
- 只用离线、旋转/平移不变的稳健指标(体积%、表面积%、轴排序包围盒%),不引入对齐风险。
- 先自检比对器(恒等=0;放大10%的盒子=体积+33.1%),自检过才输出正式表。
- 不判 pass/fail(那是后续 U6 标准校准的事),这里只给诚实的原始偏差。
运行:用 实验-工艺规程Loop/.venv 的 python。
"""
from __future__ import annotations
import os, sys, json, csv, unicodedata

def find_proj():
    DESKTOP='/Users/macsean/Desktop'
    for n in os.listdir(DESKTOP):
        p=os.path.join(DESKTOP,n)
        if os.path.isdir(p):
            try:
                if 'training_loop' in os.listdir(p): return p
            except Exception: pass
    return None

PROJ=find_proj()
from build123d import import_step, Box  # noqa

def nfc(s): return unicodedata.normalize('NFC', s)

# ---- U1(最小版)真值加载器 ----
def measure_solid(obj):
    bb=obj.bounding_box()
    size=sorted([bb.size.X, bb.size.Y, bb.size.Z])  # 轴排序 → 抵消朝向轴交换
    return {'volume': float(obj.volume), 'area': float(obj.area),
            'bbox_sorted': [round(x,4) for x in size]}

def load_step_measure(path):
    try:
        obj=import_step(path)
        m=measure_solid(obj)
        # 合法性:体积为正、有限
        ok = m['volume'] is not None and m['volume']>1e-9
        m['ok']=bool(ok); m['error']=None
        return m
    except Exception as e:
        return {'ok':False,'error':f'{type(e).__name__}: {str(e)[:160]}',
                'volume':None,'area':None,'bbox_sorted':None}

# ---- U2(最小版)通用比对器:稳健不变量 ----
def compare(pred, truth):
    def pct(a,b):
        if a is None or b is None or b==0: return None
        return round((a-b)/b*100, 2)
    out={'volume_dev_pct': pct(pred.get('volume'), truth.get('volume')),
         'area_dev_pct':   pct(pred.get('area'),   truth.get('area'))}
    ps, ts = pred.get('bbox_sorted'), truth.get('bbox_sorted')
    if ps and ts:
        out['bbox_axis_dev_pct']=[pct(ps[i],ts[i]) for i in range(3)]
        out['bbox_max_axis_dev_pct']=max(abs(x) for x in out['bbox_axis_dev_pct'] if x is not None)
    else:
        out['bbox_axis_dev_pct']=None; out['bbox_max_axis_dev_pct']=None
    return out

# ---- 自检:比对器必须先证明自己没错 ----
def self_test():
    checks=[]
    # 1) 恒等:盒子和自己比 → 全 0
    b=Box(10,20,30)
    mb=measure_solid(b)
    c_id=compare(mb, mb)
    checks.append(('identity_volume_pct', c_id['volume_dev_pct'], 0.0))
    checks.append(('identity_area_pct',   c_id['area_dev_pct'],   0.0))
    checks.append(('identity_bbox_maxdev',c_id['bbox_max_axis_dev_pct'], 0.0))
    # 2) 放大 10%:Box(11,22,33) vs Box(10,20,30) → 体积 +33.1%,面积 +21%,包围盒 +10%
    big=measure_solid(Box(11,22,33))
    c_sc=compare(big, mb)
    checks.append(('scale_volume_pct', c_sc['volume_dev_pct'], 33.1))
    checks.append(('scale_area_pct',   c_sc['area_dev_pct'],   21.0))
    checks.append(('scale_bbox_maxdev',c_sc['bbox_max_axis_dev_pct'], 10.0))
    passed=all(v is not None and abs(v-exp)<=0.2 for _,v,exp in checks)
    return passed, checks

# ---- 配对:真值(3D数模) ↔ AI 重建(baseline) ----
def build_pairs():
    truth_dir=None
    for root,dirs,files in os.walk(PROJ):
        if os.path.basename(root)=='3D数模':
            truth_dir=root; break
    truth={}
    if truth_dir:
        for f in os.listdir(truth_dir):
            if f.upper().endswith('.STEP') or f.upper().endswith('.STP'):
                key=nfc(os.path.splitext(f)[0])
                truth[key]=os.path.join(truth_dir,f)
    base=os.path.join(PROJ,'实验-工艺规程Loop','baseline')
    pred={}
    if os.path.isdir(base):
        for d in os.listdir(base):
            dp=os.path.join(base,d)
            mp=os.path.join(dp,'model.step')
            if os.path.isdir(dp) and os.path.exists(mp):
                pred[nfc(d)]=mp
    pairs={}
    for k in truth:
        if k in pred:
            pairs[k]={'truth':truth[k],'pred':pred[k]}
    return pairs, sorted(truth), sorted(pred)

CASE_NO={'法兰':'001','外筒':'002','定位销':'003','端盖':'004','锥杆':'008'}

def main():
    ok, checks = self_test()
    print("=== 比对器自检 ===")
    for name,got,exp in checks:
        flag='OK' if (got is not None and abs(got-exp)<=0.2) else 'FAIL'
        print(f"  [{flag}] {name}: got={got} expect≈{exp}")
    print("自检结论:", "PASS(数可信)" if ok else "FAIL(先别信数)")

    pairs, truth_keys, pred_keys = build_pairs()
    print(f"\n=== 配对 === 真值件 {truth_keys} ; 可配对 {len(pairs)} 件")

    rows=[]
    for k,paths in sorted(pairs.items(), key=lambda kv: CASE_NO.get(kv[0],'zzz')):
        t=load_step_measure(paths['truth'])
        p=load_step_measure(paths['pred'])
        cmp=compare(p,t) if (t['ok'] and p['ok']) else {'volume_dev_pct':None,'area_dev_pct':None,'bbox_axis_dev_pct':None,'bbox_max_axis_dev_pct':None}
        rows.append({'case':CASE_NO.get(k,'?'),'part':k,
                     'truth_vol':None if not t['ok'] else round(t['volume'],1),
                     'pred_vol': None if not p['ok'] else round(p['volume'],1),
                     'vol_dev_pct':cmp['volume_dev_pct'],
                     'area_dev_pct':cmp['area_dev_pct'],
                     'bbox_max_dev_pct':cmp['bbox_max_axis_dev_pct'],
                     'truth_bbox':t.get('bbox_sorted'),'pred_bbox':p.get('bbox_sorted'),
                     'pred_ok':p['ok'],'pred_error':p.get('error')})

    # 输出 CSV + MD + JSON
    docs=os.path.join(PROJ,'training_loop','docs')
    os.makedirs(docs, exist_ok=True)
    base_out=os.path.join(docs,'geometry_baseline_20260718')
    with open(base_out+'.json','w') as f:
        json.dump({'self_test_pass':ok,'self_test':checks,'rows':rows}, f, ensure_ascii=False, indent=1)
    with open(base_out+'.csv','w',newline='') as f:
        w=csv.writer(f); w.writerow(['case','part','truth_vol_mm3','pred_vol_mm3','vol_dev_%','area_dev_%','bbox_max_dev_%','pred_ok'])
        for r in rows:
            w.writerow([r['case'],r['part'],r['truth_vol'],r['pred_vol'],r['vol_dev_pct'],r['area_dev_pct'],r['bbox_max_dev_pct'],r['pred_ok']])
    md=["# 诚实几何基线 · AI 重建 vs 真实真值(2026-07-18)","",
        f"- 比对器自检:{'PASS(数可信)' if ok else 'FAIL'}",
        "- 指标均为旋转/平移不变(体积%、表面积%、轴排序包围盒%),无对齐风险。",
        "- 仅列原始偏差,不判 pass/fail(标准由后续 U6 校准)。","",
        "| case | 零件 | 真值体积 mm³ | 重建体积 mm³ | 体积偏差% | 表面积偏差% | 包围盒最大轴偏差% | 重建可读 |",
        "|---|---|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        md.append(f"| {r['case']} | {r['part']} | {r['truth_vol']} | {r['pred_vol']} | {r['vol_dev_pct']} | {r['area_dev_pct']} | {r['bbox_max_dev_pct']} | {'是' if r['pred_ok'] else '否:'+str(r['pred_error'])} |")
    open(base_out+'.md','w').write("\n".join(md)+"\n")

    print("\n=== 诚实基线表 ===")
    print(f"{'case':>4} {'零件':<6} {'真值vol':>12} {'重建vol':>12} {'体积%':>9} {'面积%':>9} {'bbox%':>8} ok")
    for r in rows:
        print(f"{r['case']:>4} {r['part']:<6} {str(r['truth_vol']):>12} {str(r['pred_vol']):>12} {str(r['vol_dev_pct']):>9} {str(r['area_dev_pct']):>9} {str(r['bbox_max_dev_pct']):>8} {r['pred_ok']}")
    print(f"\n输出:{base_out}.md / .csv / .json")

if __name__=='__main__':
    main()
