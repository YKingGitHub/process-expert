#!/usr/bin/env python3
"""Build a separate, reversible training-coordinate candidate for one part.

No original files are changed. Camera annotations are manually/agent authored,
not an automatic recognition result. Source image registration is a separate
gate; successful CAD transforms do not mean the training tuple is accepted.
"""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import runpy
import tempfile
import time

import cadquery as cq
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepLib import BRepLib
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from cadquery.occ_impl.exporters.svg import getPaths, TOLERANCE
from alignment_math import CANONICAL_CAMERAS, axis_angle, basis, camera_payload, determinant, mv, pixel_matrix, point, rigid_transform

BASE=Path(__file__).resolve().parents[1]
V1=BASE.parent/'2026-10-15-real-triplets-33-v1'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def stats(shape):
    box=Bnd_Box(); box.SetGap(0); BRepBndLib.AddOptimal_s(shape.wrapped,box,False,False)
    b=list(box.Get())
    return {'valid':shape.isValid(),'solid_count':len(shape.Solids()),'volume_mm3':shape.Volume(),
            'area_mm2':shape.Area(),'bounds_mm':b,'bbox_mm':[b[i+3]-b[i] for i in range(3)]}

def execute(path):
    old=os.getcwd()
    try:
        with tempfile.TemporaryDirectory(prefix='aligned-cq-') as temp:
            os.chdir(temp); ns=runpy.run_path(str(path.resolve()),run_name='__alignment_validation__')
    finally: os.chdir(old)
    solid=ns['solid']
    return solid.val() if isinstance(solid,cq.Workplane) else solid

def project(shape,right,up):
    rows=basis(right,up)
    algorithm=HLRBRep_Algo(); algorithm.Add(shape.wrapped)
    coordinate=gp_Ax2(gp_Pnt(0,0,0),gp_Dir(*rows[2]),gp_Dir(*rows[0]))
    algorithm.Projector(HLRAlgo_Projector(coordinate)); algorithm.Update(); algorithm.Hide()
    extractor=HLRBRep_HLRToShape(algorithm)
    def collect(names):
        result=[]
        for name in names:
            shape=getattr(extractor,name)()
            if not shape.IsNull():
                BRepLib.BuildCurves3d_s(shape,TOLERANCE); result.append(cq.Shape(shape))
        return result
    visible=collect(['VCompound','Rg1LineVCompound','OutLineVCompound'])
    hidden=collect(['HCompound','OutLineHCompound'])
    hidden_paths,visible_paths=getPaths(visible,hidden)
    return {'visible':visible_paths,'hidden':hidden_paths}

def save_svg(path,paths,scale,title):
    # Same millimetres-to-pixel scale and center across all views/operands.
    visible=''.join(f'<path d="{html.escape(p,quote=True)}"/>' for p in paths['visible'])
    hidden=''.join(f'<path d="{html.escape(p,quote=True)}"/>' for p in paths['hidden'])
    content=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
