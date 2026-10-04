import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from moletracker.color import analysis_image, measure, patch_medians
from moletracker.store import Store, REGIONS, restore_backup


class UsabilityTests(unittest.TestCase):
    def test_byte_image_uses_selected_pixels_without_changing_measurements(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.png'
            image = np.full((40, 40, 3), 160, dtype=np.uint8)
            image[:20] = 80
            Image.fromarray(image).save(path)
            decoded, _ = analysis_image(path, True)
            self.assertEqual(decoded.dtype, np.uint8)
            self.assertEqual(decoded.nbytes, 40 * 40 * 3)
            mask = np.zeros((40, 40), bool)
            mask[:20] = True
            fit = {'matrix': np.eye(3).tolist(), 'profile_hash': 'test'}
            self.assertEqual(measure(decoded, mask, ~mask, fit),
                             measure(image.astype(float) / 255, mask, ~mask, fit))
            np.testing.assert_allclose(patch_medians(decoded, [[0, 0, 20, 20]]), [[80/255]*3])

    def test_draft_survives_reopen_and_does_not_create_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'journal')
            try:
                session = store.create_session('2026-10')
                mole = store.add_mole(REGIONS[0], '测试位置')
                path = Path(tmp) / 'sample.png'
                Image.new('RGB', (30, 30), 'gray').save(path)
                photo = store.import_photo(path, session, 'detail')
                payload = {'masks': {'mole': []}, 'points': [[2, 3]], 'mode': 1,
                           'notes': '未完成草稿', 'profile': None, 'srgb': False, 'ordinary': True}
                store.save_draft(mole, session, photo, payload)
                backup=Path(tmp)/'with-draft.zip'
                store.backup(backup)
                restore_backup(backup,Path(tmp)/'restored')
                restored=Store(Path(tmp)/'restored')
                try:self.assertEqual(restored.load_draft(mole,session,photo),payload)
                finally:restored.close()
                store.close()
                store = Store(Path(tmp) / 'journal')
                self.assertEqual(store.load_draft(mole, session, photo), payload)
                self.assertEqual(store.observations(mole), [])
                store.clear_draft(mole, session, photo)
                self.assertIsNone(store.load_draft(mole, session, photo))
            finally:
                store.close()

    def test_backup_limits_accept_more_than_one_gib_but_remain_bounded(self):
        from moletracker.store import check_backup_limits
        check_backup_limits(2, 1024**3 + 1, 100)
        with self.assertRaises(ValueError):check_backup_limits(2, 16*1024**3 + 1, 100)

    def test_backup_capacity_and_latest_monthly_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'journal')
            try:
                session = store.create_session('2026-10')
                mole = store.add_mole(REGIONS[0], '测试位置')
                path = Path(tmp) / 'sample.png'
                Image.new('RGB', (30, 30), 'gray').save(path)
                photo = store.import_photo(path, session, 'detail')
                store.save_observation(mole, session, photo, {}, None, 'retake', '重拍')
                store.save_observation(mole, session, photo, {}, None, 'uncalibrated', '已重拍')
                self.assertEqual(store.monthly_status(session)[mole], 'uncalibrated')
                info = store.backup_capacity()
                self.assertGreaterEqual(info['original_bytes'], path.stat().st_size)
                self.assertEqual(info['photos'], 1)
                self.assertEqual(info['limit_bytes'], 16 * 1024**3)
            finally:
                store.close()
