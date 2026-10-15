#!/usr/bin/env python3
"""Run independent validation in bounded per-case subprocesses; log every run."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import time

BASE=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(); p.add_argument('--cad-python',required=True)
    p.add_argument('--cases',nargs='*'); p.add_argument('--workers',type=int,default=3)
    p.add_argument('--timeout',type=int,default=240)
    args=p.parse_args()
    cases=args.cases or [f'case_{i:03d}' for i in range(1,34)]
    def run(cid):
        case=BASE/'cases'/cid
        attempt=case/'validation_attempts'; attempt.mkdir(exist_ok=True)
        key=time.strftime('%Y%m%dT%H%M%S')+'-'+str(time.time_ns()%1000000000)
        start=time.time()
        command=[args.cad_python,str(BASE/'scripts'/'validate_case.py'),str(case)]
        # Never let a timeout before the first checkpoint reuse a previous
        # model's metrics. Existing measured attempts remain in the audit log.
        pending={'case_id':cid,'status':'validation_running','geometry_gate_pass':False,'training_ready':False}
        model=case/'model.py'
        if model.exists():
            pending['model_sha256']=hashlib.sha256(model.read_bytes()).hexdigest()
        (case/'validation.json').write_text(json.dumps(pending,indent=2)+'\n')
        try:
            proc=subprocess.run(command,text=True,capture_output=True,timeout=args.timeout)
            log=proc.stdout+'\n'+proc.stderr
            status={'returncode':proc.returncode,'seconds':time.time()-start}
        except subprocess.TimeoutExpired as exc:
            log=(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout,bytes) else (exc.stdout or '')
            status={'timeout':True,'seconds':time.time()-start}
            path=case/'validation.json'
            result=json.loads(path.read_text()) if path.exists() else {'case_id':cid}
            result.update(status='validation_timeout',geometry_gate_pass=False,training_ready=False,timeout_seconds=args.timeout)
            path.write_text(json.dumps(result,indent=2)+'\n')
        (attempt/f'{key}.log').write_text(log)
        (attempt/f'{key}.json').write_text(json.dumps(status,indent=2)+'\n')
        if (case/'validation.json').exists():
            (attempt/f'{key}-result.json').write_bytes((case/'validation.json').read_bytes())
        print(cid,status,flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(run,cases))


if __name__=='__main__': main()
