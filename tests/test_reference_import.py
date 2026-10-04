import unittest
import numpy as np
from moletracker.color import reference_xyz
from moletracker.reference import read_reference, build_profile, lab_to_xyz, normalize_source_metadata


class ReferenceImportTests(unittest.TestCase):
    def test_lab_white_and_black(self):
        np.testing.assert_allclose(lab_to_xyz([[100,0,0],[0,0,0]]),[[.96422,1,.82521],[0,0,0]],atol=1e-10)
    def test_csv_and_cgats_match_with_explicit_units(self):
        csv='patch,X,Y,Z\nA1,40,20,10\nA2,20,60,10\nA3,10,10,70\nA4,50,50,30\nA5,20,30,20\nA6,70,70,60\n'
        cgats='CGATS.17\nILLUMINANT "D50"\nOBSERVER_ANGLE "2"\nBEGIN_DATA_FORMAT\nSAMPLE_ID XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\nBEGIN_DATA\n'+ '\n'.join(line.replace(',',' ') for line in csv.splitlines()[1:])+'\nEND_DATA\n'
        a=read_reference(csv);b=read_reference(cgats)
        metadata=dict(manufacturer='Test manufacturer',model='SYNTHETIC',edition='test version',source='test fixture provenance',white='D50',observer='2',layout='Rows labelled A1 through A6')
        pa=build_profile(a,['patch','X','Y','Z'],'XYZ 0–100',metadata,confirmed=True)
        pb=build_profile(b,['SAMPLE_ID','XYZ_X','XYZ_Y','XYZ_Z'],'XYZ 0–100',metadata,confirmed=True)
        np.testing.assert_allclose(pa['xyz'],pb['xyz']);self.assertEqual(pa['patch_ids'],['A1','A2','A3','A4','A5','A6'])
        self.assertEqual(pa['xyz'][0],[.4,.2,.1]);self.assertIn('reference_file_sha256',pa)
        with self.assertRaises(ValueError):build_profile(a,['patch','X','Y','Z'],'XYZ 0–1',metadata,confirmed=True)
        with self.assertRaises(ValueError):build_profile(a,['patch','X','Y','Z'],'XYZ 0–100',{**metadata,'white':'D65'},confirmed=True)
        with self.assertRaises(ValueError):build_profile(a,['patch','X','Y','Z'],'XYZ 0–100',metadata,confirmed=False)
    def test_reject_duplicate_patch_unknown_columns_and_conflicting_metadata(self):
        data=read_reference('patch,L,a,b\nA,40,10,20\nA,50,20,10\n')
        meta=dict(manufacturer='X',model='Y',edition='Z',source='source',white='D50',observer='2',layout='labelled')
        with self.assertRaises(ValueError):build_profile(data,['patch','L','a','b'],'Lab D50',meta,confirmed=True)
        data=read_reference('CGATS.17\nILLUMINANT "D65"\nBEGIN_DATA_FORMAT\nSAMPLE_ID LAB_L LAB_A LAB_B\nEND_DATA_FORMAT\nBEGIN_DATA\nA 50 0 0\nEND_DATA\n')
        with self.assertRaises(ValueError):build_profile(data,['SAMPLE_ID','LAB_L','LAB_A','LAB_B'],'Lab D50',meta,confirmed=True)

    def test_numeric_white_and_coordinate_metadata_consistency(self):
        rows='A1 40 20 10\nA2 20 60 10\nA3 10 10 70\nA4 50 50 30\nA5 20 30 20\nA6 70 70 60\n'
        meta=dict(manufacturer='Test',model='SYNTHETIC',edition='test',source='generated fixture',white='D50',observer='2',layout='A1 to A6')
        def load(headers):
            return read_reference('CTI3\n'+headers+'\nBEGIN_DATA_FORMAT\nSAMPLE_ID XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\nBEGIN_DATA\n'+rows+'END_DATA\n')
        for white in ('96.422 100 82.521','.96422 1 .82521','192.844 200 165.042'):
            table=load(f'COLOR_REP RGB_XYZ\nILLUMINANT_WHITE_POINT_XYZ "{white}"')
            result=build_profile(table,['SAMPLE_ID','XYZ_X','XYZ_Y','XYZ_Z'],'XYZ 0–100',meta,True)
            self.assertEqual(result['white'],'D50')
            modified={**result,'source_metadata':{'ILLUMINANT_WHITE_POINT_XYZ':'95.047 100 108.883'}}
            with self.assertRaises(ValueError):reference_xyz(modified)
        for headers,kind in [
            ('ILLUMINANT_WHITE_POINT_XYZ "95.047 100 108.883"','XYZ 0–100'),
            ('ILLUMINANT D50\nILLUMINANT_WHITE_POINT_XYZ "95.047 100 108.883"','XYZ 0–100'),
            ('ILLUMINANT D65\nILLUMINANT D50','XYZ 0–100'),
            ('ILLUMINANT D50\nilluminant D65','XYZ 0–100'),
            ('COLOR_REP RGB_XYZ','Lab D50'),
            ('COLOR_REP RGB_LAB','XYZ 0–100'),
            ('NORMALIZED_TO_Y_100 YES','XYZ 0–1'),
            ('ILLUMINANT_WHITE_POINT_XYZ "0 0 0"','XYZ 0–100')]:
            with self.subTest(headers=headers),self.assertRaises(ValueError):
                build_profile(load(headers),['SAMPLE_ID','XYZ_X','XYZ_Y','XYZ_Z'],kind,meta,True)
        # Conventional column semantics reject wrong conversion even absent COLOR_REP.
        with self.assertRaises(ValueError):build_profile(load(''),['SAMPLE_ID','XYZ_X','XYZ_Y','XYZ_Z'],'Lab D50',meta,True)
        # CGATS KEYWORD declarations are repeatable declarations, not conflicting values.
        result=load('KEYWORD "COLOR_REP"\nKEYWORD "ILLUMINANT"\nILLUMINANT D50')
        build_profile(result,['SAMPLE_ID','XYZ_X','XYZ_Y','XYZ_Z'],'XYZ 0–100',meta,True)

    def test_known_semantics_refuse_conflicts_before_value_conversion(self):
        for metadata,columns,kind in [
            ({'FILE_FORMAT':'CTI3'},['c1','c2','c3'],'XYZ 0–1'),
            ({'COLOR_REP':'RGB_XYZ'},['c1','c2','c3'],'Lab D50'),
            ({},['XYZ_X','XYZ_Y','XYZ_Z'],'Lab D50'),
            ({},['XYZ_Y','XYZ_X','XYZ_Z'],'XYZ 0–100'),
            ({'DEVICE_CLASS':'DISPLAY'},['X','Y','Z'],'XYZ 0–100'),
            ({'CUSTOM_WHITEPOINT':'D65'},['X','Y','Z'],'XYZ 0–100')]:
            with self.subTest(metadata=metadata),self.assertRaises(ValueError):
                normalize_source_metadata(metadata,columns,kind)
