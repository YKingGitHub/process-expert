#!/usr/bin/env python3
"""U4 跑批状态一览 —— 读日志汇总,零成本,随时可跑。

  cd 实验-工艺规程Loop && ./.venv/bin/python ../training_loop/tools/geometry_truth/u4_status.py
  加 --ping 会额外冒烟测试模型通道(会消耗极少量 token)

判定口径(重要):
  ACCEPTED   自检收敛 + 三项指标达真值容差   ← 唯一算"成功"
  NOT_ACC    跑完了但没达标                 ← 真实能力数据
  TECH_FAIL  网络/额度/权限中断             ← **不作能力结论**,不计入成绩
  未运行      还没跑过
"""
import os, sys, json, glob, subprocess, datetime

GT = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(GT, 'u4_runs')
PARTS = [('端盖', 'end_cover'), ('外筒', 'hollow_tube'),
         ('定位销', 'locating_pin'), ('锥杆', 'tapered_rod')]


def proc_alive():
    try:
        out = subprocess.run(['pgrep', '-fl', 'u4_pipeline.py'],
                             capture_output=True, text=True).stdout.strip()
        return [l for l in out.splitlines() if 'pgrep' not in l]
    except Exception:
        return []


def summarize(part):
    p = os.path.join(RUNS, f'{part}_u4_log.json')
    if not os.path.exists(p):
        return dict(verdict='未运行', attempts=0, detail='')
    try:
        d = json.load(open(p))
    except Exception as e:
        return dict(verdict='日志损坏', attempts=0, detail=str(e)[:60])
    n = len(d.get('attempts', []))
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%H:%M:%S')
    if d.get('tech_fail'):
        return dict(verdict='TECH_FAIL', attempts=n, ts=mtime,
                    detail=str(d['tech_fail'])[:90] + '  ←不作能力结论')
    if d.get('accepted'):
        f = d.get('final', {}); dev = f.get('dev_vs_truth', {})
        return dict(verdict='ACCEPTED', attempts=n, ts=mtime,
                    detail=f"体积{dev.get('vol')}% 面积{dev.get('area')}% bbox{dev.get('bbox')}")
    # 未达标:给出最后一轮卡在哪
    last = d['attempts'][-1] if n else {}
    if last.get('error'):
        why = last['error'][:80]
    elif last.get('violations'):
        why = last['violations'][0][:80]
    elif last.get('self_check'):
        why = last['self_check'][0][:80]
    elif last.get('dev_vs_truth'):
        dv = last['dev_vs_truth']
        why = f"体积{dv.get('vol')}% 面积{dv.get('area')}% bbox{dv.get('bbox')}"
    else:
        why = ''
    return dict(verdict='NOT_ACC', attempts=n, ts=mtime, detail=why)


def main():
    print(f"===== U4 状态  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    alive = proc_alive()
    print(f"运行中进程:{'是 — ' + alive[0][:70] if alive else '否(已全部结束或未启动)'}\n")
    print(f"{'零件':6} {'判定':10} {'轮次':>4} {'更新':>9}  详情")
    print('-' * 100)
    counts = {}
    for cn, fam in PARTS:
        s = summarize(cn)
        counts[s['verdict']] = counts.get(s['verdict'], 0) + 1
        print(f"{cn:6} {s['verdict']:10} {s['attempts']:>4} {s.get('ts',''):>9}  {s['detail']}")
    print('-' * 100)
    acc = counts.get('ACCEPTED', 0)
    print(f"成功 {acc}/4   未达标 {counts.get('NOT_ACC',0)}   "
          f"技术故障 {counts.get('TECH_FAIL',0)}(不计成绩)   未跑 {counts.get('未运行',0)}")

    if '--ping' in sys.argv:
        print('\n--- 通道冒烟 ---')
        sys.path.insert(0, '/Users/macsean/Desktop/AI 工艺/实验-工艺规程Loop')
        for role in ('assign', 'digitize'):
            try:
                from src.providers import call_model
                r = call_model(role, '只回复两个字:收到', timeout=90)
                print(f'  {role:9} OK  {r[:20]!r}')
            except Exception as e:
                print(f'  {role:9} 失败  {type(e).__name__}: {str(e)[:80]}')


if __name__ == '__main__':
    main()
