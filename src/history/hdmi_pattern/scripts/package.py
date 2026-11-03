"""Standard-library-only packaging. Run on the PC after a successful Vivado build."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'
BOARD = ROOT / 'board'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def cell(kind, text):
    item = {'cell_type': kind, 'metadata': {}, 'source': text.splitlines(keepends=True)}
    if kind == 'code':
        item.update(execution_count=None, outputs=[])
    return item

def notebook(cells):
    return {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3',
            'language': 'python', 'name': 'python3'}, 'language_info': {'name': 'python',
            'version': '3.10'}}, 'nbformat': 4, 'nbformat_minor': 5}

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    BOARD.mkdir(exist_ok=True)
    for name in ('hdmi_stage1.bit', 'hdmi_stage1.hwh', 'timing_summary.rpt', 'utilization.rpt'):
        if not (OUT / name).is_file():
            raise SystemExit('Missing successful build output: ' + name)
    for name in ('tb_video_timing', 'tb_tmds_encoder', 'tb_serializer'):
        log = (OUT / (name + '.log')).read_text(encoding='utf-8', errors='replace')
        if 'PASS ' not in log or 'Fatal:' in log or 'FATAL' in log:
            raise SystemExit('Simulation has not passed: ' + name)
    source_files = []
    compiled_sources = {}
    for folder in ('rtl', 'constraints'):
        for path in (ROOT / folder).glob('*'):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            saved = OUT / 'build_sources' / relative
            if not saved.is_file() or digest(saved) != digest(path):
                raise SystemExit('Source differs from exported build; rerun build: ' + str(relative))
            compiled_sources[relative.as_posix()] = digest(saved)
    for folder in ('rtl', 'sim', 'constraints', 'scripts', 'board_files', 'docs'):
        source_files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                            and '__pycache__' not in p.parts)
    source_files.extend(ROOT / n for n in ('README.md', 'LICENSE', 'THIRD_PARTY.md', '.gitignore'))
    sources = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(source_files) if p.is_file()}
    source_id = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    manifest = {'design': 'hdmi_stage1', 'version': '1.0', 'source_id': source_id,
        'packaged_at_utc': datetime.now(timezone.utc).isoformat(), 'part': 'xc7z020clg400-1',
        'vivado': '2024.2', 'video': {'width': 640, 'height': 480, 'refresh_hz': 60,
        'pixel_clock_mhz': 25.2, 'serializer_clock_mhz': 126, 'fclk0_mhz': 100},
        'hardware_files': {n: {'sha256': digest(OUT / n), 'bytes': (OUT / n).stat().st_size}
            for n in ('hdmi_stage1.bit', 'hdmi_stage1.hwh')},
        'source_sha256': sources,
        'compiled_sources_sha256': compiled_sources,
        'validation': {'simulation': 'passed', 'implementation': 'see timing_summary.rpt and drc.rpt',
                       'physical_display': 'requires human observation; not inferred from build'}}
    write_json(OUT / 'manifest.json', manifest)
    load_nb = notebook([
        cell('markdown', '# 第一步：检查文件\n摄像头保持未连接。HDMI 线接板卡 HDMI OUT。按顺序运行三个代码格（Shift+Enter）。\n此 notebook 只加载硬件、检查状态，彩条与移动方块均由 PL 生成。'),
        cell('code', '''from pathlib import Path
import hashlib, json, time, platform
from datetime import datetime, timezone
import pynq
from pynq import Overlay, Clocks
HERE = Path.cwd()
manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
for name, info in manifest["hardware_files"].items():
    path = HERE / name
    assert path.is_file(), f"缺少文件: {path}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == info["sha256"], f"文件不配套或被改动: {name}"
print("文件检查通过；PYNQ", pynq.__version__)
print("设计:", manifest["design"], "源码ID:", manifest["source_id"][:16])
print("运行目录:", HERE)
'''),
        cell('markdown', '# 第二步：加载硬件\n本格会将 PL 切换到 HDMI 测试设计。已有 Sobel 等 Overlay 的功能会被替换。Linux 与 SD 卡启动文件保持原样。'),
        cell('code', '''ol = Overlay(str(HERE / "hdmi_stage1.bit"), download=True)
# HWH contains the 100 MHz setting. Set it explicitly as well for reproducible deployment.
Clocks.fclk0_mhz = 100.0
time.sleep(0.1)
print("硬件已加载；FCLK0 =", Clocks.fclk0_mhz, "MHz")
assert abs(Clocks.fclk0_mhz - 100.0) < 0.1, "参考时钟应为100MHz"
assert "axi_gpio_status" in ol.ip_dict, "HWH中没有状态GPIO，请检查文件配对"
'''),
        cell('markdown', '# 第三步：检查状态并观察显示器\n本格采样约2秒；LED3有快慢变化，不需要 Python 循环来驱动画面。'),
        cell('code', '''samples = []
for _ in range(12):
    samples.append(int(ol.axi_gpio_status.read(0)))
    time.sleep(0.2)
signature_ok = all((s >> 8) == 0x484431 for s in samples)
locked = all(s & 1 for s in samples)
video_running = all(s & 2 for s in samples)
monitor_detected = all(s & 4 for s in samples)
heartbeat_changes = len({(s >> 3) & 1 for s in samples}) == 2
result = dict(design="hdmi_stage1", utc=datetime.now(timezone.utc).isoformat(),
    source_id=manifest["source_id"], pynq=pynq.__version__,
    fclk0_mhz=Clocks.fclk0_mhz, raw_status=[hex(s) for s in samples],
    signature_ok=signature_ok, clock_locked=bool(locked),
    video_reset_released=bool(video_running), monitor_hpd=bool(monitor_detected),
    heartbeat_changes=heartbeat_changes,
    physical_display="请人工确认彩条、边框、移动方块和连续3分钟稳定性")
(HERE / "board_test_latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
assert signature_ok, "状态签名错误，请重新加载配套bit/hwh"
assert locked and video_running and heartbeat_changes, "显示逻辑未正常运行，请查看黑屏排查表"
if not monitor_detected:
    print("未检测到显示器HPD：检查HDMI OUT接口、线缆和显示器输入源。")
print("电路状态检查通过；屏幕实际出图需要你观察，不能仅凭状态寄存器判定。")
'''),
        cell('markdown', '## 请记录现场结果\n1. 彩条顺序：白、黄、青、绿、紫、红、蓝、黑。\n2. 四周白色细边框完整。\n3. 黑边白色方块持续移动。\n4. 连续显示3分钟，无明显闪屏、花屏。\n5. 按板上BTN0，松开后方块应回到左上附近重新运动。\n6. 重新运行第2、3格，检查再次加载。\n\n寄存器检查和画面观察是两类证据。拍摄屏幕照片并保留 `board_test_latest.json`。')
    ])
    # Assign stable IDs for nbformat 4.5 without depending on nbformat on the PC.
    for index, item in enumerate(load_nb['cells']): item['id'] = 'hdmi-%02d' % index
    write_json(BOARD / '01_hdmi_test.ipynb', load_nb)
    payload = BOARD / 'hdmi_stage1'
    payload.mkdir(exist_ok=True)
    for name in ('hdmi_stage1.bit', 'hdmi_stage1.hwh', 'manifest.json', 'build_info.txt'):
        shutil.copy2(OUT / name, payload / name)
    shutil.copy2(BOARD / '01_hdmi_test.ipynb', payload / '01_hdmi_test.ipynb')
    shutil.copy2(ROOT / 'docs' / '01_上板操作.md', payload / '操作说明.md')
    with zipfile.ZipFile(BOARD / 'hdmi_stage1_board.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(payload.iterdir()):
            archive.write(path, 'hdmi_stage1/' + path.name)
    unpack_nb = notebook([
        cell('markdown', '# 解压HDMI部署包\n将本 notebook 与 `hdmi_stage1_board.zip` 上传到 PYNQ 的同一目录。运行下面唯一的代码格。\n解压后返回文件列表，进入 `hdmi_stage1`，打开 `01_hdmi_test.ipynb`。'),
        cell('code', '''from pathlib import Path
from zipfile import ZipFile
base = Path.cwd().resolve()
with ZipFile(base / "hdmi_stage1_board.zip") as archive:
    for item in archive.infolist():
        target = (base / item.filename).resolve()
        if base not in target.parents or not item.filename.startswith("hdmi_stage1/"):
            raise ValueError("压缩包路径不符合本工程约定")
    archive.extractall(base)
print("解压完成：请返回文件列表，进入 hdmi_stage1，打开 01_hdmi_test.ipynb。")
''')])
    for index, item in enumerate(unpack_nb['cells']): item['id'] = 'unpack-%02d' % index
    write_json(BOARD / '00_解压部署包.ipynb', unpack_nb)
    with zipfile.ZipFile(ROOT / 'hdmi_stage1_source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_files):
            if path.is_file(): archive.write(path, 'stage1_hdmi_rtl/' + path.relative_to(ROOT).as_posix())
        for path in sorted(OUT.rglob('*')):
            if path.is_file(): archive.write(path, 'stage1_hdmi_rtl/out/' + path.relative_to(OUT).as_posix())
        for path in (BOARD / '01_hdmi_test.ipynb', BOARD / '00_解压部署包.ipynb'):
            archive.write(path, 'stage1_hdmi_rtl/board/' + path.name)
    print('PACKAGED:', BOARD / 'hdmi_stage1_board.zip')
    print('SOURCE ID:', source_id)

if __name__ == '__main__':
    main()
