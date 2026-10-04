"""Regressions from independent review. Synthetic-only inputs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import numpy as np
from moletracker import store as storage
from moletracker.store import Store, REGIONS, restore_backup
from moletracker.color import fit_reference, linearize, delta, analysis_image, patch_medians, polygon_mask, measure
from tests.test_integration import fixture


class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=Store(self.root/'data')
        self.session=self.store.create_session('2026-09');self.mole=self.store.add_mole(REGIONS[0],'synthetic')
        self.path=self.root/'fixture.png';self.profile,self.masks=fixture(self.path)
        self.photo=self.store.import_photo(self.path,self.session,'detail')
        self.image,_=analysis_image(self.path,True)
        self.patches=patch_medians(self.image,self.masks['patches'])
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def measurement(self):
        fit=fit_reference(self.patches,self.profile)
        result=measure(self.image,polygon_mask((360,240),self.masks['mole']),polygon_mask((360,240),self.masks['skin']),fit)
        result.update(color_source='explicit-sRGB-assumption',manual_qc=[True]*4)
        return result
    def test_degenerate_targets_and_transforms_rejected(self):
        targets=[np.zeros((6,3)),np.repeat(np.linspace(.1,.8,6)[:,None],3,axis=1),np.asarray(self.profile['xyz'])*1e-10]
        targets.append(linearize(self.patches) @ np.diag([1,1,1e-8]))
        for xyz in targets:
            with self.subTest(xyz=xyz),self.assertRaises(ValueError):fit_reference(self.patches,{**self.profile,'xyz':xyz.tolist()})
    def test_missing_and_inconsistent_provenance_fails_closed(self):
        bare={'mole_l':2.,'skin_l':5.,'d':3.}
        self.assertIsNone(delta(bare,bare))
        valid=self.measurement()
        for key in ['method','profile_hash','ordinary_skin','manual_qc','color_source','fit']:
            bad=copy.deepcopy(valid);bad.pop(key)
            with self.subTest(key=key):
                self.assertIsNone(delta(bad,valid))
                with self.assertRaises(ValueError):self.store.save_observation(self.mole,self.session,self.photo,self.masks,bad,'comparable')
        for changes in [{'d':999},{'mole_l':float('nan')},{'profile_hash':'fake'},{'manual_qc':[True,True,False,True]}]:
            bad={**valid,**changes}
            self.assertIsNone(delta(valid,bad))
            with self.assertRaises(ValueError):self.store.save_observation(self.mole,self.session,self.photo,self.masks,bad,'comparable')
    def test_restore_rejects_cross_session_and_missing_provenance(self):
        self.store.save_observation(self.mole,self.session,self.photo,self.masks,self.measurement(),'comparable')
        other=self.store.create_session('2026-10');out=self.root/'good.zip';self.store.backup(out)
        for mode in ('session','provenance'):
            badfile=self.root/(mode+'.zip')
            with zipfile.ZipFile(out) as src,zipfile.ZipFile(badfile,'w') as dst:
                data=json.loads(src.read('manifest.json'));record=data['tables']['observations'][0]
                if mode=='session':record['session_id']=other
                else:record['measurement']=json.dumps({'mole_l':1,'skin_l':2,'d':1})
                for name in src.namelist():dst.writestr(name,json.dumps(data) if name=='manifest.json' else src.read(name))
            with self.assertRaises(ValueError):restore_backup(badfile,self.root/(mode+'-restored'))
    def test_backup_shared_limits_prevent_unrestorable_success(self):
        for constant,limit in [('MAX_BACKUP',100),('MAX_MANIFEST',10),('MAX_MEMBERS',1)]:
            target=self.root/(constant+'.zip')
            with patch.object(storage,constant,limit,create=True),self.assertRaises(ValueError):self.store.backup(target)
            self.assertFalse(target.exists())
    def test_backup_record_limit_and_compressed_size_accounting(self):
        self.store.create_session('2026-10')
        with patch.object(storage,'MAX_RECORDS',1),self.assertRaises(ValueError):
            self.store.backup(self.root/'records.zip')
        good=self.root/'good.zip';self.store.backup(good)
        with zipfile.ZipFile(good) as archive:
            total=sum(i.file_size for i in archive.infolist())
        self.assertGreater(total,good.stat().st_size)
        with patch.object(storage,'MAX_BACKUP',total-1):
            with self.assertRaises(ValueError):self.store.backup(self.root/'too-large.zip')
            with self.assertRaises(ValueError):restore_backup(good,self.root/'too-large')
        with patch.object(storage,'MAX_BACKUP',total):
            self.store.backup(self.root/'boundary.zip')
            restore_backup(self.root/'boundary.zip',self.root/'boundary')

    def test_cross_session_and_role_import_of_corrupt_original_rejected(self):
        self.store.photo_path(self.photo).write_bytes(b'corrupt')
        other=self.store.create_session('2026-10')
        for session,role in [(other,'detail'),(self.session,'overview')]:
            with self.assertRaises(ValueError):self.store.import_photo(self.path,session,role)
        self.assertEqual(len(self.store.rows('SELECT * FROM photos')),1)
        with self.assertRaises(ValueError):self.store.save_observation(self.mole,self.session,self.photo,{},None,'uncalibrated','x')

    def test_complete_records_cannot_omit_geometry(self):
        valid=self.measurement()
        for masks in (None,[], 'bad', 1):
            with self.subTest(masks=masks),self.assertRaises(ValueError):
                self.store.save_observation(self.mole,self.session,self.photo,masks,valid,'comparable')
        self.store.save_observation(self.mole,self.session,self.photo,self.masks,valid,'comparable')
        out=self.root/'complete.zip';self.store.backup(out)
        for index,masks in enumerate((None,[], 'bad', {})):
            path=self.root/f'bad-mask-{index}.zip';dest=self.root/f'bad-mask-{index}'
            with zipfile.ZipFile(out) as src,zipfile.ZipFile(path,'w') as dst:
                data=json.loads(src.read('manifest.json'));data['tables']['observations'][0]['masks']=json.dumps(masks)
                for name in src.namelist():dst.writestr(name,json.dumps(data) if name=='manifest.json' else src.read(name))
            with self.assertRaises(ValueError):restore_backup(path,dest)
            self.assertFalse(dest.exists())

    def test_photo_only_shape_types_rejected_but_empty_lists_valid(self):
        malformed=[{'mole':False},{'skin':0},{'patches':{}},{'exclude':False},
                   {'mole':None},{'patches':''},{'exclude':[False]}, {'mole':[[True,1],[2,3],[3,1]]}]
        for masks in malformed:
            with self.subTest(masks=masks),self.assertRaises(ValueError):
                self.store.save_observation(self.mole,self.session,self.photo,masks,None,'uncalibrated')
        valid={'mole':[],'skin':[],'patches':[],'exclude':[]}
        self.store.save_observation(self.mole,self.session,self.photo,valid,None,'uncalibrated')
        original=self.root/'empty-shapes.zip';self.store.backup(original)
        for index,masks in enumerate(malformed):
            path=self.root/f'photo-only-{index}.zip';dest=self.root/f'photo-only-{index}'
            with zipfile.ZipFile(original) as src,zipfile.ZipFile(path,'w') as dst:
                data=json.loads(src.read('manifest.json'));data['tables']['observations'][0]['masks']=json.dumps(masks)
                for name in src.namelist():dst.writestr(name,json.dumps(data) if name=='manifest.json' else src.read(name))
            with self.assertRaises(ValueError):restore_backup(path,dest)
            self.assertFalse(dest.exists())

    def test_capture_context_presence_requires_valid_dictionary(self):
        invalid=(None,False,[],{}, {'srgb_assumed':True,'ordinary_skin':None})
        for context in invalid:
            with self.subTest(context=context),self.assertRaises(ValueError):
                self.store.save_observation(self.mole,self.session,self.photo,{'capture_context':context},None,'uncalibrated')
        # Legacy absence is legitimate and carries no fabricated assumptions.
        self.store.save_observation(self.mole,self.session,self.photo,{},None,'uncalibrated')
        original=self.root/'legacy.zip';self.store.backup(original)
        for index,context in enumerate(invalid):
            path=self.root/f'context-{index}.zip';dest=self.root/f'context-{index}'
            with zipfile.ZipFile(original) as src,zipfile.ZipFile(path,'w') as dst:
                data=json.loads(src.read('manifest.json'))
                data['tables']['observations'][0]['masks']=json.dumps({'capture_context':context})
                for name in src.namelist():dst.writestr(name,json.dumps(data) if name=='manifest.json' else src.read(name))
            with self.assertRaises(ValueError):restore_backup(path,dest)
            self.assertFalse(dest.exists())
