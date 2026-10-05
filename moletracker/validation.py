"""One domain gate for saved/restored observations and numeric comparison."""
import math
import re
import numpy as np
from .color import METHOD, MIN_PIXELS, fit_reference, polygon_mask


def validate_observation(status, masks, measurement, photo, session):
    """Complete persisted record gate. Geometry/photo context is never optional."""
    try:
        if not isinstance(masks,dict) or not isinstance(photo,dict) or not isinstance(session,str):
            raise ValueError('完整观察必须包含掩膜字典、照片和月份来源')
        if status not in ('comparable','uncalibrated','retake'):
            raise ValueError('观察状态无效')
        if photo['session_id'] != session or photo['role'] not in ('detail','overview'):
            raise ValueError('观察、照片与月份不一致')
        context=masks.get('capture_context')
        if 'capture_context' in masks and (not isinstance(context,dict) or
                set(context) != {'srgb_assumed','ordinary_skin'} or
                any(type(v) is not bool for v in context.values())):
            raise ValueError('拍摄假设记录无效')
        if status=='comparable':
            validate_measurement(measurement)
            if photo['role'] != 'detail':
                raise ValueError('可比较记录需要近照')
        elif measurement is not None:
            raise ValueError('不合格记录不能包含可比较数值')
        _geometry(masks,measurement,(photo['width'],photo['height']))
    except (KeyError,TypeError,AttributeError,OverflowError,np.linalg.LinAlgError) as exc:
        raise ValueError('观察或测量来源记录不完整 / 无效') from exc


def validate_measurement(measurement):
    """Explicit measurement-only gate for deltas; never used to admit records."""
    try:
        _measurement(measurement)
    except (KeyError,TypeError,AttributeError,OverflowError,np.linalg.LinAlgError) as exc:
        raise ValueError('测量来源记录不完整 / 无效') from exc


def _measurement(m):
    if not isinstance(m, dict) or m.get('method') != METHOD or type(m.get('ordinary_skin')) is not bool:
        raise ValueError('缺少受支持的方法或组织类型')
    if m.get('manual_qc') != [True]*4 or any(type(v) is not bool for v in m['manual_qc']):
        raise ValueError('缺少完整人工质控确认')
    source=m.get('color_source')
    if source not in ('explicit-sRGB-assumption', 'EXIF-sRGB') and not (
            isinstance(source,str) and re.fullmatch(r'ICC-to-sRGB:[a-f0-9]{64}',source)):
        raise ValueError('缺少可信色彩空间来源')
    fit=m['fit']
    refit=fit_reference(fit['patch_rgb'], fit['profile'])
    if (fit.get('method') != METHOD or m.get('profile_hash') != refit['profile_hash'] or
            fit.get('profile_hash') != refit['profile_hash']):
        raise ValueError('参考配置与哈希 / 方法不一致')
    for key in ('matrix','rmse','condition'):
        actual=np.asarray(fit[key],dtype=float)
        expected=np.asarray(refit[key],dtype=float)
        if actual.shape != expected.shape or not np.isfinite(actual).all() or not np.allclose(actual,expected,rtol=1e-8,atol=1e-10):
            raise ValueError('保存的拟合与参考样本不一致')
    def number(key,lower,upper):
        value=m.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError('测量值缺失、非有限或超出范围')
        return value
    number('mole_l',0,102)
    if type(m.get('mole_pixels')) is not int or m['mole_pixels'] < MIN_PIXELS:
        raise ValueError('目标有效像素来源无效')
    if m['ordinary_skin']:
        number('skin_l',0,102)
        d=number('d',-102,102)
        if not math.isclose(d,m['skin_l']-m['mole_l'],abs_tol=1e-8):
            raise ValueError('D 与独立 L* 值不一致')
        if type(m.get('skin_pixels')) is not int or m['skin_pixels'] < MIN_PIXELS:
            raise ValueError('皮肤有效像素来源无效')
    elif m.get('skin_l','missing') is not None or m.get('d','missing') is not None or m.get('skin_pixels') != 0:
        raise ValueError('非普通皮肤不能使用正常皮肤基线')


def _geometry(masks,measurement,size):
    for key in ('mole','skin','exclude','patches'):
        if key in masks and not isinstance(masks[key],list):
            raise ValueError('区域、排除区和参考框必须使用列表，包括空列表')
    def polygon_structure(points):
        if not isinstance(points,list) or any(not isinstance(point,list) or len(point)!=2 or
                any(type(value) not in (int,float) or not math.isfinite(value) for value in point) for point in points):
            raise ValueError('多边形必须是有限数值坐标对的列表')
    if masks.get('coordinate_system','original-unrotated-raster') != 'original-unrotated-raster':
        raise ValueError('不支持的掩膜坐标系')
    exclusions=masks.get('exclude',[])
    for poly in exclusions:
        polygon_structure(poly)
        polygon_mask(size,poly)
    regions={}
    for key in ('mole','skin'):
        points=masks.get(key,[])
        polygon_structure(points)
        if points:
            regions[key]=polygon_mask(size,points,exclusions)
    rectangles=masks.get('patches',[])
    for rect in rectangles:
        if not isinstance(rect,list) or len(rect)!=4 or any(type(value) not in (int,float) or not math.isfinite(value) for value in rect):
            raise ValueError('参考框坐标无效')
        x1,y1,x2,y2=rect
        if not 0 <= x1 < x2 <= size[0] or not 0 <= y1 < y2 <= size[1]:
            raise ValueError('参考框超出原图或为空')
    if measurement is not None:
        if 'mole' not in regions or int(regions['mole'].sum()) != measurement['mole_pixels']:
            raise ValueError('痣掩膜与测量像素来源不一致')
        if measurement['ordinary_skin'] and ('skin' not in regions or
                int(regions['skin'].sum()) != measurement['skin_pixels'] or
                np.any(regions['mole'] & regions['skin'])):
            raise ValueError('皮肤掩膜与测量像素来源不一致')
        if len(rectangles) != len(measurement['fit']['patch_rgb']):
            raise ValueError('参考框与测量来源不一致')


def validate_draft_geometry(masks, size):
    """Bounded, allocation-free structure gate; unfinished editing is allowed."""
    if not isinstance(masks, dict) or masks.get('coordinate_system', 'original-unrotated-raster') != 'original-unrotated-raster':
        raise ValueError('草稿坐标系无效')
    if 'capture_context' in masks:
        context=masks['capture_context']
        if not isinstance(context,dict) or set(context)!={'srgb_assumed','ordinary_skin'} or any(type(v) is not bool for v in context.values()):
            raise ValueError('草稿拍摄假设无效')
    def polygon(points):
        if not isinstance(points, list) or len(points) > 10000 or 0<len(points)<3:
            raise ValueError('草稿多边形无效或点数过多')
        for point in points:
            if (not isinstance(point, list) or len(point) != 2 or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in point) or
                    not (0 <= point[0] < size[0] and 0 <= point[1] < size[1])):
                raise ValueError('草稿多边形超出原图或坐标无效')
    for key in ('mole', 'skin'):
        polygon(masks.get(key, []))
    exclusions = masks.get('exclude', [])
    patches = masks.get('patches', [])
    if not isinstance(exclusions, list) or not isinstance(patches, list) or len(exclusions) + len(patches) > 1000:
        raise ValueError('草稿区域数量无效')
    for points in exclusions:
        polygon(points)
    for rect in patches:
        if (not isinstance(rect, list) or len(rect) != 4 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in rect) or
                not (0 <= rect[0] < rect[2] <= size[0] and 0 <= rect[1] < rect[3] <= size[1])):
            raise ValueError('草稿色卡框无效')
