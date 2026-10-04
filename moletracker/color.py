"""Experimental photographic color measurement. No diagnostic interpretation."""
import hashlib
import io
import json
import numpy as np
from PIL import Image, ImageCms, ImageDraw

METHOD = 'manual-linear-srgb-xyz-d50-lab-v1'
MIN_PIXELS = 100
MAX_RMSE = .025  # XYZ scale Y=1; engineering gate, not clinical accuracy
WHITE = np.array([.96422, 1., .82521])


def linearize(rgb):
    rgb = np.asarray(rgb, dtype=float)
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def encode(rgb):
    rgb = np.asarray(rgb, dtype=float)
    return np.where(rgb <= .0031308, 12.92 * rgb, 1.055 * np.maximum(rgb, 0) ** (1 / 2.4) - .055)


def analysis_image(path, assume_srgb=False):
    """Raw stored raster orientation. ICC-convert a copy; never modify original."""
    with Image.open(path) as original:
        if original.mode not in ('RGB', 'RGBA'):
            raise ValueError('仅支持 RGB 照片；请保留原件并另导出标准 sRGB 副本')
        if original.mode == 'RGBA' and original.getextrema()[3] != (255, 255):
            raise ValueError('不支持透明照片')
        icc = original.info.get('icc_profile')
        provenance = 'explicit-sRGB-assumption'
        if icc:
            try:
                source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                result = ImageCms.profileToProfile(original.convert('RGB'), source,
                    ImageCms.createProfile('sRGB'), outputMode='RGB')
                provenance = 'ICC-to-sRGB:' + hashlib.sha256(icc).hexdigest()
            except Exception as exc:
                raise ValueError('ICC 色彩配置无法解释，不能计算可比较数值') from exc
        else:
            # EXIF ColorSpace 1 identifies sRGB; other/absent tags require explicit assumption.
            exif = original.getexif()
            try:
                exif_space = exif.get_ifd(0x8769).get(0xA001)
            except (KeyError, TypeError, ValueError):
                exif_space = None
            if exif_space == 1:
                provenance = 'EXIF-sRGB'
            elif not assume_srgb:
                raise ValueError('无可信色彩配置；请确认来源为 sRGB，或仅保存未校准照片')
            result = original.convert('RGB')
        return np.asarray(result, dtype=float) / 255., provenance


def reference_xyz(profile):
    """Validate explicit reference targets independently from camera samples."""
    if not isinstance(profile,dict) or profile.get('white')!='D50' or str(profile.get('observer'))!='2':
        raise ValueError('色卡配置必须声明 D50 / 2°')
    if not profile.get('name') or not profile.get('source'):
        raise ValueError('色卡配置必须记录名称和可信参考值来源')
    if 'source_metadata' in profile:
        from .reference import normalize_source_metadata, FORMATS
        columns=profile.get('import_columns')
        if (not isinstance(profile['source_metadata'],dict) or not isinstance(columns,list) or
                len(columns)!=4 or profile.get('import_format') not in FORMATS):
            raise ValueError('导入参考配置缺少原始列或单位来源')
        normalize_source_metadata(profile['source_metadata'],columns[1:],profile['import_format'])
    target=np.asarray(profile.get('xyz'),dtype=float)
    if target.ndim!=2 or target.shape[1:]!=(3,) or not 6<=len(target)<=256:
        raise ValueError('需要 6–256 个对应彩色参考块（不能仅灰阶）')
    if not np.isfinite(target).all() or np.any(target<0) or np.any(target>1.5):
        raise ValueError('参考值必须有限；XYZ 标度应为 Y=1')
    if (np.linalg.matrix_rank(target)<3 or np.linalg.cond(target)>100 or
            np.ptp(target[:,1])<.05 or np.max(target[:,1])<.1):
        raise ValueError('参考 XYZ 颜色退化、亮度范围不足或标度不正确')
    ids=profile.get('patch_ids')
    if ids is not None and (not isinstance(ids,list) or len(ids)!=len(target) or
            any(not isinstance(v,str) or not v.strip() for v in ids) or len(ids)!=len(set(ids))):
        raise ValueError('色块标签必须唯一并与参考数值一一对应')
    return target


