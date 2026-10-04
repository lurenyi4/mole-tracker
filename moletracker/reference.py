"""Offline, explicit vendor-reference import. No bundled commercial values."""
import csv
import hashlib
import io
import shlex
import numpy as np
from .color import WHITE, reference_xyz

FORMATS=('Lab D50','XYZ 0–100','XYZ 0–1')


def lab_to_xyz(values):
    lab=np.asarray(values,dtype=float)
    if lab.ndim!=2 or lab.shape[1]!=3 or not np.isfinite(lab).all() or np.any(lab[:,0]<0) or np.any(lab[:,0]>100) or np.any(np.abs(lab[:,1:])>160):
        raise ValueError('Lab 数值无效；L* 应为 0–100，a*/b* 保留正负号')
    fy=(lab[:,0]+16)/116
    f=np.stack((fy+lab[:,1]/500,fy,fy-lab[:,2]/200),axis=1)
    return np.where(f>6/29,f**3,3*(6/29)**2*(f-4/29))*WHITE


def read_reference(content):
    if not isinstance(content,str) or len(content.encode('utf-8'))>1_000_000:
        raise ValueError('参考文件必须是最多 1 MB 的 UTF-8 文本')
    content=content.lstrip('\ufeff')
    metadata={}
    if 'BEGIN_DATA_FORMAT' in content:
        columns=[];rows=[];mode=None
        for line in content.splitlines():
            tokens=shlex.split(line,comments=True)
            if not tokens:continue
            key=tokens[0].upper()
            if len(tokens)==1 and key in ('CTI3','CGATS.17','CGATS.5'):
                if 'FILE_FORMAT' in metadata and metadata['FILE_FORMAT']!=key:
                    raise ValueError('只支持单一参考数据表')
                metadata['FILE_FORMAT']=key
                continue
            if key=='BEGIN_DATA_FORMAT':mode='columns';continue
            if key=='END_DATA_FORMAT':mode=None;continue
            if key=='BEGIN_DATA':mode='data';continue
            if key=='END_DATA':mode=None;continue
            if mode=='columns':columns.extend(tokens)
            elif mode=='data':rows.append(tokens)
            elif len(tokens)>=2 and key!='KEYWORD':
                value=' '.join(tokens[1:]).strip()
                if key in metadata and metadata[key].casefold()!=value.casefold():
                    raise ValueError('参考文件包含相互冲突的重复声明：'+key)
                metadata[key]=value
        for key,count in [('NUMBER_OF_FIELDS',len(columns)),('NUMBER_OF_SETS',len(rows))]:
            if key in metadata and metadata[key]!=str(count):raise ValueError('CGATS 声明的字段 / 色块数量不匹配')
    else:
        try:dialect=csv.Sniffer().sniff(content[:4096],delimiters=',;\t')
        except csv.Error:raise ValueError('未识别 CSV 分隔符或 CGATS 数据表')
        table=list(csv.reader(io.StringIO(content),dialect))
        columns=table[0] if table else [];rows=[r for r in table[1:] if any(v.strip() for v in r)]
    columns=[c.strip() for c in columns]
    if not columns or len(columns)!=len(set(columns)) or not rows or len(rows)>256 or any(len(r)!=len(columns) for r in rows):
        raise ValueError('参考表需有唯一列名、1–256 个色块，且各行列数一致')
    return {'columns':columns,'rows':rows,'metadata':metadata,'sha256':hashlib.sha256(content.encode()).hexdigest()}


