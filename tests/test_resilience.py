import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from PIL import Image
from moletracker.store import Store, REGIONS
from moletracker.color import analysis_image, fit_reference, patch_medians, polygon_mask, measure
from tests.test_integration import fixture


class ResilienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=Store(self.root/'data')
        self.session=self.store.create_session('2026-09');self.mole=self.store.add_mole(REGIONS[0],'synthetic location')
        self.path=self.root/'fixture.png';self.profile,self.masks=fixture(self.path)
        self.photo=self.store.import_photo(self.path,self.session,'detail')
    def tearDown(self):self.store.close();self.tmp.cleanup()

    def test_repeated_actions_are_idempotent(self):
        self.assertEqual(self.store.import_photo(self.path,self.session,'detail'),self.photo)
        a=self.store.save_observation(self.mole,self.session,self.photo,{},None,'uncalibrated','missing card')
        b=self.store.save_observation(self.mole,self.session,self.photo,{},None,'uncalibrated','missing card')
        self.assertEqual(a,b);self.assertEqual(len(self.store.observations(self.mole)),1)

    def test_interrupted_transaction_leaves_no_observation(self):
        self.store.db.execute("CREATE TRIGGER fail_save BEFORE INSERT ON observations BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.store.save_observation(self.mole,self.session,self.photo,{},None,'uncalibrated','x')
        self.assertEqual(self.store.observations(self.mole),[])
        self.store.db.execute('DROP TRIGGER fail_save')
        self.store.save_observation(self.mole,self.session,self.photo,{},None,'uncalibrated','retry')
        self.assertEqual(len(self.store.observations(self.mole)),1)

    def test_mask_and_profile_edits_recompute_keep_old_snapshot(self):
        image,_=analysis_image(self.path,True);fit=fit_reference(patch_medians(image,self.masks['patches']),self.profile)
        mole=polygon_mask((360,240),self.masks['mole']);skin=polygon_mask((360,240),self.masks['skin'])
        original=measure(image,mole,skin,fit)
        original.update(color_source='explicit-sRGB-assumption',manual_qc=[True]*4)
        self.store.save_observation(self.mole,self.session,self.photo,self.masks,original,'comparable','first')
        modified=polygon_mask((360,240),self.masks['skin'])
        recalculated=measure(image,modified,None,fit,False)
        self.assertNotEqual(recalculated['mole_l'],original['mole_l'])
        changed=json.loads(json.dumps(self.profile));changed['xyz']=[[v*.9 for v in row] for row in changed['xyz']]
        newfit=fit_reference(patch_medians(image,self.masks['patches']),changed)
        result=measure(image,mole,skin,newfit)
        self.assertNotEqual(result['profile_hash'],original['profile_hash'])
        self.assertNotEqual(result['mole_l'],original['mole_l'])
        self.assertEqual(self.store.observations(self.mole)[0]['measurement'],original)

    def test_tampered_original_and_transparent_input(self):
        original=self.store.photo_path(self.photo);original.write_bytes(b'corruption')
        with self.assertRaises(ValueError):self.store.photo_path(self.photo)
        path=self.root/'alpha.png';Image.new('RGBA',(100,100),(120,120,120,10)).save(path)
        with self.assertRaises(ValueError):analysis_image(path,True)
        path=self.root/'gray.png';Image.new('L',(100,100),100).save(path)
        with self.assertRaises(ValueError):analysis_image(path,True)

    def test_backup_failure_does_not_publish_or_replace(self):
        out=self.root/'backup.zip';self.store.backup(out);original=out.read_bytes()
        with self.assertRaises(ValueError):self.store.backup(out)
        self.assertEqual(out.read_bytes(),original)
        self.store.photo_path(self.photo).write_bytes(b'bad')
        with self.assertRaises(ValueError):self.store.backup(self.root/'failed.zip')
        self.assertFalse((self.root/'failed.zip').exists())