def fit_reference(patches, profile):
    """Fit observed encoded-sRGB patch medians to known XYZ D50, scale Y=1."""
    target=reference_xyz(profile)
    observed=np.asarray(patches,dtype=float)
    if observed.shape!=target.shape or not np.isfinite(observed).all():
        raise ValueError('观察参考块数量必须与配置一致且数值有限')
    if np.any(observed <= 2/255) or np.any(observed >= 253/255):
        raise ValueError('参考块通道接近裁切，请重新拍摄')
    linear = linearize(observed)
    if np.linalg.matrix_rank(linear) < 3 or np.linalg.cond(linear) > 100:
        raise ValueError('参考颜色不足或病态；不能可靠拟合，请检查色卡与标记')
    matrix, _, _, _ = np.linalg.lstsq(linear, target, rcond=None)
    if (not np.isfinite(matrix).all() or np.linalg.matrix_rank(matrix) < 3 or
            np.linalg.cond(matrix) > 100 or np.linalg.norm(matrix[:,1]) < .01):
        raise ValueError('拟合变换退化或亮度映射不足，不能用于比较')
    rmse = float(np.sqrt(np.mean((linear @ matrix - target)**2)))
    if rmse > MAX_RMSE:
        raise ValueError(f'色卡拟合误差过大 ({rmse:.4f})，请检查对应顺序、阴影和曝光并重拍')
    canonical = json.dumps(profile, sort_keys=True, allow_nan=False, ensure_ascii=False)
    return {'matrix':matrix.tolist(), 'rmse':rmse, 'condition':float(np.linalg.cond(linear)),
            'profile_hash':hashlib.sha256(canonical.encode()).hexdigest(), 'profile':profile,
            'patch_rgb':observed.tolist(), 'method':METHOD}


def polygon_mask(size, vertices, exclusions=()):
    """size=(width,height); all vertices refer to original, unrotated raster."""
    w,h = size
    def check(poly):
        p = np.asarray(poly, dtype=float)
        if p.ndim != 2 or p.shape[1:] != (2,) or len(p) < 3 or not np.isfinite(p).all():
            raise ValueError('多边形至少需要 3 个有效点')
        if np.any(p < 0) or np.any(p[:,0] >= w) or np.any(p[:,1] >= h):
            raise ValueError('标记坐标超出原图范围')
        return [tuple(v) for v in p]
    canvas = Image.new('1', size)
    draw = ImageDraw.Draw(canvas)
    draw.polygon(check(vertices),fill=1)
    for poly in exclusions:
        draw.polygon(check(poly),fill=0)
    return np.array(canvas,dtype=bool)


def patch_medians(image, rectangles):
    h,w = image.shape[:2]
    values=[]
    for rect in rectangles:
        if len(rect) != 4 or not all(np.isfinite(rect)):
            raise ValueError('参考块矩形无效')
        x1,y1,x2,y2=map(int,rect)
        if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h) or (x2-x1)*(y2-y1) < MIN_PIXELS:
            raise ValueError('每个参考块至少 100 像素，且需位于原图内')
        pixels=image[y1:y2,x1:x2].reshape(-1,3)
        _pixel_qc(pixels)
        values.append(np.median(pixels,axis=0))
    return values


def _pixel_qc(pixels):
    if len(pixels) < MIN_PIXELS:
        raise ValueError('有效区域不足 100 像素，请近距离重新拍摄并检查标记')
    if not np.isfinite(pixels).all() or np.any(pixels < 0) or np.any(pixels > 1):
        raise ValueError('图像数值无效')
    clipped = np.mean(np.any((pixels <= 2/255) | (pixels >= 253/255),axis=1))
    if clipped > .01:
        raise ValueError('所选区域超过 1% 像素接近通道裁切，请重拍或排除反光')


def _lstar(pixels, matrix):
    xyz = linearize(pixels) @ np.asarray(matrix)
    if np.any(xyz < 0) or np.any(xyz[:,1] > 1.05):
        raise ValueError('转换结果超出合理范围；请检查参考和照明')
    ratio=xyz[:,1]/WHITE[1]
    f=np.where(ratio > (6/29)**3,np.cbrt(ratio),ratio/(3*(6/29)**2)+4/29)
    return float(np.median(116*f-16))


def measure(image, mole_mask, skin_mask, fit, ordinary_skin=True):
    image=np.asarray(image,dtype=float)
    if image.ndim != 3 or image.shape[2] != 3 or mole_mask.shape != image.shape[:2]:
        raise ValueError('图像和掩膜尺寸不一致')
    pixels=image[mole_mask]
    _pixel_qc(pixels)
    mole_l=_lstar(pixels,fit['matrix'])
    skin_l=None
    if ordinary_skin:
        if skin_mask is None or skin_mask.shape != mole_mask.shape or np.any(mole_mask & skin_mask):
            raise ValueError('请选择与痣不重叠的邻近正常皮肤')
        _pixel_qc(image[skin_mask]);skin_l=_lstar(image[skin_mask],fit['matrix'])
    return {'mole_l':mole_l,'skin_l':skin_l,'d':None if skin_l is None else skin_l-mole_l,
            'method':METHOD,'profile_hash':fit['profile_hash'], 'fit':fit,
            'mole_pixels':int(mole_mask.sum()),'skin_pixels':int(skin_mask.sum()) if ordinary_skin else 0,
            'ordinary_skin':ordinary_skin}


def delta(before, after):
    from .validation import validate_measurement
    try:
        validate_measurement(before)
        validate_measurement(after)
    except ValueError:
        return None
    if any(before[k] != after[k] for k in ('method','profile_hash','ordinary_skin')):
        return None
    return {k:None if before[k] is None or after[k] is None else after[k]-before[k]
            for k in ('mole_l','skin_l','d')}
