"""Generate geometric synthetic fixtures; never use this profile for real photos."""
import argparse
import json
from pathlib import Path
from moletracker.store import Store, REGIONS
from moletracker.color import analysis_image, fit_reference, patch_medians, polygon_mask, measure
from tests.test_integration import fixture


def main():
    parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path);args=parser.parse_args()
    if args.destination.exists():parser.error('Choose a new directory; existing data will never be overwritten')
    args.destination.mkdir(parents=True)
    store=Store(args.destination/'journal')
    mole=store.add_mole(REGIONS[1],'合成色块 A · 仅软件测试，不是真实痣')
    for month,level in [('2026-08',.32),('2026-09',.4)]:
        path=args.destination/(month+'.png');profile,masks=fixture(path,level)
        (args.destination/'SYNTHETIC-ONLY-profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8')
        session=store.create_session(month);photo=store.import_photo(path,session,'detail')
        image,source=analysis_image(path,True);fit=fit_reference(patch_medians(image,masks['patches']),profile)
        measurement=measure(image,polygon_mask((360,240),masks['mole']),polygon_mask((360,240),masks['skin']),fit)
        measurement['color_source']=source;measurement['manual_qc']=[True]*4
        store.save_observation(mole,session,photo,masks,measurement,'comparable','全部为生成色块；仅用于练习操作')
    store.close()
    print(f'Generated SYNTHETIC demo. Run: python -m moletracker --data "{args.destination / "journal"}"')


if __name__=='__main__':main()
