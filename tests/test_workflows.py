import json
import zipfile
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import tkinter as tk

from PIL import Image
from moletracker.store import Store, REGIONS, restore_backup


class WorkflowTests(unittest.TestCase):
    def test_tracking_month_archive_and_metadata_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'journal')
            try:
                january = store.create_session('2026-01')
                october = store.create_session('2026-10')
                mole = store.add_mole(REGIONS[0], '合成位置', start_month='2026-10')
                self.assertNotIn(mole, store.missing(january))
                self.assertIn(mole, store.missing(october))
                source = Path(tmp) / '定位照片.png'
                Image.new('RGB', (30, 40), 'white').save(source)
                photo = store.import_photo(source, october, 'overview')
                store.set_tracking(mole, '2026-10', '', photo)
                self.assertEqual(store.photos(october)[0]['filename'], source.name)
                backup = Path(tmp) / 'journal.zip'
                store.backup(backup)
                restore_backup(backup, Path(tmp) / 'restored')
                restored = Store(Path(tmp) / 'restored')
                try:
                    self.assertEqual(restored.moles()[0]['overview_photo'], photo)
                    self.assertEqual(restored.photos(october)[0]['filename'], source.name)
                    self.assertEqual(restored.audit(), store.audit())
                finally: restored.close()
                store.set_tracking(mole, '2026-10', '2026-10', photo)
                self.assertNotIn(mole, store.missing(october))
                self.assertEqual(len(store.moles()), 1)
            finally: store.close()

    def test_restore_rejects_invalid_or_duplicate_tracking_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'journal')
            try:
                store.create_session('2026-10');mole=store.add_mole(REGIONS[0],'合成位置')
                backup=Path(tmp)/'valid.zip';store.backup(backup)
                with zipfile.ZipFile(backup) as archive:data=json.loads(archive.read('manifest.json'))
                for index,entries in enumerate([
                    [{'mole_id':mole,'start_month':0,'end_month':0,'overview_photo':None}],
                    data['tracking']*2,
                    [{**data['tracking'][0],'unknown':True}],
                ]):
                    corrupted=Path(tmp)/f'bad-{index}.zip'
                    with zipfile.ZipFile(corrupted,'w') as archive:
                        archive.writestr('manifest.json',json.dumps({**data,'tracking':entries}))
                    with self.assertRaises(ValueError):restore_backup(corrupted,Path(tmp)/f'restored-{index}')
                with self.assertRaises(ValueError):store.set_tracking(mole,0,0)
            finally:store.close()

    def test_legacy_backup_remains_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'journal')
            try:
                session=store.create_session('2026-01');mole=store.add_mole(REGIONS[0],'旧资料位置')
                backup=Path(tmp)/'new.zip';store.backup(backup)
                with zipfile.ZipFile(backup) as archive:data=json.loads(archive.read('manifest.json'))
                data['format']=1;data.pop('tracking');data.pop('photo_names')
                legacy=Path(tmp)/'legacy.zip'
                with zipfile.ZipFile(legacy,'w') as archive:archive.writestr('manifest.json',json.dumps(data))
                restore_backup(legacy,Path(tmp)/'restored')
                restored=Store(Path(tmp)/'restored')
                try:
                    self.assertEqual(restored.moles()[0]['start_month'],'')
                    self.assertEqual(restored.missing(session),[mole])
                finally:restored.close()
            finally:store.close()

    def test_current_backup_requires_all_additional_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'journal')
            try:
                store.create_session('2026-10');store.add_mole(REGIONS[0],'合成位置')
                backup=Path(tmp)/'valid.zip';store.backup(backup)
                with zipfile.ZipFile(backup) as archive:data=json.loads(archive.read('manifest.json'))
                for key in ('tracking','photo_names','drafts'):
                    damaged={k:v for k,v in data.items() if k!=key}
                    source=Path(tmp)/(key+'.zip');destination=Path(tmp)/(key+'-restored')
                    with zipfile.ZipFile(source,'w') as archive:archive.writestr('manifest.json',json.dumps(damaged))
                    with self.assertRaises(ValueError):restore_backup(source,destination)
                    self.assertFalse(destination.exists())
            finally:store.close()

    def test_draft_does_not_allocate_full_resolution_masks(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'journal')
            try:
                session = store.create_session('2026-10')
                mole = store.add_mole(REGIONS[0], '合成位置')
                source = Path(tmp) / 'photo.png'
                Image.new('RGB', (30, 40), 'white').save(source)
                photo = store.import_photo(source, session, 'detail')
                payload = {'masks': {'mole': [[1, 1], [20, 1], [20, 20]]}, 'points': [], 'mode': 1,
                           'notes': '', 'profile': None, 'srgb': False, 'ordinary': True}
                with patch('moletracker.validation.polygon_mask', side_effect=AssertionError('full raster allocation')):
                    store.save_draft(mole, session, photo, payload)
                payload['masks']['mole'][0] = [-1, 1]
                with self.assertRaises(ValueError): store.save_draft(mole, session, photo, payload)
            finally: store.close()

    def test_display_coordinates_roundtrip(self):
        from moletracker.canvas_tools import display_point, original_point
        for rotation in range(4):
            for point in ([0, 0], [49, 29], [12.5, 8.25]):
                visible = display_point(point, (50, 30), rotation)
                self.assertEqual(original_point(visible, (50, 30), rotation), list(point))

    def test_canvas_move_delete_and_redo_preserve_original_coordinates(self):
        from moletracker.photo_canvas import PhotoCanvas
        root=tk.Tk()
        try:
            canvas=PhotoCanvas(root,lambda:None);canvas.pack();root.update()
            image=Image.new('RGB',(100,80),'white')
            canvas.set_prepared((image,image.copy()),{'mole':[[10,10],[40,10],[40,40]],'skin':[],'exclude':[],'patches':[]})
            canvas.mode=1;canvas.rotate();canvas.scale=1.;canvas.render()
            original=list(canvas.masks['mole'][0]);point=canvas.projected(original)
            canvas.click(SimpleNamespace(x=point[0],y=point[1]))
            destination=canvas.projected([15,20])
            event=SimpleNamespace(x=destination[0],y=destination[1])
            canvas.drag(event);canvas.release(event)
            self.assertEqual(canvas.masks['mole'][0],[15,20])
            canvas.undo();self.assertEqual(canvas.masks['mole'][0],original)
            canvas.redo();self.assertEqual(canvas.masks['mole'][0],[15,20])
            canvas.selected_handle=('mole',0);canvas.delete_vertex()
            self.assertEqual(len(canvas.points),2)
            canvas.undo();self.assertEqual(len(canvas.masks['mole']),3)
        finally:root.destroy()

    def test_instance_lock_and_cancelled_backup_preserve_data(self):
        from moletracker.instance import InstanceLock
        from concurrent.futures import CancelledError
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'journal';lock=InstanceLock(root)
            try:
                with self.assertRaises(ValueError):InstanceLock(root)
                store=Store(root)
                try:
                    session=store.create_session('2026-10')
                    source=Path(tmp)/'original.png';Image.new('RGB',(30,40),'white').save(source)
                    photo=store.import_photo(source,session,'detail')
                    def stop(*args):raise CancelledError()
                    target=Path(tmp)/'cancelled.zip'
                    with self.assertRaises(CancelledError):store.backup(target,stop)
                    self.assertFalse(target.exists());self.assertTrue(store.photo_path(photo).is_file())
                finally:store.close()
            finally:lock.close()
