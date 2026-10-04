"""Local journal and integrity-checked portable backups. No network functions."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import uuid
import warnings
import zipfile
from PIL import Image
from .validation import validate_observation

REGIONS = ('头面耳颈 / scalp 头皮','前躯干与两侧','背部','手臂与腋下','双手、指缝和指甲',
           '腿部与可见褶皱','双脚、趾缝、足底和趾甲','可选外部皮肤黏膜交界')
COVERAGE = ('pending','reviewed','not_photographed','needs_retake')
MAX_FILE = 40*1024*1024
MAX_PIXELS = 30_000_000
MAX_BACKUP = 1024*1024*1024
MAX_MANIFEST = 10*1024*1024
MAX_MEMBERS = 10000
MAX_RECORDS = 100000
TABLES = ('sessions','moles','photos','observations','coverage','audit')


def now(): return datetime.now(timezone.utc).isoformat()
def identifier(): return uuid.uuid4().hex

def text(value, limit=2000):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError('请输入有效文字，且不要超过长度限制')
    return value.strip()

def validate_image(raw):
    if len(raw)>MAX_FILE: raise ValueError('单张照片不能超过 40 MiB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as img:
                if img.format not in ('JPEG','PNG') or img.width*img.height>MAX_PIXELS:
                    raise ValueError('仅支持最多 3000 万像素的 JPEG/PNG 原件')
                width,height=img.size
                fmt=img.format
                img.verify()
            with Image.open(io.BytesIO(raw)) as img: img.load()
        return width,height,fmt
    except Exception as exc:
        raise ValueError('照片损坏、不支持或超出安全尺寸限制') from exc


class Store:
    def __init__(self, root):
        self.root=Path(root).expanduser().resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        (self.root/'originals').mkdir(exist_ok=True)
        self.db=sqlite3.connect(self.root/'journal.sqlite3')
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, month TEXT UNIQUE NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS moles(id TEXT PRIMARY KEY, region TEXT NOT NULL, location TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS photos(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), hash TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, role TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, mole_id TEXT NOT NULL REFERENCES moles(id), session_id TEXT NOT NULL REFERENCES sessions(id), photo_id TEXT NOT NULL REFERENCES photos(id), masks TEXT NOT NULL, measurement TEXT, status TEXT NOT NULL, notes TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS coverage(session_id TEXT NOT NULL REFERENCES sessions(id), region TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(session_id,region));
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY, observation_id TEXT REFERENCES observations(id), detail TEXT NOT NULL, created TEXT NOT NULL);
        ''')
        self.db.commit()

    def close(self): self.db.close()
    def rows(self,query,args=()): return [dict(r) for r in self.db.execute(query,args)]
    def sessions(self): return self.rows('SELECT * FROM sessions ORDER BY month DESC')
    def moles(self): return self.rows('SELECT * FROM moles ORDER BY created,id')
    def photos(self,session): return self.rows('SELECT * FROM photos WHERE session_id=? ORDER BY created',(session,))
    def audit(self): return self.rows('SELECT * FROM audit ORDER BY created')
    def _exists(self,table,key):
        if table not in TABLES or not self.db.execute(f'SELECT 1 FROM {table} WHERE id=?',(key,)).fetchone():
            raise ValueError('所选记录不存在')

    def create_session(self,month):
        if not isinstance(month,str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month):
            raise ValueError('月份格式应为 YYYY-MM')
        if self.db.execute('SELECT 1 FROM sessions WHERE month=?',(month,)).fetchone():
            raise ValueError('该月份已存在，请选择已有记录')
        key=identifier()
        with self.db:self.db.execute('INSERT INTO sessions VALUES (?,?,?)',(key,month,now()))
        return key

    def add_mole(self,region,location):
        if region not in REGIONS: raise ValueError('身体区域无效')
        key=identifier()
        with self.db:self.db.execute('INSERT INTO moles VALUES (?,?,?,?)',(key,region,text(location,500),now()))
        return key

    def edit_mole(self,key,region,location):
        self._exists('moles',key)
        if region not in REGIONS: raise ValueError('身体区域无效')
        before=self.rows('SELECT * FROM moles WHERE id=?',(key,))[0]
        with self.db:
            self.db.execute('UPDATE moles SET region=?,location=? WHERE id=?',(region,text(location,500),key))
            self.db.execute('INSERT INTO audit VALUES (?,?,?,?)',(identifier(),None,json.dumps({'mole_id':key,'before':before,'region':region,'location':location},ensure_ascii=False),now()))

    def import_photo(self,path,session,role):
        self._exists('sessions',session)
        if role not in ('overview','detail'): raise ValueError('照片类型无效')
        path=Path(path)
        if not path.is_file() or path.stat().st_size>MAX_FILE:raise ValueError('文件不存在或超过 40 MiB')
        raw=path.read_bytes();w,h,_=validate_image(raw)
        digest=hashlib.sha256(raw).hexdigest()
        existing=self.db.execute('SELECT id FROM photos WHERE session_id=? AND hash=? AND role=?',(session,digest,role)).fetchone()
        if existing:
            self.photo_path(existing[0])
            return existing[0]
        dest=self.root/'originals'/digest
        if dest.exists() and (not dest.is_file() or dest.stat().st_size > MAX_FILE or hashlib.sha256(dest.read_bytes()).hexdigest() != digest):
            raise ValueError('已有原件校验失败；未新增记录，请从可信备份恢复')
        if not dest.exists():
            with tempfile.NamedTemporaryFile(dir=dest.parent,delete=False) as file:
                tmp=Path(file.name);file.write(raw)
            tmp.replace(dest)
        key=identifier()
        with self.db:self.db.execute('INSERT INTO photos VALUES (?,?,?,?,?,?,?)',(key,session,digest,w,h,role,now()))
        return key

    def photo_path(self,key):
        self._exists('photos',key)
        digest=self.db.execute('SELECT hash FROM photos WHERE id=?',(key,)).fetchone()[0]
        if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('照片索引损坏')
        path=self.root/'originals'/digest
        if not path.is_file() or path.stat().st_size>MAX_FILE or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('照片原件丢失或校验失败；请从可信备份恢复')
        return path

    def save_observation(self,mole,session,photo,masks,measurement,status,notes=''):
        for table,key in [('moles',mole),('sessions',session),('photos',photo)]:self._exists(table,key)
        p=self.rows('SELECT * FROM photos WHERE id=?',(photo,))[0]
        self.photo_path(photo)
        validate_observation(status, masks, measurement, p, session)
        if not isinstance(notes,str) or len(notes)>5000:
            raise ValueError('观察文字无效')
        encoded_masks=json.dumps(masks,allow_nan=False,sort_keys=True)
        encoded_measurement=json.dumps(measurement,allow_nan=False,sort_keys=True) if measurement else None
        existing=self.db.execute('SELECT id FROM observations WHERE mole_id=? AND session_id=? AND photo_id=? AND masks=? AND measurement IS ? AND status=? AND notes=?',
            (mole,session,photo,encoded_masks,encoded_measurement,status,notes)).fetchone()
        if existing:return existing[0]
        key=identifier()
        with self.db:self.db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)',
            (key,mole,session,photo,encoded_masks,encoded_measurement,status,notes,now()))
        return key

    def observations(self,mole):
        result=self.rows('SELECT o.*, s.month FROM observations o JOIN sessions s ON s.id=o.session_id WHERE mole_id=? ORDER BY s.month,o.created',(mole,))
        for row in result:
            row['masks']=json.loads(row['masks']);row['measurement']=json.loads(row['measurement']) if row['measurement'] else None
        return result

    def correct_identity(self,observation,target,reason):
        self._exists('observations',observation);self._exists('moles',target)
        before=self.db.execute('SELECT mole_id FROM observations WHERE id=?',(observation,)).fetchone()[0]
        detail=json.dumps({'from':before,'to':target,'reason':text(reason)},ensure_ascii=False)
        with self.db:
            self.db.execute('UPDATE observations SET mole_id=? WHERE id=?',(target,observation))
            self.db.execute('INSERT INTO audit VALUES (?,?,?,?)',(identifier(),observation,detail,now()))

    def coverage(self,session):
        self._exists('sessions',session)
        states={r:'pending' for r in REGIONS}
        states.update({r['region']:r['state'] for r in self.rows('SELECT * FROM coverage WHERE session_id=?',(session,))})
        return states

    def set_coverage(self,session,region,state):
        self._exists('sessions',session)
        if region not in REGIONS or state not in COVERAGE:raise ValueError('覆盖状态无效')
        with self.db:self.db.execute('INSERT OR REPLACE INTO coverage VALUES (?,?,?)',(session,region,state))

    def missing(self,session):
        return [r['id'] for r in self.rows('SELECT id FROM moles WHERE id NOT IN (SELECT mole_id FROM observations WHERE session_id=?) ORDER BY created,id',(session,))]

    def backup(self,path):
        path=Path(path)
        if path.exists():raise ValueError('备份文件已存在；请选择新文件名')
        data={'format':1,'tables':{t:self.rows(f'SELECT * FROM {t}') for t in TABLES}}
        if any(len(rows)>MAX_RECORDS for rows in data['tables'].values()):
            raise ValueError('备份记录数超过本版本恢复限制；未发布备份')
        for observation in data['tables']['observations']:
            photo=self.rows('SELECT * FROM photos WHERE id=?',(observation['photo_id'],))[0]
            validate_observation(observation['status'],json.loads(observation['masks']),
                json.loads(observation['measurement']) if observation['measurement'] else None,photo,observation['session_id'])
        hashes={r['hash'] for r in data['tables']['photos']}
        manifest=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8')
        sizes=[len(manifest)]+[(self.root/'originals'/digest).stat().st_size for digest in hashes]
        check_backup_limits(len(sizes),sum(sizes),len(manifest))
        # Validate before publishing a backup; interrupted writes never replace existing data.
        with tempfile.NamedTemporaryFile(dir=path.parent,suffix='.tmp',delete=False) as tmp:temp=Path(tmp.name)
        try:
            with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json',manifest)
                for digest in sorted(hashes):
                    raw=(self.root/'originals'/digest).read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('原件校验失败，备份已中止')
                    archive.writestr('originals/'+digest,raw)
            temp.replace(path)
        finally:
            if temp.exists():temp.unlink()


def check_backup_limits(members, total_bytes, manifest_bytes):
    if members > MAX_MEMBERS or total_bytes > MAX_BACKUP or manifest_bytes > MAX_MANIFEST:
        raise ValueError('备份超出本版本可恢复限制（解压后 1 GiB、10000 文件、清单 10 MiB）。未发布备份；请保留资料目录的离线副本，勿删除原件')


def restore_backup(source,destination):
    """Restore into a new directory only; reject unknown members and traversal."""
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('恢复目标必须是一个尚不存在的新文件夹')
    with zipfile.ZipFile(source) as archive:
        entries=archive.infolist();names=[e.filename for e in entries]
        if len(names)!=len(set(names)) or 'manifest.json' not in names:
            raise ValueError('备份缺少清单或存在重复成员')
        check_backup_limits(len(names),sum(e.file_size for e in entries),archive.getinfo('manifest.json').file_size)
        try:data=json.loads(archive.read('manifest.json'))
        except Exception as exc:raise ValueError('备份清单损坏') from exc
        if not isinstance(data,dict) or data.get('format')!=1 or set(data.get('tables',{}))!=set(TABLES):raise ValueError('备份格式不支持')
        tables=data['tables']
        if any(not isinstance(tables[t],list) or len(tables[t])>MAX_RECORDS for t in TABLES):raise ValueError('备份记录无效')
        try:hashes={p['hash'] for p in tables['photos']}
        except (KeyError,TypeError) as exc:raise ValueError('照片清单损坏') from exc
        if any(not isinstance(h,str) or not re.fullmatch('[a-f0-9]{64}',h) for h in hashes):raise ValueError('照片哈希无效')
        if set(names)!={'manifest.json'}|{'originals/'+h for h in hashes}:raise ValueError('备份包含未知文件或缺少原件')
        destination.parent.mkdir(parents=True,exist_ok=True)
        staging=Path(tempfile.mkdtemp(prefix='.mole-restore-',dir=destination.parent))
        restored=None
        try:
            restored=Store(staging)
            for h in hashes:
                if archive.getinfo('originals/'+h).file_size>MAX_FILE:raise ValueError('备份照片超过限制')
                raw=archive.read('originals/'+h)
                if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('备份原件校验失败')
                validate_image(raw);(staging/'originals'/h).write_bytes(raw)
            with restored.db:
                for table in TABLES:
                    cols=[r[1] for r in restored.db.execute(f'PRAGMA table_info({table})')]
                    for row in tables[table]:
                        if not isinstance(row,dict) or set(row)!=set(cols):raise ValueError('备份字段不匹配')
                        if any(not isinstance(v,(str,int,type(None))) for v in row.values()):raise ValueError('备份字段类型错误')
                        restored.db.execute(f'INSERT INTO {table} VALUES ({",".join("?" for _ in cols)})',[row[c] for c in cols])
            # Validate domain values and JSON, not only SQL references.
            for r in restored.sessions():
                if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',r['month']):raise ValueError('备份月份无效')
            for m in restored.moles():
                if m['region'] not in REGIONS:raise ValueError('备份区域无效')
                text(m['location'],500)
                for o in restored.observations(m['id']):
                    photo=restored.rows('SELECT * FROM photos WHERE id=?',(o['photo_id'],))[0]
                    validate_observation(o['status'],o['masks'],o['measurement'],photo,o['session_id'])
            for r in restored.rows('SELECT * FROM coverage'):
                if r['region'] not in REGIONS or r['state'] not in COVERAGE:raise ValueError('备份覆盖状态无效')
            for p in restored.rows('SELECT * FROM photos'):
                w,h,_=validate_image(restored.photo_path(p['id']).read_bytes())
                if (w,h)!=(p['width'],p['height']) or p['role'] not in ('detail','overview'):raise ValueError('备份照片元数据无效')
            restored.close();restored=None
            staging.rename(destination)
        except (sqlite3.Error,KeyError,TypeError,json.JSONDecodeError) as exc:
            raise ValueError('备份记录损坏或引用不一致') from exc
        finally:
            if restored:restored.close()
            if staging.exists():shutil.rmtree(staging)
