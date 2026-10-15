#!/usr/bin/env python3
"""Build review manifests and per-part downloads from measured outputs only."""
import hashlib
import json
from pathlib import Path
import zipfile

BASE=Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    samples=[]
    for case in sorted((BASE/'cases').glob('case_*')):
        views=json.loads((case/'views.json').read_text())
        authoring=json.loads((case/'authoring.json').read_text())
        validation=json.loads((case/'validation.json').read_text())
        models=[case/'model.py',case/'reference.step',case/'verified_reconstructed.step']
        if not all(p.is_file() for p in models): raise FileNotFoundError(f'Incomplete candidate triplet: {case.name}')
        for path, key in zip(models, ('model_sha256', 'reference_sha256', 'reconstructed_sha256')):
            if sha(path) != validation.get(key):
                raise ValueError(f'{case.name}: stale validation for {path.name}; rerun independent validation')
        if validation.get('execution_status') != 'success' or validation.get('status') in ('validation_error', 'pending'):
            raise ValueError(f'{case.name}: incomplete independent validation')
        if validation.get('boolean_status') not in ('success','error'):
            raise ValueError(f'{case.name}: geometry Boolean check did not finish')
        if validation.get('boolean_status') == 'error' and (not validation.get('error') or validation.get('geometry_gate_pass')):
            raise ValueError(f'{case.name}: Boolean failure must be disclosed and cannot pass')
        # Full original PDFs remain in the local source corpus. Preview and
        # provenance hashes are published; no misleading PDF download links.
        for src in views['sources']:
            src['original_pdf_local_only']=True
        (case/'views.json').write_text(json.dumps(views,ensure_ascii=False,indent=2)+'\n')
        files=[case/'model.py',case/'reference.step',case/'verified_reconstructed.step',case/'authoring.json',case/'validation.json',case/'views.json',case/'structured_views.webp']
        files += [case/v[key] for v in views['views'] for key in ('image','native_image')]
        files += [case/s['preview'] for s in views['sources']]
        files += sorted((case/'validation_attempts').glob('*'))
        hashes={str(p.relative_to(case)):sha(p) for p in files}
        manifest={'case_id':case.name,'units':'mm','triplet':{'input_views':'views.json','cadquery':'model.py','output_step':'reconstructed.step'},'independent_reference_step':'reference.step','output_step_source':'verified_reconstructed.step; independently executed model.py','training_ready':False,'acceptance_status':'pending','gt_assisted_code_authoring':True,'source_pdf_included':False,'sha256':{('reconstructed.step' if k=='verified_reconstructed.step' else k):v for k,v in hashes.items()}}
        (case/'triplet.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        files.append(case/'triplet.json')
        with zipfile.ZipFile(case/'triplet.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for p in files:
                name='reconstructed.step' if p.name=='verified_reconstructed.step' else str(p.relative_to(case))
                info=zipfile.ZipInfo(case.name+'/'+name,date_time=(2026,10,15,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,p.read_bytes(),compresslevel=9)
        # Full authoring metadata is displayed as JSON to avoid omitting any
        # agent's limitations merely because authoring schemas differ.
        samples.append({'id':case.name,'name':views['part_name'],'source_page_count':len(views['sources']),'views':views,'authoring':authoring,'authoring_display':json.dumps(authoring,ensure_ascii=False,indent=2),'validation':validation,'triplet':manifest,'download':f'cases/{case.name}/triplet.zip','download_sha256':sha(case/'triplet.zip')})
    if len(samples) != 33:
        raise ValueError(f'Expected exactly 33 parts, found {len(samples)}')
    summary={'case_count':len(samples),'source_page_count':sum(s['source_page_count'] for s in samples),'view_region_count':sum(len(s['views']['views']) for s in samples),'execution_success_count':sum(s['validation'].get('execution_status')=='success' for s in samples),'geometry_gate_pass_count':sum(bool(s['validation'].get('geometry_gate_pass')) for s in samples),'legacy_check_pass_count':sum(bool(s['validation'].get('legacy_geometry_check')) for s in samples),'geometry_boolean_error_count':sum(s['validation'].get('boolean_status')=='error' for s in samples),'geometry_boolean_error_cases':[s['id'] for s in samples if s['validation'].get('boolean_status')=='error'],'human_accepted_count':0,'training_ready_count':0,'purpose':'GT-assisted label authoring / development dataset, NOT model benchmark','geometry_pass_cases':[s['id'] for s in samples if s['validation'].get('geometry_gate_pass')],'geometry_revision_or_unverified_cases':[s['id'] for s in samples if not s['validation'].get('geometry_gate_pass')]}
    (BASE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (BASE/'dataset.json').write_text(json.dumps({'schema_version':1,'dataset_id':'real-triplets-33-v1','created':'2026-10-15','summary':summary,'samples':samples},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
