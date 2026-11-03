"""PYNQ control only: sensor setup and diagnostics. Pixel traffic stays in PL."""
from pathlib import Path
from datetime import datetime, timezone
import json
import time

class Camera:
    def __init__(self, overlay, directory=None, pause_seconds=0.000020):
        self.overlay = overlay
        self.root = Path(directory or Path.cwd())
        self.gpio = overlay.axi_gpio_control
        self.counts = overlay.axi_gpio_counts
        self.diag = overlay.axi_gpio_diag
        self.clock = overlay.axi_gpio_clock
        self.pause_seconds = pause_seconds
        self.control = 0
        self.initialized = False
        self.sensor_id = None
        self.gpio.write(0, 0)
        if (self.status() >> 16) != 0xCA02:
            raise RuntimeError('当前不是camera_stage2硬件，请加载配套bit/hwh。')

    def status(self):
        return int(self.gpio.read(8))

    def _control(self, value):
        self.control = value
        self.gpio.write(0, value)

    def _lines(self, scl_low=None, sda_low=None):
        value = self.control
        if scl_low is not None:
            value = (value | 4) if scl_low else (value & ~4)
        if sda_low is not None:
            value = (value | 8) if sda_low else (value & ~8)
        self._control(value)
        time.sleep(self.pause_seconds)

    def _raise_scl(self):
        self._lines(scl_low=False)
        deadline = time.monotonic() + 0.05
        while not self.status() & (1 << 6):
            if time.monotonic() > deadline:
                raise RuntimeError('SCL无法释放为高：检查摄像头3脚到RPi23、供电和共地。')
            time.sleep(self.pause_seconds)

    def _start(self):
        self._lines(sda_low=False)
        self._raise_scl()
        if not self.status() & (1 << 7):
            raise RuntimeError('SDA被持续拉低：检查摄像头4脚到RPi24；可重跑第3格复位。')
        self._lines(sda_low=True)
        self._lines(scl_low=True)

    def _stop(self):
        self._lines(scl_low=True, sda_low=True)
        self._raise_scl()
        self._lines(sda_low=False)

    def _write_byte(self, value):
        for bit in range(7, -1, -1):
            self._lines(scl_low=True, sda_low=not bool(value & (1 << bit)))
            self._raise_scl()
            self._lines(scl_low=True)
        self._lines(sda_low=False)
        self._raise_scl()
        acknowledged = not bool(self.status() & (1 << 7))
        self._lines(scl_low=True)
        if not acknowledged:
            raise RuntimeError(f'SCCB无应答，发送字节0x{value:02X}。检查电源、XCK、RST及SCL/SDA接线。')

    def _read_byte(self):
        self._lines(sda_low=False)
        value = 0
        for _ in range(8):
            self._raise_scl()
            value = (value << 1) | ((self.status() >> 7) & 1)
            self._lines(scl_low=True)
        # Single-byte read ends with master NACK (SDA released).
        self._raise_scl()
        self._lines(scl_low=True)
        return value

    def write_reg(self, address, value):
        self._start()
        try:
            for byte in (0x78, address >> 8, address & 255, value):
                self._write_byte(byte)
        finally:
            self._stop()

    def read_reg(self, address):
        self._start()
        try:
            for byte in (0x78, address >> 8, address & 255):
                self._write_byte(byte)
        finally:
            self._stop()
        self._start()
        try:
            self._write_byte(0x79)
            value = self._read_byte()
        finally:
            self._stop()
        return value

    def reset_and_identify(self):
        self.initialized = False
        self._control(1)  # XCLK on; reset still asserted; capture off.
        time.sleep(0.020)
        self._control(3)  # Release open-drain reset.
        time.sleep(0.030)
        self._lines(scl_low=False, sda_low=False)
        self.sensor_id = (self.read_reg(0x300A) << 8) | self.read_reg(0x300B)
        print(f'读到芯片型号ID：0x{self.sensor_id:04X}；期望0x5640')
        if self.sensor_id != 0x5640:
            raise RuntimeError('芯片ID不匹配，暂不继续初始化。')
        return self.sensor_id

    def configure(self):
        if self.sensor_id != 0x5640:
            raise RuntimeError('请先运行第3格，读取并确认芯片ID。')
        self._control(self.control & ~32)
        self.initialized = False
        config = json.loads((self.root / 'ov5640_qvga_rgb565.json').read_text(encoding='utf-8'))
        for index, item in enumerate(config['registers']):
            address, value = int(item['address'], 16), int(item['value'], 16)
            self.write_reg(address, value)
            if item['delay_ms']:
                time.sleep(item['delay_ms'] / 1000.0)
            if index % 50 == 0:
                print(f'初始化进度：{index+1}/{len(config["registers"])}')
        time.sleep(0.300)
        width = (self.read_reg(0x3808) << 8) | self.read_reg(0x3809)
        height = (self.read_reg(0x380A) << 8) | self.read_reg(0x380B)
        fmt = self.read_reg(0x4300)
        if (width, height, fmt) != (320, 240, 0x61):
            raise RuntimeError(f'配置读回不符：{width}x{height}, format=0x{fmt:02X}')
        self.initialized = True
        print('配置读回通过：320x240，RGB565；摄像头内部测试彩条已开启。')

    def start_capture(self):
        if not self.initialized:
            raise RuntimeError('请先完成摄像头初始化。')
        self._control(self.control | 32)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.status() & 256:
                print('已收到完整帧并切换到摄像头画面；显示边框应为绿色。')
                return
            time.sleep(0.1)
        report = self.report(0.5)
        raise RuntimeError('5秒内没有完整帧。请按报告检查PCLK、HREF/VS、数据线及图像尺寸。' + str(report))

    def show_live(self):
        if not self.initialized:
            raise RuntimeError('请先完成第4格初始化。')
        self.write_reg(0x503D, 0)
        time.sleep(0.5)
        print('摄像头内部彩条已关闭：屏幕应显示镜头前的实时图像。')

    def show_sensor_bars(self):
        self.write_reg(0x503D, 0x80)

    def set_byte_swap(self, enabled):
        was_capturing = bool(self.control & 32)
        self._control(self.control & ~32)
        time.sleep(0.01)
        self._control((self.control | 16) if enabled else (self.control & ~16))
        if was_capturing:
            self.start_capture()

    def report(self, interval=1.0):
        def counters():
            return [int(self.counts.read(0)), int(self.counts.read(8)),
                    int(self.diag.read(0)), int(self.diag.read(8)), int(self.clock.read(0))]
        before = counters()
        start = time.monotonic()
        time.sleep(interval)
        after = counters()
        elapsed = time.monotonic() - start
        delta = [((b-a) & 0xFFFFFFFF) for a,b in zip(before,after)]
        status = self.status()
        result = {'utc': datetime.now(timezone.utc).isoformat(), 'design': 'camera_stage2',
            'sensor_id': None if self.sensor_id is None else f'0x{self.sensor_id:04X}',
            'control_hex': hex(self.control), 'status_hex': hex(status),
            'video_clock_locked': bool(status & 1), 'monitor_hpd': bool(status & 4),
            'camera_clock_locked': bool(status & 16), 'capture_enabled': bool(status & 32),
            'scl_high': bool(status & 64), 'sda_high': bool(status & 128),
            'display_has_camera_frame': bool(status & 256),
            'good_frames': after[0], 'displayed_frames': after[1],
            'bad_frames': after[2], 'dropped_frames': after[3],
            'good_frames_per_s': round(delta[0]/elapsed, 3),
            'display_updates_per_s': round(delta[1]/elapsed, 3),
            'pclk_mhz_measured_by_pl_counter': round(delta[4]/elapsed/1e6, 3),
            'hdmi_refresh_hz': 60, 'camera_pixels': [320,240],
            'display_observation': 'requires human observation; not inferred from registers'}
        (self.root / 'camera_report_latest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    def stop(self):
        self._control(0)
        self.initialized = False
        print('摄像头XCLK已关闭、复位有效、采集停止；显示器恢复PL测试图案。')
