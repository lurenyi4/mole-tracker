"""Native widget smoke test. Requires a working DISPLAY or Windows/macOS desktop."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import tkinter as tk
from moletracker.app import App
from moletracker.store import Store, REGIONS
from tests.test_integration import fixture


@unittest.skipIf(sys.platform.startswith('linux') and not os.environ.get('DISPLAY'),'Native display unavailable')
class GuiSmokeTests(unittest.TestCase):
    def test_full_flow_and_unsaved_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=tk.Tk();store=Store(Path(tmp)/'data')
            try:
                app=App(root,store);root.update()
                session=store.create_session('2026-09');mole=store.add_mole(REGIONS[0],'synthetic fixture')
                path=Path(tmp)/'test.png';profile,masks=fixture(path);photo=store.import_photo(path,session,'detail')
                app.session=session;app.mole=mole;app.photo=photo;app.refresh_sessions();app.refresh_moles()
                app.canvas.load(store.photo_path(photo),masks);app.profile=profile;app.srgb.set(True)
                for var in app.qc:var.set(True)
                app.save_comparable();root.update()
                self.assertEqual(len(store.observations(mole)),1)
                app.canvas.zoom(1.25);app.canvas.fit();root.update()
                app.dirty=True
                with patch('tkinter.messagebox.askyesno',return_value=False):self.assertFalse(app.discard())
                self.assertTrue(app.dirty)
                with patch('tkinter.messagebox.askyesno',return_value=True):self.assertTrue(app.discard())
                self.assertTrue(app.dirty)  # confirmation alone does not commit a transition
                app.dirty=False
                app.history.selection_set(store.observations(mole)[0]['id']);app.load_observation();root.update()
                self.assertEqual(app.canvas.masks['mole'],masks['mole'])
                self.assertFalse(any(v.get() for v in app.qc))
                with patch('tkinter.filedialog.askopenfilenames',return_value=()):app.import_photos('detail')
                self.assertEqual(len(store.photos(session)),1)
            finally:store.close();root.destroy()

    def test_failed_image_transition_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=tk.Tk();store=Store(Path(tmp)/'data')
            try:
                app=App(root,store);root.update()
                session=store.create_session('2026-09');mole=store.add_mole(REGIONS[0],'first')
                path=Path(tmp)/'first.png';profile,masks=fixture(path)
                good=store.import_photo(path,session,'detail')
                badpath=Path(tmp)/'bad.png';fixture(badpath,.4);bad=store.import_photo(badpath,session,'detail')
                app.session=session;app.mole=mole;app.photo=good;app.refresh_sessions();app.refresh_moles()
                app.canvas.load(store.photo_path(good),masks);app.srgb.set(True);app.ordinary.set(False)
                for var in app.qc:var.set(True)
                oldimage=app.canvas.original;oldmasks=app.canvas.masks
                badobservation=store.save_observation(mole,session,bad,{},None,'uncalibrated','synthetic')
                app.refresh_history()
                store.photo_path(bad).write_bytes(b'corrupt')
                index=next(i for i,r in enumerate(app.photo_rows) if r['id']==bad)
                app.photo_list.selection_clear(0,'end');app.photo_list.selection_set(index)
                with self.assertRaises(ValueError):app.select_photo()
                self.assertEqual(app.photo,good);self.assertIs(app.canvas.original,oldimage);self.assertIs(app.canvas.masks,oldmasks)
                self.assertEqual(app.selected(app.photo_list,app.photo_rows)['id'],good)
                self.assertTrue(all(var.get() for var in app.qc))
                app.history.selection_set(badobservation)
                with self.assertRaises(ValueError):app.load_observation()
                self.assertEqual(app.photo,good);self.assertIs(app.canvas.original,oldimage);self.assertIs(app.canvas.masks,oldmasks)
                # Direct persistence also refuses the corrupt original.
                with self.assertRaises(ValueError):store.save_observation(mole,session,bad,masks,None,'retake','failed load')
                # Repair test fixture directly, then retry normally.
                (store.root/'originals'/next(p['hash'] for p in app.photo_rows if p['id']==bad)).write_bytes(badpath.read_bytes())
                app.photo_list.selection_clear(0,'end');app.photo_list.selection_set(index);app.select_photo()
                self.assertEqual(app.photo,bad);self.assertEqual(app.canvas.masks.get('mole'),[])
                self.assertFalse(app.srgb.get());self.assertTrue(app.ordinary.get());self.assertFalse(any(v.get() for v in app.qc))
            finally:store.close();root.destroy()

    def test_assumptions_and_profile_confirmation_do_not_leak(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root=tk.Tk();store=Store(Path(tmp)/'data')
            try:
                app=App(root,store);root.update()
                session=store.create_session('2026-09');first=store.add_mole(REGIONS[0],'first');second=store.add_mole(REGIONS[0],'second')
                path=Path(tmp)/'a.png';profile,masks=fixture(path);photo=store.import_photo(path,session,'detail')
                app.session=session;app.mole=first;app.photo=photo;app.refresh_sessions();app.refresh_moles();app.canvas.load(store.photo_path(photo),masks)
                app.srgb.set(True);app.ordinary.set(False)
                app.mole_list.selection_clear(0,'end');app.mole_list.selection_set(1);app.select_mole()
                self.assertFalse(app.srgb.get());self.assertTrue(app.ordinary.get())
                profilepath=Path(tmp)/'profile.json';profilepath.write_text(json.dumps(profile))
                for var in app.qc:var.set(True)
                with patch('tkinter.filedialog.askopenfilename',return_value=str(profilepath)):app.load_profile()
                self.assertFalse(app.qc[2].get());self.assertEqual(app.canvas.masks.get('patches'),[])
                app.srgb.set(True);app.ordinary.set(False)
                app.record(None,'uncalibrated','no valid calibration')
                row=store.observations(second)[0];app.srgb.set(False);app.ordinary.set(True)
                app.history.selection_set(row['id']);app.load_observation()
                self.assertTrue(app.srgb.get());self.assertFalse(app.ordinary.get());self.assertFalse(any(v.get() for v in app.qc))
            finally:store.close();root.destroy()

    def test_failed_month_creation_keeps_dirty_guard(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            root=tk.Tk();store=Store(Path(tmp)/'data')
            try:
                app=App(root,store);root.update();store.create_session('2026-09')
                app.refresh_sessions()
                for value in ('2026-99','2026-09'):
                    app.dirty=True
                    with patch('tkinter.simpledialog.askstring',return_value=value),patch('tkinter.messagebox.askyesno',return_value=True):
                        with self.assertRaises(ValueError):app.new_session()
                    self.assertTrue(app.dirty)
                app.dirty=True
                with patch('tkinter.simpledialog.askstring',return_value='2026-10'),patch('tkinter.messagebox.askyesno',return_value=True),patch.object(store,'create_session',side_effect=sqlite3.OperationalError('test failure')):
                    with self.assertRaises(sqlite3.OperationalError):app.new_session()
                self.assertTrue(app.dirty)
            finally:store.close();root.destroy()

    def test_comparison_failure_clears_entire_panel_and_retries(self):
        from moletracker.color import analysis_image, fit_reference, patch_medians, polygon_mask, measure
        with tempfile.TemporaryDirectory() as tmp:
            root=tk.Tk();store=Store(Path(tmp)/'data')
            try:
                app=App(root,store);root.update();mole=store.add_mole(REGIONS[0],'synthetic')
                ids=[];photos=[]
                for month,level in [('2026-08',.32),('2026-09',.4)]:
                    session=store.create_session(month);path=Path(tmp)/(month+'.png');profile,masks=fixture(path,level)
                    photo=store.import_photo(path,session,'detail');photos.append((store.photo_path(photo),path.read_bytes()))
                    image,source=analysis_image(path,True);fit=fit_reference(patch_medians(image,masks['patches']),profile)
                    result=measure(image,polygon_mask((360,240),masks['mole']),polygon_mask((360,240),masks['skin']),fit)
                    result.update(color_source=source,manual_qc=[True]*4)
                    ids.append(store.save_observation(mole,session,photo,masks,result,'comparable'))
                app.mole=mole;app.refresh_moles();app.history.selection_set(ids);app.compare()
                self.assertIn('+8.32',app.comparison.get())
                for path,raw in photos:
                    path.write_bytes(b'bad')
                    with self.assertRaises(ValueError):app.compare()
                    self.assertNotIn('+8.32',app.comparison.get());self.assertEqual(app.compare_images,[])
                    self.assertTrue(all(not label.cget('image') for label in app.compare_labels))
                    path.write_bytes(raw);app.compare();self.assertIn('+8.32',app.comparison.get())
            finally:store.close();root.destroy()

    def test_reference_wizard_to_measurement_and_minimum_layout(self):
        import json
        from moletracker.reference import read_reference
        from moletracker.reference_ui import ReferenceWizard
        with tempfile.TemporaryDirectory() as tmp:
            root=tk.Tk();store=Store(Path(tmp)/'data')
            try:
                app=App(root,store);root.overrideredirect(True);root.geometry('1100x760');root.update()
                path=Path(tmp)/'synthetic.png';profile,masks=fixture(path)
                csv='patch,X,Y,Z\n'+'\n'.join(f'P{i+1},'+','.join(str(v*100) for v in row) for i,row in enumerate(profile['xyz']))
                wizard=ReferenceWizard(root,read_reference(csv),app.use_profile);root.update()
                values={'manufacturer':'SYNTHETIC','model':'GENERATED TEST ONLY','edition':'test-1','source':'generated fixture, not a physical card','layout':'P1 to P6 left-to-right','white':'D50','observer':'2','kind':'XYZ 0–100'}
                for key,value in values.items():
                    widget=wizard.fields[key]
                    if hasattr(widget,'set'):widget.set(value)
                    else:widget.insert(0,value)
                wizard.confirmed.set(True);wizard.show_preview()
                root.update()
                self.assertTrue(wizard.preview.winfo_ismapped())
                self.assertEqual(str(wizard.preview.master),wizard.preview.winfo_parent())
                self.assertEqual(len(wizard.preview.get_children()),6)
                output=Path(tmp)/'profile.json'
                with patch('tkinter.filedialog.asksaveasfilename',return_value=str(output)):wizard.save()
                self.assertEqual(json.loads(output.read_text())['patch_ids'],['P1','P2','P3','P4','P5','P6'])
                app.session=store.create_session('2026-09');app.mole=store.add_mole(REGIONS[0],'synthetic');app.photo=store.import_photo(path,app.session,'detail')
                app.refresh_sessions();app.refresh_moles();app.canvas.load(store.photo_path(app.photo),masks)
                app.srgb.set(True)
                for var in app.qc:var.set(True)
                app.save_comparable();self.assertEqual(len(store.observations(app.mole)),1)
                app.tabs.select(app.cover);root.update()
                self.assertEqual((root.winfo_width(),root.winfo_height()),(1100,760))
                print('Layout: exact 1100x760 content window, 17-point large-font coverage scroll checked')
                self.assertTrue(app.status_label.winfo_ismapped())
                self.assertLessEqual(app.status_label.winfo_y()+app.status_label.winfo_height(),root.winfo_height())
                # Large-font coverage remains reachable via the always-visible scrollbar.
                from tkinter import ttk
                ttk.Style(root).configure('.',font=('Noto Sans CJK SC',17))
                root.update();app.cover_scroll.yview_moveto(1);root.update()
                self.assertGreaterEqual(float(app.cover_scroll.yview()[1]),.99)
                self.assertTrue(app.status_label.winfo_ismapped())
            finally:store.close();root.destroy()

    def test_new_id_cancel_and_failures_preserve_unsaved_editor(self):
        import copy
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            root=tk.Tk();store=Store(Path(tmp)/'data')
            try:
                app=App(root,store);root.update()
                app.session=store.create_session('2026-09');old=store.add_mole(REGIONS[0],'old')
                path=Path(tmp)/'a.png';_,masks=fixture(path);app.photo=store.import_photo(path,app.session,'detail')
                app.mole=old;app.refresh_sessions();app.refresh_moles();app.canvas.load(store.photo_path(app.photo),copy.deepcopy(masks))
                app.notes.insert('1.0','unsaved note');app.dirty=True
                def unchanged():
                    self.assertEqual(app.mole,old);self.assertEqual(app.canvas.masks,masks)
                    self.assertEqual(app.notes.get('1.0','end').strip(),'unsaved note');self.assertTrue(app.dirty)
                def open_dialog():
                    with patch('tkinter.messagebox.askyesno',return_value=True):app.add_mole()
                    return next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
                dialog=open_dialog();unchanged();dialog.destroy();unchanged()
                dialog=open_dialog()
                button=next(w for w in dialog.winfo_children() if w.winfo_class()=='TButton')
                entry=next(w for w in dialog.winfo_children() if w.winfo_class()=='TEntry')
                with patch('tkinter.messagebox.showerror') as error:
                    button.invoke();self.assertTrue(error.called)
                unchanged()
                entry.insert(0,'new location')
                with patch.object(store,'add_mole',side_effect=sqlite3.OperationalError('simulated')),patch('tkinter.messagebox.showerror') as error:
                    button.invoke();self.assertTrue(error.called)
                unchanged()
                button.invoke();root.update()
                self.assertNotEqual(app.mole,old);self.assertEqual(len(store.moles()),2)
                self.assertFalse(app.dirty);self.assertEqual(app.canvas.masks['mole'],[])
                self.assertEqual(app.notes.get('1.0','end').strip(),'')
            finally:store.close();root.destroy()

    def test_legacy_absent_capture_context_loads_without_partial_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=tk.Tk();store=Store(Path(tmp)/'data')
            try:
                app=App(root,store);root.update()
                app.session=store.create_session('2026-09');app.mole=store.add_mole(REGIONS[0],'legacy')
                path=Path(tmp)/'a.png';fixture(path);photo=store.import_photo(path,app.session,'detail')
                observation=store.save_observation(app.mole,app.session,photo,{},None,'uncalibrated','legacy photo only')
                app.refresh_sessions();app.refresh_moles();app.history.selection_set(observation)
                app.srgb.set(True);app.ordinary.set(False);app.load_observation();root.update()
                self.assertEqual(app.photo,photo);self.assertFalse(app.srgb.get());self.assertTrue(app.ordinary.get())
                self.assertEqual(app.notes.get('1.0','end').strip(),'legacy photo only')
            finally:store.close();root.destroy()
