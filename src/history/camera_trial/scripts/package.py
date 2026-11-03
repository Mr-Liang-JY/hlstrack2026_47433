"""Package only a successful, source-matched Vivado build. Standard library only."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT, BOARD = ROOT / 'out', ROOT / 'board'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def cell(kind, source):
    value = dict(cell_type=kind, metadata={}, source=source.splitlines(keepends=True))
    if kind == 'code':
        ast.parse(source)
        value.update(execution_count=None, outputs=[])
    return value


def notebook(cells):
    for index, value in enumerate(cells):
        value['id'] = 'camera-%02d' % index
    return dict(cells=cells, nbformat=4, nbformat_minor=5, metadata={
        'kernelspec': dict(display_name='Python 3', language='python', name='python3'),
        'language_info': dict(name='python', version='3.10')})


def make_notebooks():
    load = notebook([
        cell('markdown', '# OV5640 V5.0 → PYNQ-Z2 → HDMI OUT\n'
             '基础模式已经固定：摄像头320×240 RGB565，HDMI 640×480/60Hz。\n'
             '按顺序运行下面五个代码格，每格按Shift+Enter。不要直接Run All：第4格后先观察摄像头内部彩条。\n'
             'Python只设置寄存器和检查状态；每一帧图像由Verilog电路采集、缓存并输出。\n\n'
             '## 第1格：检查文件\n确认bit、hwh、驱动和配置表配套。此时尚未改变FPGA电路。'),
        cell('code', '''from pathlib import Path
import hashlib, json, time
import pynq
from pynq import Overlay, Clocks
HERE = Path.cwd()
manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
assert manifest["design"] == "camera_stage2", "请打开本阶段部署包中的notebook"
for name, info in manifest["deployment_files"].items():
    path = HERE / name
    assert path.is_file(), "缺少文件: " + str(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == info["sha256"], "文件校验错误: " + name
print("文件校验通过；PYNQ", pynq.__version__)
print("源码ID:", manifest["source_id"][:16], "运行目录:", HERE)
'''),
        cell('markdown', '## 第2格：加载新硬件，先检查HDMI\n'
             '将第一阶段的PL设计替换成摄像头显示电路。摄像头XCLK仍关闭，复位有效，采集停止。\n'
             '**预期屏幕：白边彩条和移动方块。**这说明新设计的显示基础仍正常。'),
        cell('code', '''ol = Overlay(str(HERE / "camera_stage2.bit"), download=True)
Clocks.fclk0_mhz = 100.0
time.sleep(0.2)
assert abs(Clocks.fclk0_mhz - 100.0) < 0.1, "FCLK0应为100MHz"
from camera_run import Camera
camera = Camera(ol, HERE)
status = camera.status()
print("硬件已加载；FCLK0:", Clocks.fclk0_mhz, "MHz；状态:", hex(status))
assert status & 1 and status & 2 and status & 16, "显示/摄像头时钟尚未就绪，请查看排错说明"
if not status & 4:
    print("没有检测到显示器HPD，请检查HDMI OUT、线缆和输入源。")
print("请观察白边彩条与移动方块。摄像头尚未启动。")
'''),
        cell('markdown', '## 第3格：启动摄像头控制链路，读取芯片ID\n'
             '开启24MHz XCLK，复位后通过SCCB读取型号。\n'
             '**预期：0x5640。**包装上的0x78是总线写地址；0x5640才是芯片型号。\n'
             '本格通过还不能证明D0～D7视频数据线正确。报错时先停在这里排查。'),
        cell('code', 'camera.reset_and_identify()\n'),
        cell('markdown', '## 第4格：先显示摄像头内部彩条\n'
             '设置320×240、RGB565，读回检查，再启动PL采集。初始化可能需要数秒到数十秒。\n'
             '**预期：绿边彩条，移动方块消失；good_frames和displayed_frames增加。**\n'
             '绿边彩条来自摄像头，经DVP进入缓存后显示。先观察本格，再运行第5格。'),
        cell('code', '''camera.configure()
camera.start_capture()
sensor_bars_report = camera.report(1.0)
print("先观察显示器：应为绿边彩条、没有移动方块。确认后再运行第5格。")
'''),
        cell('markdown', '## 第5格：关闭内部测试模式，显示镜头实景\n'
             '只改变摄像头测试模式寄存器，采集和显示电路继续工作。\n'
             '**预期：绿色边框内出现实时实景，移动手时图像改变。**模糊时调整手动镜头焦距。'),
        cell('code', '''camera.show_live()
live_report = camera.report(1.0)
print("请移动镜头前的物体，观察是否实时更新，并连续观察3分钟。")
print("报告已保存到 camera_report_latest.json；运行结束后PL仍持续显示。")
'''),
        cell('markdown', '## 看懂结果与重新开始\n'
             '- `good_frames`：尺寸正确且已接收完整的摄像头帧数。\n'
             '- `displayed_frames`：在显示帧边界完成换帧的次数。\n'
             '- `bad_frames`：尺寸或字节数错误的帧；持续增加时查数据/同步线和配置。\n'
             '- `dropped_frames`：缓冲未空闲时主动丢弃的整帧；不等同于坏帧。\n'
             '- HDMI固定60Hz与摄像头采集帧率不同，屏幕会重复最后一帧。\n'
             '- 寄存器状态不能代替人工观察颜色、画面完整性和运动。\n\n'
             '停止：新建代码格运行 `camera.stop()`。完整重来：从第2格依次重跑。\n'
             '恢复内部彩条：新建格运行 `camera.show_sensor_bars()`。\n'
             '只有颜色明显错误且图像轮廓正常时，参照排错说明使用 `camera.set_byte_swap(True)`。默认不交换。\n'
             '按BTN0复位后需从第3格重新初始化。详细说明见同目录“操作说明.md”。')
    ])
    assert sum(c['cell_type'] == 'code' for c in load['cells']) == 5
    write_json(BOARD / '01_摄像头启动与显示.ipynb', load)
    unpack = notebook([
        cell('markdown', '# 解压摄像头部署包\n将本notebook和`camera_stage2_board.zip`上传到板卡Jupyter的同一目录。\n'
             '运行下面唯一代码格。这一步只是解压文件，不会配置FPGA。\n'
             '完成后返回文件列表，进入`camera_stage2`，打开`01_摄像头启动与显示.ipynb`。'),
        cell('code', '''from pathlib import Path
from zipfile import ZipFile
base = Path.cwd().resolve()
with ZipFile(base / "camera_stage2_board.zip") as archive:
    for item in archive.infolist():
        target = (base / item.filename).resolve()
        if base not in target.parents or not item.filename.startswith("camera_stage2/"):
            raise ValueError("部署包路径不符合本工程约定")
    archive.extractall(base)
print("解压完成：返回文件列表，进入camera_stage2，打开01_摄像头启动与显示.ipynb。")
''')])
    write_json(BOARD / '00_解压摄像头部署包.ipynb', unpack)


def main():
    BOARD.mkdir(exist_ok=True)
    for name in ('camera_stage2.bit', 'camera_stage2.hwh', 'timing_summary.rpt', 'utilization.rpt', 'drc.rpt'):
        if not (OUT / name).is_file():
            raise SystemExit('Missing successful build output: ' + name)
    for name in ('tb_video_timing', 'tb_tmds_encoder', 'tb_serializer', 'tb_dvp_framebuffer', 'tb_cdc_counter', 'test_sccb_protocol'):
        log = (OUT / (name + '.log')).read_text(encoding='utf-8', errors='replace')
        if 'PASS ' not in log or 'Fatal:' in log or 'FATAL' in log or 'Traceback' in log:
            raise SystemExit('Validation has not passed: ' + name)
    compiled = {}
    for folder in ('rtl', 'constraints'):
        for path in (ROOT / folder).glob('*'):
            if not path.is_file():
                continue
            saved = OUT / 'build_sources' / path.relative_to(ROOT)
            if not saved.is_file() or digest(path) != digest(saved):
                raise SystemExit('Source differs from compiled snapshot: ' + str(path))
            compiled[path.relative_to(ROOT).as_posix()] = digest(saved)
    make_notebooks()
    source_files = []
    for folder in ('rtl', 'sim', 'constraints', 'scripts', 'board_files', 'docs', 'python', 'config'):
        source_files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    source_files.extend(ROOT / name for name in ('README.md', 'LICENSE', 'THIRD_PARTY.md', '.gitignore'))
    sources = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(source_files)}
    source_id = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    payload = BOARD / 'camera_stage2'
    payload.mkdir(exist_ok=True)
    for name in ('camera_stage2.bit', 'camera_stage2.hwh', 'build_info.txt'):
        shutil.copy2(OUT / name, payload / name)
    shutil.copy2(ROOT / 'python' / 'camera_run.py', payload / 'camera_run.py')
    shutil.copy2(ROOT / 'config' / 'ov5640_qvga_rgb565.json', payload / 'ov5640_qvga_rgb565.json')
    shutil.copy2(BOARD / '01_摄像头启动与显示.ipynb', payload / '01_摄像头启动与显示.ipynb')
    shutil.copy2(ROOT / 'docs' / '01_操作与目的.md', payload / '操作说明.md')
    manifest = dict(design='camera_stage2', version='1.0', source_id=source_id,
        packaged_at_utc=datetime.now(timezone.utc).isoformat(), vivado='2024.2', part='xc7z020clg400-1',
        video=dict(width=640, height=480, refresh_hz=60, pixel_clock_mhz=25.2, serializer_clock_mhz=126, fclk0_mhz=100),
        camera=dict(module='OV5640 V5.0 DVP', width=320, height=240, format='RGB565', xclk_mhz=24,
                    sensor_fps='measure on board; not asserted to be 30'),
        deployment_files={p.name: dict(sha256=digest(p), bytes=p.stat().st_size) for p in sorted(payload.iterdir())
                          if p.is_file() and p.name != 'manifest.json'},
        source_sha256=sources, compiled_sources_sha256=compiled,
        validation=dict(rtl_simulations=5, sccb_protocol_test='passed (software wire-level model)',
            implementation='see timing_summary.rpt and drc.rpt',
            physical_camera='not yet observed; requires connected board and human observation'))
    write_json(OUT / 'manifest.json', manifest)
    shutil.copy2(OUT / 'manifest.json', payload / 'manifest.json')
    with zipfile.ZipFile(BOARD / 'camera_stage2_board.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(payload.iterdir()):
            if path.is_file():
                archive.write(path, 'camera_stage2/' + path.name)
    with zipfile.ZipFile(ROOT / 'camera_stage2_source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_files):
            archive.write(path, 'stage2_ov5640_hdmi/' + path.relative_to(ROOT).as_posix())
        for path in sorted((OUT / 'build_sources').rglob('*')):
            if path.is_file():
                archive.write(path, 'stage2_ov5640_hdmi/out/' + path.relative_to(OUT).as_posix())
        for path in sorted(OUT.iterdir()):
            if path.is_file() and path.name != 'delivery_check.json' and path.suffix in ('.bit', '.hwh', '.rpt', '.json', '.txt', '.log'):
                archive.write(path, 'stage2_ov5640_hdmi/out/' + path.name)
        for name in ('00_解压摄像头部署包.ipynb', '01_摄像头启动与显示.ipynb'):
            archive.write(BOARD / name, 'stage2_ov5640_hdmi/board/' + name)
    print('PACKAGED:', BOARD / 'camera_stage2_board.zip')
    print('SOURCE ID:', source_id)


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
