# 痣迹：中文快速开始

这是离线桌面应用的源码包，不是双击即装的安装包。先解压，再进入里面的 `mole-tracker` 文件夹。需要已安装 Python 3.11+ 和 Tk（推荐 8.6）。

历史 Linux 原生界面与 39 项测试通过，独立软件审查通过。2026-10-04 在 Windows 启用 UTF-8 后复测 39 项全部通过；macOS 尚未实机验证，Windows/macOS 安装包仍未验证。实验数值不用于诊断或健康保证；新出现、变化、瘙痒或出血不要等到下个月，请及时咨询皮肤科。

## 1. 安装依赖并打开

打开终端，先切换到解压后的项目目录。第一次安装依赖需要网络；安装完成后应用本身完全离线。

**macOS / Linux**
```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m moletracker --data "$HOME/MoleJournal"
```
macOS 建议使用带 Tk 的官方 Python。Linux 若提示缺少 tkinter，按你的发行版安装 Python Tk 组件；中文显示需要中文字体。

**Windows PowerShell**
```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m moletracker --data C:\MoleJournal
```
Windows 的 Python 安装应包含 Tcl/Tk。

资料目录应在项目源码目录之外，也不要放在 iCloud、OneDrive 等同步目录。应用不上传照片，但无法控制操作系统的同步软件。资料和备份都没有应用级加密。

## 2. 先练习，不用真实照片

macOS / Linux 在同一项目目录执行：
```sh
.venv/bin/python -m examples.generate_demo "$HOME/MoleDemo"
.venv/bin/python -m moletracker --data "$HOME/MoleDemo/journal"
```
`MoleDemo` 必须是尚不存在的新目录。Windows 可以用 `.venv\Scripts\python` 执行相同模块，并选择本地新目录。

示例是两个月的生成色块。选择稳定 ID，「历史与对比」默认选中最近两个有观察的月份，也可按 Ctrl（macOS Command）重新多选两条。「联动缩放 / 原图对比」可检查局部、原图与拍摄备注。演示色卡配置只能用于这些合成图片，不能打印后用于真实皮肤。

## 3. 记录真实照片

1. 后置相机 + 三脚架/定时器或家人协助，固定柔和灯光；用 USB 把 JPEG/PNG 原件传到本机
2. 新建月份，为每个已有痣建立稳定 ID，写清左/右和解剖位置。首次记录不等于新长出
3. 导入概览定位与近照，用「缩略图选片」寻找照片。在「定位概览 / 纳入与归档」关联定位图并核对纳入月份。逐点标记痣内部、邻近正常皮肤；完成多边形，排除毛发、反光和边缘。可拖动白点纠错，Delete 删点、Ctrl+Z/Y 撤销/重做、Enter 完成。浏览模式拖动平移，＋/−缩放，「适合」显示全图；旋转仅改变显示
4. 没有可靠色卡配置时，可保存未校准照片。需要数值时，先用「设置实体色卡」导入对应实物/版本的厂商参考文件；见 [实体色卡设置](docs/REFERENCE_SETUP.md)，无需手写 JSON
5. 认真检查四项质控，不合格就重拍或明确记录原因。非普通皮肤/指甲等关闭「普通皮肤」，不套用正常皮肤 D
6. 查看历史与区域覆盖。未拍摄不等于没有痣。拍摄、导入、复核 20–30 处在一小时内完成仍需真实试用验证

完整路线包含头皮、背部、褶皱、手脚和指甲；不要求私密或侵入式拍摄。详见 [拍摄协议](docs/CAPTURE_PROTOCOL.md)。

## 4. 定期备份

「备份到本地」导出原件、标记、参考、历史和恢复草稿；「恢复副本」只恢复到新目录。备份含敏感照片/EXIF，未加密，请安全存放。总量上限为解压后 16 GiB，另有文件数和清单大小限制，处理方法见 README。开始备份时会显示原件容量并检查目标空间。

选齐月份、ID 和照片后的编辑会自动保留恢复草稿。下次用「恢复编辑草稿」继续，重新确认四项质控后再存为正式观察。列表里的「下一处未记录 / 待重拍」按本月追踪范围与最新状态导航。任务中可请求停止，已完成部分保留；关闭会先停止并保存草稿。恢复成功后可打开副本。同一资料目录只能由一个交互进程打开。

新资料 schema 和新备份格式为 2，旧程序无法读取；新程序仍可恢复旧备份。升级前留存旧备份，具体兼容范围、54 项 Windows 测试及合成性能限制见 README。小屏可通过编辑面板的横、纵滚动条访问全部控件。

源码包不含你的照片、数据库或 Git 历史。升级源码不会自动移动资料；升级前先备份。更多限制、操作与测试命令见 [README](README.md)。
