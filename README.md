# 痣迹 · 离线照片日志（0.1 原型）

本机手动记录稳定 ID、每月照片、区域覆盖和观察历史。中文原生桌面界面，提供 Windows / Linux / macOS 源码启动说明。历史验收在 Linux 完成，2026-10-04 在 Windows 启用 UTF-8 后复测 39 项全部通过；没有服务器、账号、遥测、云 API、外链资源或照片上传。

**不提供诊断、风险评分、黑色素测量或健康保证。新出现、变化、瘙痒或出血不要等到月度记录，应及时咨询皮肤科。** 数值功能是尚未经过真实设备/临床验证的实验方法。

先看 [中文快速开始](QUICKSTART.zh-CN.md)。最新软件审查结果见 [交付说明](docs/RELEASE_NOTES.md)。

## 安装与启动

需要 Python 3.11+、Tk 8.6（推荐）、Pillow、NumPy。首次安装依赖需要网络或离线 wheel；安装后应用完全离线。仅从 Python 官方发行版、系统发行版和 PyPI 获取依赖。

### Windows（PowerShell）
```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m moletracker --data C:\MoleJournal
```
Python 官方安装器勾选 Tcl/Tk。避免 OneDrive 同步目录。Windows 已完成自动化测试，安装包、长期实际使用和真实设备仍需验证。

### macOS（Terminal）
```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m moletracker --data "$HOME/MoleJournal"
```
建议使用含 Tk 的官方 Python。不要把资料目录放入 iCloud 同步的桌面/文稿。尚未在 macOS 实机运行。

### Linux
```sh
# 先用系统发行版安装 Python 与 python-tk；发行版名称可能不同
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m moletracker --data "$HOME/MoleJournal"
```
需要图形桌面和中文字体（例如 Noto Sans CJK SC）。本次真实 GUI 测试使用 Python 3.13.5、Tk 8.6、Pillow 11.1.0、NumPy 2.2.4；数值测试另在 Python 3.12 / Pillow 12.3.0 / NumPy 2.3.5 通过。当前云环境的 Tk 9 初次显示有中文字形问题，因此推荐 Tk 8.6，并检查本机字体显示。

## 第一次使用
1. 阅读 [拍摄协议](docs/CAPTURE_PROTOCOL.md)；后置手机相机、三脚架/定时器或家人协助、固定柔和照明，以 USB 传原件
2. 新建月份，为每个已有痣建立稳定 ID，写清左/右、身体区域与解剖标志；首次记录不等于新长出
3. 导入概览定位、近照观察。选 ID 与照片，逐点标记痣内部、邻近正常皮肤，完成多边形；排除毛发、反光及边缘。浏览模式拖动平移，＋/−缩放，适合按钮显示全图
4. 数值需实物哑光多色块色卡与可信参考文件。点击「设置实体色卡」导入厂商 CSV / CGATS，在向导选择列和单位（支持 D50/2° Lab 或 XYZ），无需手写 JSON，再按厂商标签顺序框选参考块。未选定色卡时先用照片日志，不伪造可比较数值。详见 [实体色卡设置向导](docs/REFERENCE_SETUP.md) 和 [色彩方法](docs/COLOR.md)
5. 四项质控均需真实检查；模糊/阴影/反光/像素不足应重拍。可明确保存未校准或待重拍照片及原因。黏膜、指甲等关闭「普通皮肤」选项，不套用正常皮肤基线
6. 历史页用 Ctrl（macOS Command）多选两条观察，对比原图局部与 L* / D 差值。没有通用临床阈值；原图未校正的屏幕显示不能作为精确颜色标准
7. 逐区填写覆盖清单；缺少照片不代表没有痣。20–30 处在一小时内完成是尚未验证的真实试用目标

修改掩膜请从历史载入，重新检查后另存观察，原版本保留。身份标错可纠正，留下审计记录。相同照片重复导入及完全相同观察重复保存不会新增重复条目。同一图多个 ID 切换时保留参考框，但需分别标记痣/皮肤并重新质控。