def normalize_source_metadata(raw, mapped_columns, kind):
    """Narrow CGATS consistency gate; no adaptation or arbitrary dialect support."""
    metadata={}
    for original,value in raw.items():
        key=original.strip().upper()
        value=value.strip()
        if key in metadata and metadata[key].casefold()!=value.casefold():
            raise ValueError('参考文件包含相互冲突的重复声明：'+key)
        metadata[key]=value
    supported={'ILLUMINANT','ILLUMINATION_NAME','ILLUMINANT_WHITE_POINT_XYZ',
               'OBSERVER_ANGLE','OBSERVER','COLOR_REP','NORMALIZED_TO_Y_100'}
    for key in metadata:
        if key not in supported and any(word in key for word in ('ILLUM','OBSERVER','WHITE','COLOR_REP','COLOUR_REP','UNIT','SCALE','NORMALIZED','LUMINANCE')):
            raise ValueError('不支持的参考条件声明：'+key+'；请获取明确的受支持导出')
    white=None
    for key in ('ILLUMINANT','ILLUMINATION_NAME'):
        if key in metadata:
            if metadata[key].upper()!='D50':
                raise ValueError('文件光源声明不是 D50')
            white='D50'
    if 'ILLUMINANT_WHITE_POINT_XYZ' in metadata:
        try:
            xyz=np.array([float(v) for v in metadata['ILLUMINANT_WHITE_POINT_XYZ'].split()])
        except ValueError as exc:
            raise ValueError('数值白点声明无效') from exc
        if xyz.shape!=(3,) or not np.isfinite(xyz).all() or np.any(xyz<=0):
            raise ValueError('数值白点必须包含三个有限正值')
        normalized=xyz/xyz[1]
        # Allow rounded vendor white points, not a change of illuminant.
        if not np.allclose(normalized,WHITE,rtol=0,atol=.0005):
            raise ValueError('参考数值白点不是 D50；不能通过选择框重新标为 D50')
        white='D50'
    observer=None
    for key in ('OBSERVER_ANGLE','OBSERVER'):
        if key in metadata:
            if metadata[key].lower() not in ('2','2.0','2 degree'):
                raise ValueError('文件观察者声明不是 2°')
            observer='2'
    selected='LAB' if kind=='Lab D50' else 'XYZ'
    declared=None
    if 'COLOR_REP' in metadata:
        parts=metadata['COLOR_REP'].upper().split('_')
        cie=[p for p in parts if p in ('XYZ','LAB')]
        if len(cie)!=1:
            raise ValueError('不支持或矛盾的 COLOR_REP；请获取单一 Lab 或 XYZ 导出')
        declared=cie[0]
        if declared!=selected:
            raise ValueError('选择的数值类型与文件 COLOR_REP 不一致')
    labels=[label.strip().upper() for label in mapped_columns]
    known_xyz={'XYZ_X':'X','XYZ_Y':'Y','XYZ_Z':'Z','X':'X','Y':'Y','Z':'Z'}
    known_lab={'LAB_L':'L','LAB_A':'A','LAB_B':'B','L':'L','A':'A','B':'B','L*':'L','A*':'A','B*':'B'}
    expected=list('LAB') if selected=='LAB' else list('XYZ')
    selected_names=known_lab if selected=='LAB' else known_xyz
    other_names=known_xyz if selected=='LAB' else known_lab
    for index,label in enumerate(labels):
        if label in other_names or (label in selected_names and selected_names[label]!=expected[index]):
            raise ValueError('所选列名明确表示另一色彩空间或分量顺序；请检查列映射')
    scale=None
    if metadata.get('DEVICE_CLASS','OUTPUT').upper()!='OUTPUT':
        raise ValueError('仅支持反射参考卡数据，不支持显示器 / 其他设备特性文件')
    if metadata.get('FILE_FORMAT')=='CTI3' and selected=='XYZ':
        if kind!='XYZ 0–100':
            raise ValueError('CTI3 XYZ 格式使用 Y=100；请选择 XYZ 0–100')
        scale=100
    if 'NORMALIZED_TO_Y_100' in metadata:
        value=metadata['NORMALIZED_TO_Y_100'].upper()
        if value!='YES':
            raise ValueError('不支持非 Y=100 归一化的该类 CGATS 声明；请获取明确单位导出')
        if selected!='XYZ' or kind!='XYZ 0–100':
            raise ValueError('文件明确声明 Y=100；请选择 XYZ 0–100')
        scale=100
    return {'declared_white':white,'declared_observer':observer,
            'declared_coordinates':declared,'declared_xyz_scale':scale}


def build_profile(table,columns,kind,metadata,confirmed=False):
    if not confirmed:raise ValueError('请先核对实物版本、参考来源、D50 / 2° 与单位')
    required=('manufacturer','model','edition','source','layout','white','observer')
    if any(not isinstance(metadata.get(k),str) or not metadata[k].strip() for k in required):
        raise ValueError('请填写制造商、型号、版本/批次、来源和色块布局')
    if metadata['white']!='D50' or metadata['observer']!='2':
        raise ValueError('当前仅支持明确的 D50 / 2° 数据；不自动猜测或转换其他光源 / 观察者')
    if kind not in FORMATS or len(columns)!=4 or len(set(columns))!=4 or any(c not in table['columns'] for c in columns):
        raise ValueError('请分别选择色块 ID 与三个数值列，并明确单位')
    source_interpretation=normalize_source_metadata(table['metadata'],columns[1:],kind)
    indices=[table['columns'].index(c) for c in columns]
    ids=[row[indices[0]].strip() for row in table['rows']]
    if any(not name or len(name)>60 for name in ids) or len(ids)!=len(set(ids)):
        raise ValueError('色块 ID 必须非空且唯一')
    try:values=np.array([[float(row[i]) for i in indices[1:]] for row in table['rows']])
    except ValueError as exc:raise ValueError('选中的三列必须是数值，使用小数点格式') from exc
    xyz=lab_to_xyz(values) if kind=='Lab D50' else values/(100 if kind=='XYZ 0–100' else 1)
    profile={'name':' / '.join(metadata[k].strip() for k in ('manufacturer','model','edition')),
             'source':metadata['source'].strip(),'white':'D50','observer':'2','xyz':xyz.tolist(),
             'patch_ids':ids,'layout':metadata['layout'].strip(),'card_identity':{k:metadata[k].strip() for k in ('manufacturer','model','edition')},
             'reference_file_sha256':table['sha256'],'import_format':kind,'import_columns':columns,
             'source_metadata':table['metadata'],'source_interpretation':source_interpretation,'source_verified_by_user':True}
    reference_xyz(profile)
    return profile
