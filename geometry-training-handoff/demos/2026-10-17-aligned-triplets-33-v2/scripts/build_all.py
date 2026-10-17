#!/usr/bin/env python3
"""Bounded per-part execution. Preserve every batch's stdout/error log."""
import argparse
import concurrent.futures
import datetime
import json
from pathlib import Path
import subprocess
import sys

BASE=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cad-python',required=True)
    parser.add_argument('--timeout',type=int,default=300)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('cases',nargs='*')
    args=parser.parse_args()
    annotations={}
    for path in sorted((BASE/'scripts').glob('annotations_*.json')):
        for item in json.loads(path.read_text())['cases']:
            if item['case_id'] in annotations: raise ValueError('duplicate annotation')
            annotations[item['case_id']]=item
    chosen=args.cases or sorted(annotations)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    logs=BASE/'build_logs'/stamp; logs.mkdir(parents=True)
    def run(cid):
        command=[args.cad_python,str(BASE/'scripts/build_case.py'),cid]
        try:
            done=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=args.timeout)
            result={'case_id':cid,'exit_code':done.returncode,'timeout':False}
            output=done.stdout
        except subprocess.TimeoutExpired as error:
            result={'case_id':cid,'exit_code':None,'timeout':True}
            output=error.stdout or ''
            if isinstance(output,bytes): output=output.decode(errors='replace')
            output+='\nTIMEOUT: renderer did not finish within configured limit.\n'
        (logs/(cid+'.log')).write_text(output)
        result['log']=str((logs/(cid+'.log')).relative_to(BASE))
        if result['exit_code']!=0:
            dest=BASE/'cases'/cid; dest.mkdir(parents=True,exist_ok=True)
            old=BASE.parent/'2026-10-15-real-triplets-33-v1'/'cases'/cid
            data={'schema_version':2,'case_id':cid,'name':json.loads((old/'views.json').read_text())['part_name'],
                  'status':'build_failed','reason':'See preserved build log; no aligned training tuple is accepted.',
                  'annotation':annotations[cid],'training_ready':False,'human_acceptance':'pending',
                  'pixel_registration_status':'not_run','views':[],
                  'source_views':json.loads((old/'views.json').read_text()),
                  'legacy_geometry_validation':json.loads((old/'validation.json').read_text()),'build_result':result}
            (dest/'alignment.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result),flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results=list(pool.map(run,chosen))
    (logs/'summary.json').write_text(json.dumps({'command':sys.argv,'results':results},indent=2)+'\n')

if __name__=='__main__': main()
