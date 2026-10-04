"""All fixtures are generated colors and geometric shapes, never medical photos."""
from pathlib import Path
import io
import json
import tempfile
import unittest
import zipfile
import numpy as np
from PIL import Image
from moletracker.color import analysis_image, encode, linearize, fit_reference, patch_medians, polygon_mask, measure, delta
from moletracker.store import Store, restore_backup, REGIONS


def fixture(path, lesion=.32, gain=None):
    rgb=np.full((240,360,3),.65)
    rgb[60:150,50:140]=lesion
    samples=np.array([[.2,.3,.4],[.7,.2,.3],[.2,.8,.3],[.3,.2,.8],[.8,.7,.4],[.6,.6,.6]])
    matrix=np.array([[.4361,.2225,.0139],[.3851,.7169,.0971],[.1431,.0606,.7142]])
    rects=[]
    for i,patch in enumerate(samples):
        x=10+i*55;rgb[190:220,x:x+40]=patch;rects.append([x+5,195,x+35,215])
    if gain is not None:rgb=encode(linearize(rgb)*gain)
    Image.fromarray(np.rint(rgb*255).astype('uint8')).save(path)
    profile={'name':'SYNTHETIC TEST ONLY — NOT A PHYSICAL CARD','source':'Generated linear RGB → XYZ matrix; test fixture only', 'white':'D50','observer':'2','xyz':(linearize(samples)@matrix).tolist()}
    masks={'mole':[[65,75],[125,75],[125,135],[65,135]],'skin':[[170,60],[280,60],[280,150],[170,150]],'exclude':[], 'patches':rects}
    return profile,masks


class IntegrationTests(unittest.TestCase):
    def test_two_months_backup_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=Store(root/'data');mole=store.add_mole(REGIONS[1],'synthetic square, left')
            results=[]
            for month,level,gain in [('2026-08',.32,None),('2026-09',.4,np.array([.8,1.1,.9]))]:
                path=root/(month+'.png');profile,masks=fixture(path,level,gain)
                session=store.create_session(month);photo=store.import_photo(path,session,'detail')
                with self.assertRaises(ValueError):analysis_image(store.photo_path(photo))
                image,space=analysis_image(store.photo_path(photo),assume_srgb=True)
                fit=fit_reference(patch_medians(image,masks['patches']),profile)
                a=polygon_mask((360,240),masks['mole']);b=polygon_mask((360,240),masks['skin'])
                measurement=measure(image,a,b,fit);measurement['color_source']=space;measurement['manual_qc']=[True]*4
                store.save_observation(mole,session,photo,masks,measurement,'comparable','synthetic only')
                results.append(measurement)
            self.assertGreater(delta(*results)['mole_l'],7)
            self.assertLess(abs(delta(*results)['skin_l']),1)
            store.backup(root/'archive.zip');restore_backup(root/'archive.zip',root/'restored')
            restored=Store(root/'restored');records=restored.observations(mole)
            self.assertEqual(records,store.observations(mole))
            self.assertEqual(records[1]['measurement']['fit']['profile'],profile)
            self.assertEqual(records[1]['masks'],masks)
            store.close();restored.close()

    def test_tampered_backup_and_import_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=Store(root/'data');session=store.create_session('2026-09')
            path=root/'synthetic.png';fixture(path);store.import_photo(path,session,'detail');store.backup(root/'good.zip')
            with zipfile.ZipFile(root/'good.zip') as src,zipfile.ZipFile(root/'bad.zip','w') as dst:
                for name in src.namelist():dst.writestr(name,b'corrupt' if name.startswith('originals/') else src.read(name))
            with self.assertRaises(ValueError):restore_backup(root/'bad.zip',root/'restored')
            self.assertFalse((root/'restored').exists());store.close()

    def test_bad_fit_and_no_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.png';profile,masks=fixture(path);image,_=analysis_image(path,True)
            values=patch_medians(image,masks['patches'])
            profile['xyz'][0]=[1.2,1.2,1.2]
            with self.assertRaises(ValueError):fit_reference(values,profile)
            with self.assertRaises(ValueError):patch_medians(image,[[0,0,2,2]])

    def test_icc_conversion_and_exif_original_retention(self):
        from PIL import ImageCms
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'icc.jpg';exif=Image.Exif();exif[274]=6;exif[271]='Synthetic Camera'
            icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
            Image.new('RGB',(60,80),(90,100,120)).save(path,icc_profile=icc,exif=exif)
            store=Store(root/'data');s=store.create_session('2026-09');p=store.import_photo(path,s,'detail')
            image,provenance=analysis_image(store.photo_path(p))
            self.assertEqual(image.shape,(80,60,3));self.assertTrue(provenance.startswith('ICC-to-sRGB'))
            self.assertEqual(path.read_bytes(),store.photo_path(p).read_bytes())
            with Image.open(store.photo_path(p)) as stored:
                self.assertEqual(stored.getexif()[274],6);self.assertEqual(stored.info['icc_profile'],icc)
            store.close()