## 本地存储与备份

默认目录 `~/.moletracker`，可用 `--data` 明确指定。SQLite 保存日志；originals 保存 SHA-256 命名的原始文件，字节/EXIF/ICC 不改动。显示采用原始栅格方向，不自动旋转 EXIF，确保标记和测量始终是原始坐标。

「备份到本地」明确导出 ZIP，含全部原件、标记、校准配置与历史。「恢复副本」只写入新目录，不覆盖当前资料；用 `--data` 打开恢复目录。应用不加密，原件可能包含 GPS 等敏感元数据；操作系统同步与备份软件由你管理。使用磁盘加密、合适的本机账户权限和安全离线备份。不要把真实照片放入这个 Git 仓库。数据库崩溃恢复依赖 SQLite 事务；无法保证断电时所有操作均持久化，请定期验证备份。

限制：JPEG/PNG，单张 40 MiB / 3000 万像素；不支持 HEIC/RAW，需在保留原件的前提下另行导出标准色彩副本。全尺寸浮点颜色分析可能占用约 1 GiB 内存（3000 万像素）；建议 8 GiB 以上 RAM，过大图像应使用较低分辨率的相机拍摄模式并确保足够细节。

## 可重复验证
```sh
python -m unittest -v
python -m compileall -q moletracker tests
python -m examples.generate_demo /path/to/new-synthetic-demo
python -m moletracker --data /path/to/new-synthetic-demo/journal
```
无图形桌面时 GUI 测试明确 skipped，不等于通过。示例全部为生成的几何色块，色卡配置**仅用于测试，不能打印后作为实物参考**。

Windows 测试请使用 `.venv\Scripts\python -B -X utf8 -m unittest -v`，避免默认 GBK 编码读取 UTF-8 测试文件出错。`-B` 可避免生成字节码缓存。

源码仓库保留 `tests/` 测试源码和示例生成器；虚拟环境、字节码缓存、历史测试输出和本地数据库不提交。2026-10-04 清理时上述生成产物已移入回收站，原有 `MoleJournal/` 资料保留本机并通过 `.gitignore` 排除；运行前按安装步骤重建 `.venv`。

[需求](docs/REQUIREMENTS.md) · [验证计划](docs/VALIDATION.md) · [工作记录](WORK_LOG.md) · [审查清单](docs/REVIEW_CHECKLIST.md)

## 打包与回滚

源码分发是当前可靠路径；可在每个目标 OS 上自行使用 PyInstaller 从官方 PyPI 安装后打包（未实测）：
```sh
python -m pip install pyinstaller
python -m PyInstaller --windowed --name MoleJournal run_desktop.py
```
每个 OS 分别构建，不能把 Linux 构建当作 Windows/macOS 包。需要验证 Tk、中文字体、文件选择器、备份、无网络运行以及 macOS 签名/Windows 安全提示；本项目未提供签名安装包。

Git 只跟踪源码、测试与文档。通过提交记录回滚源码；应用资料不随源码回滚。在升级或回滚前，先从应用导出备份。

### 数据完整性边界
备份与恢复共享上限：解压后总计 1 GiB、10,000 个成员文件、10 MiB 清单、每表 100,000 条记录。超过上限时备份明确失败，绝不报告成功；在支持更大归档前，请退出应用后另存整个资料目录的可信离线副本，并勿删除原资料。ZIP 压缩后的较小体积不能绕过解压后限制。

切换照片或 ID 时，未标记色彩空间的 sRGB 假设会清除，组织模式默认回到「普通皮肤」，必须重新核对；从历史载入则恢复该条观察明确保存的假设，人工质控始终清除。载入新的参考配置会清除色卡框和实物对应确认。照片读取失败会保持原先图片、ID 与标记的一致状态，所有观察写入再次校验原件。
