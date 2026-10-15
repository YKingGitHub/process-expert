#!/usr/bin/env python3
"""Independent authoring QA. Run with CadQuery 2.5.2; not a model benchmark.

No alignment/normalization in metrics. Reference STEP is only read after the
program is executed in an empty temporary directory. Never imports the model's
pre-exported STEP. This runner executes reviewed authoring code, NOT untrusted
model output; the project's inference sandbox is unchanged.
"""
import argparse
import ast
import hashlib
import itertools
import json
import os
import runpy
import tempfile
import time
import traceback
from pathlib import Path

import cadquery as cq
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.TopTools import TopTools_ListOfShape


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_program(path):
    tree=ast.parse(path.read_text())
    issues=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            for name in node.names:
                if name.name not in ('cadquery','math'):
                    issues.append(f'unsupported import {name.name}')
        if isinstance(node,ast.ImportFrom) and node.module not in ('cadquery','math'):
            issues.append(f'unsupported import from {node.module}')
        if isinstance(node,ast.Name) and node.id in ('open','eval','exec','__import__','compile'):
            issues.append(f'forbidden name {node.id}')
        if isinstance(node,ast.Attribute) and (node.attr.startswith('import') or node.attr in ('read','read_bytes','read_text','loads','load','loadShape','makePolygon','makeShell')):
            issues.append(f'forbidden geometry / I/O attribute {node.attr}')
        if isinstance(node,ast.Constant) and isinstance(node.value,str) and any(s in node.value.lower() for s in ('iso-10303-21','dbrep_drawableshape','base64','reference.step','ground_truth.step')):
            issues.append('embedded or imported reference geometry marker')
    if issues:
        raise ValueError('; '.join(sorted(set(issues))))
    return {'status':'passed','allowed_imports':['cadquery','math'],'external_geometry_reads':False,'execution_mode':'trusted_authored_label_not_model_sandbox'}


def stats(shape):
    b=Bnd_Box(); b.SetGap(0)
    BRepBndLib.AddOptimal_s(shape.wrapped,b,False,False)
    bounds=list(b.Get())
    return {'valid':shape.isValid(),'solid_count':len(shape.Solids()),'volume_mm3':shape.Volume(),'surface_area_mm2':shape.Area(),'bounds_mm':bounds,'bbox_mm':[bounds[i+3]-bounds[i] for i in range(3)],'face_count':len(shape.Faces())}


def write_mesh(shape,path):
    bounds=stats(shape)['bbox_mm']
    vertices,triangles=shape.tessellate(max(max(bounds)*0.0008,0.03),0.12)
    data={'vertices':[[round(v.x,5),round(v.y,5),round(v.z,5)] for v in vertices],'triangles':triangles,'units':'mm','purpose':'interactive_visual_preview_not_validation_metric'}
    path.write_text(json.dumps(data,separators=(',',':')))