<title>{html.escape(title)}</title><rect width="1024" height="1024" fill="white"/>
<g transform="translate(512,512) scale({scale},{-scale})" fill="none" stroke-linecap="round" stroke-linejoin="round">
<g stroke="#a1a1aa" stroke-width="{0.9/scale}" stroke-dasharray="{5/scale},{4/scale}">{hidden}</g>
<g stroke="#162f40" stroke-width="{1.6/scale}">{visible}</g></g></svg>'''
    path.write_text(content)

def load_annotations():
    cases={}
    for p in sorted((BASE/'scripts').glob('annotations_*.json')):
        for row in json.loads(p.read_text())['cases']:
            if row['case_id'] in cases: raise ValueError('duplicate case annotation')
            cases[row['case_id']]=row
    return cases

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('case_id'); args=parser.parse_args()
    case_id=args.case_id; annotation=load_annotations()[case_id]
    dest=BASE/'cases'/case_id; dest.mkdir(parents=True,exist_ok=True)
    source=V1/'cases'/case_id
    source_views=json.loads((source/'views.json').read_text())
    old_validation=json.loads((source/'validation.json').read_text())
    out={'schema_version':2,'case_id':case_id,'name':source_views['part_name'],
         'annotation':annotation,'status':'unresolved','training_ready':False,'human_acceptance':'pending',
         'source_dataset':'2026-10-15-real-triplets-33-v1','source_views':source_views,
         'source_model_sha256':sha(source/'model.py'),'source_reference_sha256':sha(source/'reference.step'),
         'legacy_geometry_validation':old_validation,'coordinate_policy':'proper rigid rotation and translation only; mm retained; no mirror or scale',
         'pixel_registration_status':'not_run','views':[]}
    start=time.monotonic()
    if annotation.get('status')=='unresolved' or not annotation.get('front_basis'):
        out['reason']='No justified external front-view camera; excluded from aligned training candidates'
        write_json(dest/'alignment.json',out); print(case_id,'unresolved',flush=True); return
    R=basis(annotation['front_basis']['right'],annotation['front_basis']['up'])
    reference=cq.importers.importStep(str(source/'reference.step')).val()
    original=stats(reference); center=[(original['bounds_mm'][i]+original['bounds_mm'][i+3])/2 for i in range(3)]
    transform,inverse=rigid_transform(R,center)
    out['raw_to_canonical']=transform; out['canonical_to_raw']=inverse
    out['rotation_determinant']=determinant(R)
    out['canonical_frame']={'X':'drawing-front right','Y':'drawing-front up','Z':'towards front-view camera'}
    axis,degrees=axis_angle(R); translation=[row[3] for row in transform[:3]]
    new_reference=reference.rotate((0,0,0),axis,degrees).translate(translation)
    raw_code=(source/'model.py').read_text()
    extra='\n\n# Training-coordinate calibration: proper rigid transform, millimetres retained.\n'
    extra+='RAW_TO_CANONICAL = '+repr(transform)+'\n'
    extra+='_raw_shape = solid.val() if isinstance(solid, cq.Workplane) else solid\n'
    extra+='solid = _raw_shape.rotate((0, 0, 0), '+repr(axis)+', '+repr(degrees)+').translate('+repr(translation)+')\n'
    (dest/'model.py').write_text(raw_code.rstrip()+extra)
    rebuilt=execute(dest/'model.py')
    cq.exporters.export(new_reference,str(dest/'reference.step'))
    cq.exporters.export(rebuilt,str(dest/'reconstructed.step'))
    # All displayed projections are from these exported/reloaded STEP files.
    ref=cq.importers.importStep(str(dest/'reference.step')).val()
    rec=cq.importers.importStep(str(dest/'reconstructed.step')).val()
    ref_stats=stats(ref); rec_stats=stats(rec)
    raw_stats=old_validation['reconstructed']
    invariants={'reference_volume_relative_change':abs(ref_stats['volume_mm3']/original['volume_mm3']-1),
                'reconstructed_volume_relative_change':abs(rec_stats['volume_mm3']/raw_stats['volume_mm3']-1),
                'reference_area_relative_change':abs(ref_stats['area_mm2']/original['area_mm2']-1),
                'reconstructed_area_relative_change':abs(rec_stats['area_mm2']/raw_stats['surface_area_mm2']-1),
                'transform_roundtrip_error_mm':max(abs(x-y) for v in reference.Vertices() for x,y in zip(v.toTuple(),point(inverse,point(transform,v.toTuple()))))}
    if not(ref_stats['valid'] and rec_stats['valid'] and ref_stats['solid_count']==rec_stats['solid_count']==1):
        raise ValueError('Rigid transform produced an invalid/non-single solid')
    if max(v for k,v in invariants.items() if k.endswith('change'))>1e-6 or invariants['transform_roundtrip_error_mm']>1e-6:
        raise ValueError('Rigid transform invariant failed')
    scale=800/max(ref_stats['bbox_mm'])
    out.update(status='pose_calibrated_candidate',reference=ref_stats,reconstructed=rec_stats,
               rigid_invariants=invariants,shared_pixels_per_mm=scale,canvas_size=[1024,1024],
               reference_sha256=sha(dest/'reference.step'),reconstructed_sha256=sha(dest/'reconstructed.step'),
               model_sha256=sha(dest/'model.py'),builder_sha256=sha(Path(__file__)))
    paths_dir=dest/'renders'; paths_dir.mkdir(exist_ok=True)
    projections={}; projection_cache={}
    def cached_projection(label, shape, right, up):
        key=(label,tuple(right),tuple(up))
        if key not in projection_cache:
            projection_cache[key]=project(shape,right,up)
        return projection_cache[key]
    for role,camera in CANONICAL_CAMERAS.items():
        if role not in ('front','top','right_side'): continue
        for label,shape in [('reference',ref),('reconstructed',rec)]:
            paths=cached_projection(label,shape,camera['right'],camera['up'])
            target=paths_dir/f'{role}_{label}.svg'; save_svg(target,paths,scale,f'{case_id} {role} {label}')
        projections[role]={'camera':camera_payload(camera['right'],camera['up']),
                           'canonical_mm_to_pixel':pixel_matrix(camera['right'],camera['up'],scale),
                           'reference':f'renders/{role}_reference.svg','reconstructed':f'renders/{role}_reconstructed.svg',
                           'synthetic_reference_only':True}
    out['canonical_projections']=projections
    supplied=set()
    for item in annotation['views']:
        row=dict(item); row['source_image']=f'../{V1.name}/cases/{case_id}/'+next(v['image'] for v in source_views['views'] if v['id']==item['id'])
        row['pair_status']='not_pairable'
        if item.get('kind')=='external' and item.get('raw_right') is not None and item.get('raw_up') is not None:
            right=mv(R,item['raw_right']); up=mv(R,item['raw_up']); basis(right,up)
            row['canonical_camera']=camera_payload(right,up)
            row['canonical_mm_to_pixel']=pixel_matrix(right,up,scale)
            row['pair_status']='pose_only_pixel_registration_pending'
            for label,shape in [('reference',ref),('reconstructed',rec)]:
                paths=cached_projection(label,shape,right,up)
                name=f'{item["id"]}_{label}.svg'; save_svg(paths_dir/name,paths,scale,f'{case_id} source-matched {item["id"]} {label}')
                row[label+'_render']=f'renders/{name}'
            if item.get('canonical_role') in ('front','top','right_side'): supplied.add(item['canonical_role'])
        elif item.get('kind')=='section':
            row['reason']='Section plane/offset not calibrated; no external render is substituted for a section'
        else: row['reason']='No supported external orthographic camera for this annotation'
        out['views'].append(row)
    out['input_view_mask']={role:role in supplied for role in ('front','top','right_side')}
    out['elapsed_seconds']=round(time.monotonic()-start,3)
    write_json(dest/'alignment.json',out)
    print(case_id,out['status'],out['input_view_mask'],flush=True)

if __name__=='__main__': main()
