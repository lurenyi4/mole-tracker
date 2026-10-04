import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
from moletracker.store import Store, restore_backup, REGIONS
from moletracker.color import linearize, fit_reference, measure, polygon_mask, delta, METHOD


class ColorTests(unittest.TestCase):
    def setUp(self):
        self.rgb = np.array([[.2,.3,.4],[.7,.2,.3],[.2,.8,.3],[.3,.2,.8],[.8,.7,.4],[.6,.6,.6]])
        self.matrix = np.array([[.4361,.2225,.0139],[.3851,.7169,.0971],[.1431,.0606,.7142]])
        self.profile = {'name':'SYNTHETIC ONLY','source':'generated test values', 'white':'D50','observer':'2','xyz':(linearize(self.rgb) @ self.matrix).tolist()}

    def test_transfer_and_recovery(self):
        self.assertAlmostEqual(linearize(np.array([.04045]))[0], .04045/12.92)
        fit = fit_reference(self.rgb, self.profile)
        np.testing.assert_allclose(fit['matrix'],self.matrix,atol=1e-10)
        self.assertLess(fit['rmse'],1e-8)

    def test_invalid_reference(self):
        with self.assertRaises(ValueError): fit_reference(np.ones((6,3))*.4,self.profile)
        with self.assertRaises(ValueError): fit_reference(self.rgb,{**self.profile,'white':'D65'})
        with self.assertRaises(ValueError): fit_reference(self.rgb,{**self.profile,'source':''})
        with self.assertRaises(ValueError): fit_reference(self.rgb[:2],self.profile)
        with self.assertRaises(ValueError): fit_reference(self.rgb,{**self.profile,'xyz':[[float('nan')]*3]*6})

    def test_change_preserved_and_skin_independent(self):
        image=np.full((40,40,3),.65); image[:20]=.3
        mole=np.zeros((40,40),bool); mole[:20]=True
        skin=~mole
        a=measure(image,mole,skin,fit_reference(self.rgb,self.profile))
        image[:20]=.4
        b=measure(image,mole,skin,fit_reference(self.rgb,self.profile))
        self.assertGreater(b['mole_l'],a['mole_l'])
        self.assertLess(b['d'],a['d'])
        self.assertEqual(b['skin_l'],a['skin_l'])
        image[20:]=.7
        c=measure(image,mole,skin,fit_reference(self.rgb,self.profile))
        self.assertEqual(c['mole_l'],b['mole_l'])
        self.assertGreater(c['skin_l'],b['skin_l'])
        self.assertIsNone(measure(image,mole,None,fit_reference(self.rgb,self.profile),ordinary_skin=False)['d'])
        with self.assertRaises(ValueError): measure(image,mole,mole,fit_reference(self.rgb,self.profile))

    def test_cast_recovery(self):
        from moletracker.color import encode
        image=np.full((40,40,3),.65); image[:20]=.3
        mask=np.zeros((40,40),bool);mask[:20]=True
        gain=np.array([.8,1.1,.9])
        cast=encode(linearize(image)*gain)
        a=measure(image,mask,~mask,fit_reference(self.rgb,self.profile))
        b=measure(cast,mask,~mask,fit_reference(encode(linearize(self.rgb)*gain),self.profile))
        self.assertAlmostEqual(a['d'],b['d'],places=8)
        cast[:20]=encode(linearize(np.array([.4]*3))*gain)
        c=measure(cast,mask,~mask,fit_reference(encode(linearize(self.rgb)*gain),self.profile))
        self.assertGreater(c['mole_l'],b['mole_l'])

    def test_masks_qc_delta(self):
        m=polygon_mask((40,40),[[1,1],[30,1],[30,30],[1,30]],[[[10,10],[20,10],[20,20],[10,20]]])
        self.assertFalse(m[15,15]);self.assertTrue(m[2,2])
        with self.assertRaises(ValueError): polygon_mask((40,40),[[0,0],[100,0],[0,20]])
        fit=fit_reference(self.rgb,self.profile)
        with self.assertRaises(ValueError): measure(np.ones((40,40,3)),m,None,fit,ordinary_skin=False)
        with self.assertRaises(ValueError): measure(np.full((40,40,3),.5),np.eye(40,dtype=bool),None,fit,ordinary_skin=False)
        base=np.full((40,40,3),.65);base[:20]=.3
        mask=np.zeros((40,40),bool);mask[:20]=True
        a=measure(base,mask,~mask,fit)
        a.update(color_source='explicit-sRGB-assumption',manual_qc=[True]*4)
        a.update(mole_l=10.,skin_l=30.,d=20.)
        b={**a,'mole_l':12.,'d':18.}
        self.assertEqual(delta(a,b)['d'],-2.)
        self.assertIsNone(delta(a,{**b,'profile_hash':'y'}))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.store=Store(self.root/'data')
        self.file=self.root/'test.png';Image.new('RGB',(60,60),(120,100,90)).save(self.file)
    def tearDown(self): self.store.close();self.tmp.cleanup()

    def test_persist_identity_coverage_and_original(self):
        s=self.store.create_session('2026-09')
        with self.assertRaises(ValueError): self.store.create_session('2026-09')
        m=self.store.add_mole(REGIONS[0],'左侧 landmark')
        p=self.store.import_photo(self.file,s,'detail')
        self.assertEqual(self.store.photo_path(p).read_bytes(),self.file.read_bytes())
        o=self.store.save_observation(m,s,p,{'mole':[[1,1],[20,1],[20,20]]},None,'retake','blur')
        self.assertEqual(self.store.missing(s),[])
        n=self.store.add_mole(REGIONS[1],'right')
        self.store.correct_identity(o,n,'corrected visual match')
        self.assertEqual(self.store.missing(s),[m])
        self.assertEqual(len(self.store.audit()),1)
        self.store.set_coverage(s,REGIONS[0],'not_photographed')
        self.assertEqual(self.store.coverage(s)[REGIONS[0]],'not_photographed')
        self.assertEqual(self.store.coverage(s)[REGIONS[1]],'pending')
        self.store.close();self.store=Store(self.root/'data')
        self.assertEqual(len(self.store.moles()),2)
        self.assertEqual(self.store.observations(n)[0]['id'],o)

    def test_backup_restore_and_reject_corrupt(self):
        s=self.store.create_session('2026-09');m=self.store.add_mole(REGIONS[0],'left')
        p=self.store.import_photo(self.file,s,'overview')
        self.store.save_observation(m,s,p,{},None,'uncalibrated','No profile')
        out=self.root/'backup.zip';self.store.backup(out)
        dest=self.root/'restored';restore_backup(out,dest)
        other=Store(dest)
        self.assertEqual(other.moles(),self.store.moles())
        self.assertEqual(other.photo_path(p).read_bytes(),self.file.read_bytes());other.close()
        with self.assertRaises(ValueError): restore_backup(out,dest)
        import zipfile
        with zipfile.ZipFile(self.root/'bad.zip','w') as z:z.writestr('../evil','bad')
        with self.assertRaises(ValueError):restore_backup(self.root/'bad.zip',self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_invalid_import_and_dates(self):
        for month in ['2026-13','x','2026-1']:
            with self.assertRaises(ValueError):self.store.create_session(month)
        s=self.store.create_session('2026-09')
        bad=self.root/'bad.jpg';bad.write_bytes(b'not an image')
        with self.assertRaises(ValueError):self.store.import_photo(bad,s,'detail')
        with self.assertRaises(ValueError):self.store.add_mole('unknown','x')
        with self.assertRaises(ValueError):self.store.set_coverage(s,REGIONS[0],'absent')
