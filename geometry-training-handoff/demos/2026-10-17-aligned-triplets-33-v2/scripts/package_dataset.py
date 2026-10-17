#!/usr/bin/env python3
"""Package reviewed alignment candidates without upgrading their training gate."""
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

BASE=Path(__file__).resolve().parents[1]
V1=BASE.parent/'2026-10-15-real-triplets-33-v1'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(data): return (json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()

def main():
    samples=[]
    notes=json.loads((BASE/'scripts/inspection_notes.json').read_text())
    for i in range(1,34):
        cid=f'case_{i:03d}'; case=BASE/'cases'/cid; path=case/'alignment.json'
        data=json.loads(path.read_text()); source=V1/'cases'/cid
        data['alignment_review_notes']=notes.get(cid,[])
        data.setdefault('source_model_sha256',sha(source/'model.py'))
        data.setdefault('source_reference_sha256',sha(source/'reference.step'))
        # Retain source inventory even when no justified front or completed build exists.
        if not data['views']:
            by_id={v['id']:v for v in data['source_views']['views']}
            data['views']=[{**v,'source_image':f'../{V1.name}/cases/{cid}/'+by_id[v['id']]['image'],
                            'pair_status':'not_pairable','reason':data.get('reason','Unresolved')}
                           for v in data['annotation']['views']]
        if data.get('source_model_sha256') and data['source_model_sha256']!=data['legacy_geometry_validation']['model_sha256']:
            raise ValueError(cid+': old geometry validation does not match the source program')
        if data.get('source_reference_sha256') and data['source_reference_sha256']!=data['legacy_geometry_validation']['reference_sha256']:
            raise ValueError(cid+': old geometry validation does not match source STEP')
        assert data['training_ready'] is False
        if data['status']=='build_failed':
            leftovers=[p for p in case.iterdir() if p.name not in ('alignment.json',f'{cid}_alignment_candidate.zip')]
            if leftovers:
                quarantine=Path(tempfile.mkdtemp(prefix=f'cad-alignment-failed-{cid}-'))
                inventory={str(p.relative_to(case)):sha(p) for p in case.rglob('*') if p.is_file() and p.name!='alignment.json'}
                for item in leftovers: item.rename(quarantine/item.name)
                data['quarantined_attempt']={'local_directory':str(quarantine),'files_sha256':inventory,
                                            'reason':'Incomplete generated assets retained locally, excluded from published training candidates'}
        data['download']={'zip':f'cases/{cid}/{cid}_alignment_candidate.zip'}
        path.write_bytes(dump(data))
        files={'alignment.json':path,'source_views.json':source/'views.json'}
        source_map={}
        for v in data['source_views']['views']:
            target='source_views/'+v['id']+'.png'
            files[target]=source/v['image']; source_map[v['id']]=target
        if data['status']=='pose_calibrated_candidate':
            if data.get('export_coordinate_verification',{}).get('status')!='passed':
                raise ValueError(cid+': run verify_exports.py before packaging a coordinate candidate')
            for filename in ['model.py','reference.step','reconstructed.step']:
                files[filename]=case/filename
            for directory in ['renders','inputs']:
                for file in sorted((case/directory).glob('*')):
                    if file.is_file(): files[str(file.relative_to(case))]=file
        manifest={'case_id':cid,'training_ready':False,'human_acceptance':'pending',
                  'source_view_files':source_map,'files_sha256':{name:sha(file) for name,file in files.items()},
                  'notes':['Real source crops may still contain dimensions and annotations.',
                           'Only inputs/*_registered.png have an explicit pixel calibration, if present.',
                           'renders/* are synthetic checks, never replacements for missing source inputs.',
                           'A passing sparse landmark gate is not full-contour or human acceptance.',
                           'model.py and both STEP files use the same proper rigid transform. Geometry labels retain v1 quality.']}
        with zipfile.ZipFile(case/f'{cid}_alignment_candidate.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for name,file in files.items():
                info=zipfile.ZipInfo(name,date_time=(2026,10,17,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,file.read_bytes())
            archive.writestr('package_manifest.json',dump(manifest))
        samples.append(data)
    attempted=[v for s in samples for v in s['views'] if v.get('pixel_registration')]
    registered=[v for v in attempted if v['pixel_registration']['landmark_gate_pass'] is True]
    summary={'case_count':len(samples),
             'pose_calibrated_count':sum(s['status']=='pose_calibrated_candidate' for s in samples),
             'unresolved_count':sum(s['status']=='unresolved' for s in samples),
             'build_failed_count':sum(s['status']=='build_failed' for s in samples),
             'registered_case_count':sum(any(v.get('pixel_registration',{}).get('landmark_gate_pass') is True for v in s['views']) for s in samples),
             'registered_view_count':len(registered),
             'registration_attempted_view_count':len(attempted),
             'landmark_pass_view_count':len(registered),
             'training_ready_count':0,
             'legacy_geometry_pass_count':sum(s['legacy_geometry_validation']['geometry_gate_pass'] is True for s in samples)}
    dataset={'schema_version':2,'created_date':'2026-10-17','summary':summary,'samples':samples,
             'training_contract':{'unit':'mm','canvas_size':[1024,1024],
                                  'front':{'right':'+X','up':'+Y','camera_from':'+Z'},
                                  'top':{'right':'+X','up':'-Z','camera_from':'+Y'},
                                  'right_side':{'right':'-Z','up':'+Y','camera_from':'+X'},
                                  'missing_view_policy':'explicit mask; do not synthesize missing training inputs',
                                  'section_policy':'separate type; require plane/offset before matching a cut render',
                                  'geometry_transform':'same rigid transform on reference STEP and CadQuery; no mirroring or scaling'}}
    (BASE/'dataset.json').write_bytes(dump(dataset))
    release={'files_sha256':{str(p.relative_to(BASE)):sha(p) for p in sorted((BASE/'scripts').glob('*')) if p.is_file()},
             'note':'Release-time script/annotation/anchor snapshot; each successful case records its actual builder hash separately.'}
    (BASE/'release_manifest.json').write_bytes(dump(release))
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__': main()
