#!/usr/bin/env python3
"""Calibrate real source pixels to the STEP projection camera, never redraw them.

Only views with explicit geometric envelope/held-out feature observations are
registered. Other views remain pose-only, not silently marked calibrated.
"""
import itertools
import hashlib
import json
import math
from pathlib import Path
from PIL import Image
from alignment_math import dot

BASE=Path(__file__).resolve().parents[1]
V1=BASE.parent/'2026-10-15-real-triplets-33-v1'

def main():
    config=json.loads((BASE/'scripts/pixel_anchors.json').read_text())
    provenance={cid:{vid:{'file':'scripts/pixel_anchors.json','sha256':hashlib.sha256((BASE/'scripts/pixel_anchors.json').read_bytes()).hexdigest(),'method':config['method']} for vid in views} for cid,views in config['cases'].items()}
    for extra in sorted((BASE/'scripts').glob('pixel_anchors_*.json')):
        extra_config=json.loads(extra.read_text())
        if extra_config.get('acceptance',config['acceptance'])!=config['acceptance']:
            raise ValueError('Extra anchor config cannot change acceptance thresholds')
        for cid,views in extra_config['cases'].items():
            current=config['cases'].setdefault(cid,{})
            for vid,annotation in views.items():
                if vid in current: raise ValueError(f'Duplicate pixel anchors: {cid}/{vid}')
                current[vid]=annotation
                provenance.setdefault(cid,{})[vid]={'file':str(extra.relative_to(BASE)), 'sha256':hashlib.sha256(extra.read_bytes()).hexdigest(),'method':extra_config.get('method',config['method']),'measurement_provenance':extra_config.get('provenance')}
    limits=config['acceptance']
    for cid,annotations in config['cases'].items():
        case=BASE/'cases'/cid; path=case/'alignment.json'
        if not path.exists(): raise FileNotFoundError(f'Build {cid} before registering pixels')
        data=json.loads(path.read_text()); scale=data['shared_pixels_per_mm']
        sv=data['source_views']; by_id={v['id']:v for v in sv['views']}
        bounds=data['reference']['bounds_mm']
        corners=list(itertools.product(*[(bounds[i],bounds[i+3]) for i in range(3)]))
        for row in data['views']:
            if row['id'] not in annotations: continue
            ann=annotations[row['id']]; view=by_id[row['id']]
            if len(ann.get('landmarks',[]))<2:
                raise ValueError(f'{cid}/{row["id"]}: need at least two independently observed landmarks')
            if len(ann['dimension_evidence_mm'])!=2 or len(ann['preview_geometry_bbox'])!=4:
                raise ValueError('Physical dimensions must have two entries and pixel bounds four')
            if row['kind']!='external' or 'canonical_camera' not in row:
                raise ValueError('Cannot pixel-register a section or unmapped view')
            src=sv['sources'][view['source_page']-1]
            old=V1/'cases'/cid
            with Image.open(old/src['preview']) as preview: pw,ph=preview.size
            rw,rh=src['upright_size']; factor=[rw/pw,rh/ph]
            bb=ann['preview_geometry_bbox']; rawbox=[bb[i]*factor[i%2] for i in range(4)]
            right=row['canonical_camera']['screen_right']; up=row['canonical_camera']['screen_up']
            uv=[[dot(right,c),dot(up,c)] for c in corners]
            mm_min=[min(p[i] for p in uv) for i in range(2)]; mm_max=[max(p[i] for p in uv) for i in range(2)]
            spans=[mm_max[i]-mm_min[i] for i in range(2)]
            widths=[rawbox[2]-rawbox[0],rawbox[3]-rawbox[1]]
            for measured,declared in zip(spans,ann['dimension_evidence_mm']):
                if abs(measured-declared)>0.01: raise ValueError(f'{cid}/{row["id"]}: physical dimension evidence disagrees with STEP')
            pixel_scales=[a/b for a,b in zip(widths,spans)]
            ppmm=sum(a*b for a,b in zip(widths,spans))/sum(b*b for b in spans)
            disagreement=abs(pixel_scales[0]-pixel_scales[1])/ppmm
            image_scale=scale/ppmm
            rawcenter=[(rawbox[i]+rawbox[i+2])/2 for i in range(2)]
            mmcenter=[(mm_min[i]+mm_max[i])/2 for i in range(2)]
            # Uniform scale only. Image y is downward; CAD camera up is upward.
            tx=512+scale*mmcenter[0]-image_scale*rawcenter[0]
            ty=512-scale*mmcenter[1]-image_scale*rawcenter[1]
            crop=view['bbox_upright_pixels']; native=old/view['native_image']
            with Image.open(native).convert('RGB') as image:
                result=image.transform((1024,1024),Image.Transform.AFFINE,
                    (1/image_scale,0,-tx/image_scale-crop[0],0,1/image_scale,-ty/image_scale-crop[1]),
                    resample=Image.Resampling.BICUBIC,fillcolor='white')
                target=case/'inputs'/f'{row["id"]}_registered.png'; target.parent.mkdir(exist_ok=True)
                result.save(target,optimize=True)
            checks=[]
            for lm in ann['landmarks']:
                raw=[lm['preview_xy'][i]*factor[i] for i in range(2)]
                observed=[image_scale*raw[0]+tx,image_scale*raw[1]+ty]
                expected=[512+scale*lm['projected_mm'][0],512-scale*lm['projected_mm'][1]]
                checks.append({**lm,'observed_output_pixel':observed,'expected_step_pixel':expected,
                               'error_pixels':math.dist(observed,expected)})
            passed=disagreement<=limits['max_axis_scale_disagreement'] and all(x['error_pixels']<=limits['max_landmark_error_output_pixels'] for x in checks)
            row['pixel_registration']={'method':provenance[cid][row['id']]['method'],'anchor_provenance':provenance[cid][row['id']],'source_preview_geometry_bbox':bb,
                'source_geometry_bbox_raw_pixels':rawbox,'physical_dimension_evidence_mm':ann['dimension_evidence_mm'],
                'source_pixels_per_mm':ppmm,'axis_scale_disagreement':disagreement,
                'raw_upright_page_to_output_pixel':[[image_scale,0,tx],[0,image_scale,ty],[0,0,1]],
                'native_crop_to_output_pixel':[[image_scale,0,tx+image_scale*crop[0]],[0,image_scale,ty+image_scale*crop[1]],[0,0,1]],
                'landmarks':checks,'thresholds':limits,'landmark_gate_pass':passed,
                'full_contour_acceptance':'not_automatically_verified','no_pixels_redrawn':True}
            row['registered_source']=str(target.relative_to(case))
            row['pair_status']='landmark_calibrated_review_pending' if passed else 'pixel_registration_failed'
        registered=[v for v in data['views'] if v.get('pixel_registration')]
        data['pixel_registration_status']='landmark_calibrated_review_pending' if registered and all(v['pixel_registration']['landmark_gate_pass'] for v in registered) else 'pixel_registration_failed'
        data['pixel_registration_coverage']={'registered_external_views':len(registered),'total_external_views':sum(v['kind']=='external' for v in data['views']),'all_external_views_registered':all(v.get('pixel_registration',{}).get('landmark_gate_pass') is True for v in data['views'] if v['kind']=='external')}
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        print(cid,[(v['id'],v['pair_status'],round(max(x['error_pixels'] for x in v['pixel_registration']['landmarks']),3)) for v in registered])

if __name__=='__main__': main()