def checked_intersection(reference, rebuilt, reference_stats, rebuilt_stats):
    """Do not mistake an OCC failure or invalid result for measured disjointness.

    Same exact Common operation as CadQuery, with explicit completion/validity
    checks. Fixed interior probes are a contradiction test, NOT a replacement
    overlap metric and never promote a failed candidate to a geometry pass.
    """
    args=TopTools_ListOfShape(); args.Append(reference.wrapped)
    tools=TopTools_ListOfShape(); tools.Append(rebuilt.wrapped)
    operation=BRepAlgoAPI_Common(); operation.SetArguments(args); operation.SetTools(tools)
    operation.SetRunParallel(True); operation.Build()
    if not operation.IsDone():
        raise ValueError('OpenCascade Common did not complete')
    intersection=cq.Shape.cast(operation.Shape())
    if not intersection.isValid():
        raise ValueError('OpenCascade Common returned invalid geometry')
    iv=intersection.Volume()
    if iv < -1e-9:
        raise ValueError(f'OpenCascade Common returned negative volume: {iv}')
    if iv <= 1e-9:
        a=reference_stats['bounds_mm']; b=rebuilt_stats['bounds_mm']
        lo=[max(a[i],b[i]) for i in range(3)]
        hi=[min(a[i+3],b[i+3]) for i in range(3)]
        if all(x<y for x,y in zip(lo,hi)):
            for fractions in itertools.product((0.125,0.25,0.375,0.5,0.625,0.75,0.875),repeat=3):
                point=tuple(x+f*(y-x) for x,y,f in zip(lo,hi,fractions))
                if reference.isInside(point,1e-7) and rebuilt.isInside(point,1e-7):
                    raise ValueError(f'Empty Common contradicts a point inside both operands: {point}')
    return max(0.0,iv)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('case',type=Path)
    parser.add_argument('--skip-boolean',action='store_true')
    args=parser.parse_args(); case=args.case.resolve()
    out={'schema_version':1,'case_id':case.name,'cadquery_version':cq.__version__,'purpose':'GT-assisted label-authoring QA; not held-out model evaluation','coordinate_alignment':'none; original physical mm frame','thresholds':{'legacy_volume_relative':0.02,'legacy_area_relative':0.05,'legacy_sorted_bbox_relative':0.02,'additional_symmetric_difference_over_reference_volume':0.01,'additional_axis_bbox_relative':0.01},'human_acceptance':'pending','training_ready':False}
    out['validator_sha256']=digest(Path(__file__))
    started=time.time()
    try:
        model=case/'model.py'; out['model_sha256']=digest(model)
        out['program_audit']=audit_program(model)
        cwd=os.getcwd()
        try:
            with tempfile.TemporaryDirectory(prefix='cq-label-isolation-') as temp:
                os.chdir(temp)
                namespace=runpy.run_path(str(model),run_name='__triplet_validation__')
        finally:
            os.chdir(cwd)
        solid=namespace['solid']; solid=solid.val() if isinstance(solid,cq.Workplane) else solid
        if not isinstance(solid,cq.Shape): raise TypeError('solid is not a CadQuery Shape or Workplane')
        rebuilt=case/'verified_reconstructed.step'
        cq.exporters.export(solid,str(rebuilt))
        reloaded=cq.importers.importStep(str(rebuilt)).val()
        out['execution_status']='success'; out['reconstructed_sha256']=digest(rebuilt)
        reference=cq.importers.importStep(str(case/'reference.step')).val()
        out['reference_sha256']=digest(case/'reference.step')
        a=stats(reference); b=stats(reloaded)
        out['reference']=a; out['reconstructed']=b
        rel=lambda x,y:abs(y-x)/max(abs(x),1e-12)
        volume_error=rel(a['volume_mm3'],b['volume_mm3'])
        area_error=rel(a['surface_area_mm2'],b['surface_area_mm2'])
        axis_error=[rel(x,y) for x,y in zip(a['bbox_mm'],b['bbox_mm'])]
        sorted_error=[rel(x,y) for x,y in zip(sorted(a['bbox_mm']),sorted(b['bbox_mm']))]
        out['metrics']={'volume_relative_error':volume_error,'area_relative_error':area_error,'axis_bbox_relative_error':axis_error,'sorted_bbox_relative_error':sorted_error,'max_bound_position_error_mm':max(abs(x-y) for x,y in zip(a['bounds_mm'],b['bounds_mm']))}
        out['legacy_geometry_check']=bool(b['valid'] and b['solid_count']==1 and volume_error<=0.02 and area_error<=0.05 and max(sorted_error)<=0.02)
        # Visuals are generated before expensive booleans; report stays truthful
        # if a parent supervisor later marks timeout.
        write_mesh(reference,case/'reference_mesh.json')
        write_mesh(reloaded,case/'reconstructed_mesh.json')
        out['boolean_status']='running'
        (case/'validation.json').write_text(json.dumps(out,indent=2)+'\n')
        if not args.skip_boolean:
            try:
                iv=checked_intersection(reference,reloaded,a,b)
                av=a['volume_mm3']; bv=b['volume_mm3']
                if iv > min(av,bv)+max(av,bv)*1e-6:
                    raise ValueError('Boolean intersection volume exceeds either operand')
                union=av+bv-iv
                difference=max(0.0,av+bv-2*iv)
                out['metrics'].update({'intersection_volume_mm3':iv,'iou_same_frame':iv/union if union else None,'symmetric_difference_volume_mm3':difference,'symmetric_difference_over_reference_volume':difference/av})
                out['boolean_status']='success'
                out['geometry_gate_pass']=bool(out['legacy_geometry_check'] and max(axis_error)<=0.01 and difference/av<=0.01)
            except Exception as exc:
                out['boolean_status']='error'; out['geometry_gate_pass']=False
                out['error']=f'Boolean validation error: {type(exc).__name__}: {exc}'
                out['metrics'].update({k:None for k in ('intersection_volume_mm3','iou_same_frame','symmetric_difference_volume_mm3','symmetric_difference_over_reference_volume')})
        else:
            out['boolean_status']='not_run'; out['geometry_gate_pass']=False
        out['status']='geometry_gate_pass_review_pending' if out['geometry_gate_pass'] else 'needs_geometry_revision'
        if out['boolean_status']=='error': out['status']='geometry_check_error'
    except Exception as exc:
        out['status']='validation_error'; out['error']=f'{type(exc).__name__}: {exc}'
        out['traceback']=traceback.format_exc(); out['geometry_gate_pass']=False
    out['elapsed_seconds']=round(time.time()-started,3)
    (case/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out.get(k) for k in ('case_id','status','execution_status','error','elapsed_seconds')}),flush=True)
    return 1 if out.get('status')=='validation_error' else 0


if __name__=='__main__': raise SystemExit(main())
