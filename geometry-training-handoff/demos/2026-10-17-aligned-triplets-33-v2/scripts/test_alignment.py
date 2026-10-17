"""Pure-Python contract and on-disk release checks; no CAD/GPU dependency."""
import hashlib
import itertools
import json
import math
from pathlib import Path
import unittest
import zipfile
from alignment_math import CANONICAL_CAMERAS, axis_angle, basis, cross, determinant, dot, mv, pixel_matrix, point, rigid_transform

BASE=Path(__file__).resolve().parents[1]
V1=BASE.parent/'2026-10-15-real-triplets-33-v1'

class MathTests(unittest.TestCase):
    def test_all_24_axis_rotations_are_proper_and_invertible(self):
        rotations=[]
        axes=[list(v) for v in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))]
        for right,up in itertools.product(axes,repeat=2):
            if dot(right,up):continue
            r=basis(right,up); rotations.append(r)
            self.assertEqual(determinant(r),1)
            t,inv=rigid_transform(r,[13,-42,105])
            self.assertEqual(point(inv,point(t,[10,22,-4])),[10,22,-4])
            axis,angle=axis_angle(r); a=math.radians(angle)
            for vector in axes:
                c=cross(axis,vector); projected=[vector[i]*math.cos(a)+c[i]*math.sin(a)+axis[i]*dot(axis,vector)*(1-math.cos(a)) for i in range(3)]
                for x,y in zip(projected,mv(r,vector)):self.assertAlmostEqual(x,y,places=10)
        self.assertEqual(len(rotations),24)

    def test_invalid_basis_is_rejected(self):
        for right,up in [([1,0,0],[1,0,0]),([2,0,0],[0,1,0]),([float('nan'),0,0],[0,1,0])]:
            with self.assertRaises(ValueError):basis(right,up)

    def test_canonical_cameras_have_consistent_handedness(self):
        for v in CANONICAL_CAMERAS.values():self.assertEqual(determinant(basis(v['right'],v['up'])),1)
        m=pixel_matrix([1,0,0],[0,1,0],2)
        self.assertEqual(mv(m,[10,20,0,1]),[532,472,1])

class ReleaseTests(unittest.TestCase):
    def test_all_cases_annotations_and_export_contract(self):
        annotations={}
        for file in (BASE/'scripts').glob('annotations_*.json'):
            for annotation in json.loads(file.read_text())['cases']:
                self.assertNotIn(annotation['case_id'],annotations)
                annotations[annotation['case_id']]=annotation
        self.assertEqual(set(annotations),{f'case_{i:03d}' for i in range(1,34)})
        dataset=json.loads((BASE/'dataset.json').read_text())
        self.assertEqual(len(dataset['samples']),33)
        for d in dataset['samples']:
            self.assertEqual(d['annotation'],annotations[d['case_id']])
            self.assertFalse(d['training_ready'])
            original=json.loads((V1/'cases'/d['case_id']/'validation.json').read_text())
            self.assertEqual(d['legacy_geometry_validation'],original)
            if d['status']!='pose_calibrated_candidate': continue
            self.assertEqual(d['builder_sha256'],hashlib.sha256((BASE/'scripts/build_case.py').read_bytes()).hexdigest())
            self.assertEqual(d['export_coordinate_verification']['status'],'passed')
            for v in d['views']:
                if 'canonical_camera' not in v: continue
                expected=CANONICAL_CAMERAS.get(v['canonical_role'])
                if expected:
                    self.assertEqual(v['canonical_camera']['screen_right'],expected['right'])
                    self.assertEqual(v['canonical_camera']['screen_up'],expected['up'])

    def test_release_snapshot_and_downloads(self):
        release=json.loads((BASE/'release_manifest.json').read_text())
        for name,expected in release['files_sha256'].items():
            self.assertEqual(hashlib.sha256((BASE/name).read_bytes()).hexdigest(),expected,name)
        for archive in (BASE/'cases').glob('*/*_alignment_candidate.zip'):
            with zipfile.ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                manifest=json.loads(z.read('package_manifest.json'))
                self.assertFalse(manifest['training_ready'])
                for name,expected in manifest['files_sha256'].items():
                    self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),expected,name)
                alignment=json.loads(z.read('alignment.json'))
                self.assertEqual('reference.step' in z.namelist(),alignment['status']=='pose_calibrated_candidate')

    def test_pilot_fronts_are_all_canonical_xy_and_pixels_validated(self):
        for cid in ('case_014','case_015','case_017'):
            d=json.loads((BASE/'cases'/cid/'alignment.json').read_text())
            self.assertEqual(d['status'],'pose_calibrated_candidate')
            self.assertEqual(d['rotation_determinant'],1)
            self.assertFalse(d['training_ready'])
            rows=[v for v in d['views'] if v['kind']=='external']
            front=next(v for v in rows if v['canonical_role']=='front')
            self.assertEqual(front['canonical_camera']['screen_right'],[1,0,0])
            self.assertEqual(front['canonical_camera']['screen_up'],[0,1,0])
            for v in rows:
                self.assertEqual(v['pair_status'],'landmark_calibrated_review_pending')
                self.assertTrue(v['pixel_registration']['landmark_gate_pass'])
                self.assertTrue((BASE/'cases'/cid/v['registered_source']).exists())
            self.assertLess(d['rigid_invariants']['transform_roundtrip_error_mm'],1e-6)

    def test_no_section_fills_missing_standard_view(self):
        for path in (BASE/'cases').glob('*/alignment.json'):
            d=json.loads(path.read_text())
            for view in d.get('views',[]):
                if view['kind']!='external':
                    self.assertNotIn('registered_source',view)
                    self.assertNotIn('reference_render',view)

    def test_current_source_and_output_hashes(self):
        for path in (BASE/'cases').glob('*/alignment.json'):
            d=json.loads(path.read_text()); cid=d['case_id']
            self.assertEqual(d['source_model_sha256'],hashlib.sha256((V1/'cases'/cid/'model.py').read_bytes()).hexdigest())
            self.assertEqual(d['source_reference_sha256'],hashlib.sha256((V1/'cases'/cid/'reference.step').read_bytes()).hexdigest())
            if d['status']=='pose_calibrated_candidate':
                for filename,key in [('model.py','model_sha256'),('reference.step','reference_sha256'),('reconstructed.step','reconstructed_sha256')]:
                    self.assertEqual(d[key],hashlib.sha256((path.parent/filename).read_bytes()).hexdigest())

if __name__=='__main__':unittest.main(verbosity=2)
