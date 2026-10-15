#!/usr/bin/env python3
"""Agent-authored drawing-region annotations; deterministic crop/pad (not a detector).

The source STEP is never read here. Boxes are normalized against the displayed
upright source page, then recorded in pixels. Dimensions, section hatching and
hidden/center lines inside each box are retained. No geometric redrawing.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parents[1]
# (page, role, source label, normalized crop, parent source label)
ANNOTATIONS = {}


def add(case, page, role, label, box, parent=None):
    ANNOTATIONS.setdefault(f'case_{case:03d}', []).append((page, role, label, box, parent))


# Simple sheets: view names are provisional functional roles, not verified axes.
simple = {
6: [('front','Longitudinal',(.14,.13,.49,.43)),('side','End',(.53,.13,.72,.43))],
7: [('front','Longitudinal',(.12,.15,.55,.38)),('side','End',(.58,.15,.74,.38))],
8: [('front','Plate face',(.25,.14,.50,.67)),('side','Thickness',(.53,.18,.70,.64))],
9: [('front','Longitudinal',(.15,.17,.48,.43)),('side','End',(.61,.16,.77,.44))],
10:[('front','Bent tube',(.14,.25,.57,.47)),('side','End',(.67,.25,.78,.47))],
11:[('front','Mounting face',(.15,.06,.55,.48)),('side','Side',(.57,.10,.83,.52)),('top','Plan',(.21,.50,.53,.71))],
12:[('front','Profile',(.17,.06,.46,.43)),('side','Side',(.61,.12,.76,.44)),('top','Plan',(.20,.45,.47,.73))],
13:[('front','End',(.10,.11,.48,.66)),('section','A-A',(.51,.12,.90,.68))],
14:[('front','Fork face',(.12,.07,.42,.55)),('section','Axial section',(.44,.03,.70,.53)),('top','Plan',(.14,.54,.43,.74)),('section','A-A',(.50,.54,.80,.76))],
15:[('front','Fork / rod',(.13,.13,.69,.46)),('top','Plan',(.19,.52,.67,.74))],
16:[('front','Longitudinal - broken',(.17,.17,.59,.57)),('side','End',(.65,.26,.89,.57))],
17:[('front','Fork face',(.16,.07,.56,.70)),('side','Side',(.57,.10,.81,.68))],
18:[('front','Plate face',(.14,.13,.74,.65)),('side','Thickness',(.75,.13,.87,.61))],
19:[('front','End',(.14,.07,.66,.65)),('side','Side',(.70,.04,.88,.65))],
20:[('front','Gear end',(.10,.10,.46,.50)),('section','A-A',(.45,.07,.79,.57)),('detail','I',(.71,.47,.91,.69)),('specification','Gear parameters',(.86,.17,.985,.38))],
21:[('front','Pin - thread symbolic',(.13,.10,.67,.48)),('side','End',(.67,.19,.86,.44)),('section','B-B',(.14,.47,.60,.72))],
22:[('front','End',(.10,.11,.44,.58)),('section','A-A',(.49,.06,.88,.63))],
23:[('front','Shaft - broken',(.16,.12,.75,.57))],
24:[('front','Plate face',(.21,.16,.62,.61)),('side','Thickness',(.71,.14,.88,.62))],
25:[('front','Sprocket face',(.13,.08,.51,.61)),('section','B-B',(.55,.07,.77,.67)),('specification','Chain parameters',(.81,.19,.985,.42))],
26:[('front','Sprocket face',(.12,.14,.49,.61)),('section','B-B',(.49,.10,.73,.64)),('specification','Chain parameters',(.80,.18,.96,.42))],
27:[('front','Sprocket face',(.16,.15,.53,.62)),('section','B-B',(.58,.15,.78,.65)),('specification','Chain parameters',(.80,.16,.96,.37))],
28:[('front','Sprocket face',(.16,.10,.54,.65)),('section','B-B',(.56,.12,.79,.67)),('specification','Chain parameters',(.82,.20,.97,.40))],
29:[('front','Plate face',(.24,.19,.52,.58)),('side','Thickness',(.59,.22,.66,.57))],
30:[('front','Flange face',(.24,.19,.50,.55)),('side','Thickness',(.61,.21,.72,.54))],
31:[('front','Flange face',(.19,.21,.44,.60)),('side','Thickness',(.58,.20,.69,.53))],
32:[('front','Gasket face',(.19,.22,.49,.61)),('side','Thickness',(.56,.22,.64,.56))],
33:[('front','Plate face',(.11,.13,.76,.39)),('section','A-A',(.12,.45,.66,.61))],
}
for case, views in simple.items():
    for role,label,box in views:
        add(case,1,role,label,box, views[0][1] if role in ('section','detail') else None)

# Multi-sheet castings: preserve every section/detail group as well as main views.
# Some densely interleaved section callouts cannot be separated losslessly in v1.
add(1,1,'side','End / side',(.03,.08,.30,.69))
add(1,1,'front','Main sectional elevation',(.28,.03,.90,.77))
add(1,1,'section','H-H',(.43,.80,.55,.96),'Main sectional elevation')
for role,label,box in [
 ('auxiliary','B',(.05,.06,.36,.55)),('detail','K-K / C',(.42,.06,.63,.35)),
 ('section','A-A',(.65,.05,.93,.38)),('section','B-B',(.08,.61,.32,.89)),
 ('section','C-C',(.39,.43,.68,.81))]: add(1,2,role,label,box,'Main sectional elevation')
for label,box in [('D-D',(.09,.06,.32,.49)),('E-E',(.35,.09,.60,.47)),('F-F',(.62,.04,.94,.49)),('P-P',(.04,.56,.34,.93)),('G-G',(.34,.58,.59,.88))]:
    add(1,3,'section',label,box,'Main sectional elevation')
for role,label,box in [('detail','A',(.025,.06,.40,.46)),('detail','B',(.42,.05,.94,.63)),('section','J-J',(.04,.48,.53,.96)),('section','M-M',(.62,.64,.77,.78)),('auxiliary','N-N',(.78,.64,.96,.78))]:
    add(1,4,role,label,box,'Main sectional elevation')
for role,label,box in [('detail','C',(.04,.04,.43,.49)),('detail','D',(.53,.03,.96,.48)),('detail','F',(.025,.50,.24,.89)),('detail','E',(.25,.48,.65,.86)),('section','O-O',(.64,.55,.91,.79)),('detail','V',(.24,.88,.39,.97))]:
    add(1,5,role,label,box,'Main sectional elevation')
add(2,1,'front','Elevation',(.28,.07,.78,.39))
add(2,1,'section','Longitudinal section',(.28,.40,.77,.77),'Elevation')
add(2,1,'section','Left sections',(.03,.06,.28,.75),'Elevation')
add(2,1,'side','Right end / detail',(.77,.44,.94,.82),'Elevation')
# Dense detail sheet preserved without title blocks; each region remains a group.
for label,box in [('Upper detail row',(.03,.03,.95,.27)),('Second detail row',(.03,.27,.95,.48)),('Lower-left sections',(.03,.52,.24,.91)),('Middle sections',(.24,.51,.75,.76)),('Lower sections',(.26,.76,.81,.95)),('Right details',(.75,.51,.95,.80))]:
    add(2,2,'detail_group',label,box,'Elevation')
add(3,1,'front','Elevation',(.28,.09,.82,.41))
add(3,1,'top','Plan',(.28,.44,.73,.62))
for role,label,box in [('detail','M',(.04,.06,.23,.37)),('section','F-F / View D',(.02,.44,.28,.67)),('section','L-L',(.82,.40,.96,.60)),('auxiliary','B',(.80,.62,.92,.80))]: add(3,1,role,label,box,'Elevation')
add(4,1,'front','Elevation',(.03,.10,.64,.42))
add(4,1,'top','Plan',(.12,.48,.65,.64))
for role,label,box in [('section','F-F',(.02,.48,.15,.67)),('detail_group','Upper end / sections',(.66,.09,.98,.44)),('detail_group','Lower sections',(.65,.44,.87,.61))]:add(4,1,role,label,box,'Elevation')
# case_005 source PDF scans are portrait and text is sideways: 90 deg CW upright.
add(5,1,'front','Elevation',(.31,.13,.95,.44))
add(5,1,'section','Longitudinal section',(.33,.45,.91,.74),'Elevation')
add(5,1,'side','End',(.045,.13,.29,.43))
add(5,1,'detail','K',(.05,.46,.125,.58),'Elevation')
add(5,1,'detail','L',(.16,.48,.29,.58),'Elevation')
for role,label,box in [
 ('section','A-A',(.04,.07,.15,.21)),('section','B-B',(.18,.07,.29,.22)),('section','C-C',(.30,.08,.40,.24)),
 ('section','D-D',(.41,.12,.60,.31)),('section','E-E',(.04,.23,.29,.47)),('section','F-F',(.30,.26,.45,.52)),
 ('section','G-G',(.45,.31,.70,.54)),('section','H-H',(.78,.39,.90,.59)),('detail','A',(.03,.45,.30,.69)),
 ('detail','B',(.31,.54,.44,.70)),('detail','C',(.45,.56,.68,.75)),('detail','M',(.62,.39,.81,.60)),
 ('detail','D',(.035,.66,.31,.89)),('detail','E',(.30,.77,.42,.90)),('detail','F',(.43,.67,.63,.91)),
 ('detail','H',(.58,.73,.71,.91)),('auxiliary','A-A',(.67,.59,.81,.77)),('auxiliary','B-B',(.79,.57,.97,.79))]:
    add(5,2,role,label,box,'Elevation')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,required=True)
    args=parser.parse_args()
    data=json.loads((args.data/'inference_manifest.json').read_text())
    total=0
    for sample in data['samples']:
        cid=sample['id']; case=BASE/'cases'/cid
        views_dir=case/'views'; views_dir.mkdir(parents=True,exist_ok=True)
        source_dir=case/'source'; source_dir.mkdir(exist_ok=True)
        pages=[]; source_records=[]
        for i,(image_path,pdf_path) in enumerate(zip(sample['images'],sample['source_pdfs']),1):
            image=Image.open(image_path).convert('RGB')
            original_size=image.size
            if cid=='case_005': image=image.transpose(Image.Transpose.ROTATE_270)
            pages.append(image)
            preview=image.copy(); preview.thumbnail((1800,1800))
            preview.save(source_dir/f'page_{i:02d}.webp',quality=90)
            pdf_dest=source_dir/f'page_{i:02d}.pdf'; shutil.copyfile(pdf_path,pdf_dest)
            source_records.append({'page':i,'pdf':f'source/{pdf_dest.name}','pdf_sha256':sha(pdf_dest),'preview':f'source/page_{i:02d}.webp','original_size':original_size,'upright_size':image.size,'rotation_clockwise_degrees':90 if cid=='case_005' else 0})
        items=[]
        for i,(page,role,label,box,parent) in enumerate(ANNOTATIONS[cid],1):
            image=pages[page-1]; w,h=image.size
            pixels=[round(box[0]*w),round(box[1]*h),round(box[2]*w),round(box[3]*h)]
            crop=image.crop(pixels)
            native=f'views/view_{i:02d}_native.png'; crop.save(case/native,optimize=True)
            scale=min(976/crop.width,936/crop.height)
            resized=crop.resize((max(1,round(crop.width*scale)),max(1,round(crop.height*scale))),Image.Resampling.LANCZOS)
            canvas=Image.new('RGB',(1024,1024),'white')
            offset=((1024-resized.width)//2,64+(936-resized.height)//2)
            canvas.paste(resized,offset)
            draw=ImageDraw.Draw(canvas)
            font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
            draw.text((24,16),f'{role.upper()} | {label}',fill='#334155',font=font)
            standard=f'views/view_{i:02d}.png'; canvas.save(case/standard,optimize=True)
            items.append({'id':f'view_{i:02d}','role':role,'label':label,'source_page':page,'bbox_upright_normalized':box,'bbox_upright_pixels':pixels,'native_image':native,'image':standard,'canvas_size':[1024,1024],'resize_scale_px_per_source_px':scale,'padding_xy':offset,'source_to_canvas_matrix':[[scale,0,offset[0]-pixels[0]*scale],[0,scale,offset[1]-pixels[1]*scale],[0,0,1]],'parent_source_label':parent,'orientation_status':'provisional_agent_annotation','gt_used_for_crop':False})
        # Three explicit slots; sections stay additional views, never fill a missing slot.
        slots={r:next((v['id'] for v in items if v['role']==r),None) for r in ['front','top','side']}
        thumb=Image.new('RGB',(1536,512),'#e9edf2'); draw=ImageDraw.Draw(thumb)
        font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
        for j,(role,vid) in enumerate(slots.items()):
            if vid:
                v=next(v for v in items if v['id']==vid)
                im=Image.open(case/v['image']); im.thumbnail((512,512)); thumb.paste(im,(j*512,0))
            else:
                draw.text((j*512+30,220),f'{role.upper()}: not supplied',font=font,fill='#64748b')
        thumb.save(case/'structured_views.webp',quality=92)
        record={'schema_version':1,'case_id':cid,'part_name':sample['name'],'annotation_method':'agent_manual_source_image_region_annotation','purpose':'label_authoring_not_heldout_evaluation','sources':source_records,'views':items,'standard_slots':slots,'extra_view_ids':[v['id'] for v in items if v['role'] not in slots],'projection_convention':'unverified','axis_mapping_to_step':None,'shared_physical_pixel_scale':False,'crop_policy':'uniform 1024 square per view; aspect ratio preserved; source crop and inverse mapping retained; dimensions retained; independent fitting does not imply equal mm per pixel','review_status':'pending_human_acceptance','gaps':['View roles and relationships are provisional; review source pages.','Pixel crop removes surrounding context; source PDFs retained for tolerances, materials and revision checks.','Section/detail groups on dense legacy sheets need further splitting.' ] if int(cid[-3:])<=5 else ['View roles and projection convention need human confirmation.','Source PDFs retained for manufacturing notes and revision checks.'],'annotation_gt_leakage':False}
        (case/'views.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        total+=len(items)
    print(json.dumps({'cases':len(data['samples']),'source_pages':sum(len(s['images']) for s in data['samples']),'view_regions':total}))


if __name__=='__main__': main()
