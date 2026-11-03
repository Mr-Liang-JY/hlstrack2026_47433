"""Reusable simple-mode AXI DMA checks. Importing this module needs no PYNQ."""
from pathlib import Path
import hashlib
import json
import math
import time
import xml.etree.ElementTree as ET
import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    config['_base'] = str(path.parent)
    for key in ('bitfile', 'manifest'):
        if config.get(key):
            config[key] = str((path.parent / config[key]).resolve())
    return config


def compare_arrays(actual, expected, atol=0.0, rtol=0.0):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape:
        raise ValueError('Shape mismatch: %r != %r' % (actual.shape, expected.shape))
    if atol < 0 or rtol < 0 or not np.isfinite([atol, rtol]).all():
        raise ValueError('Tolerances must be finite and nonnegative')
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError('Non-finite values are not valid measurements')
    if atol == rtol == 0:
        matches = actual == expected
    else:
        matches = np.isclose(actual, expected, atol=atol, rtol=rtol)
    errors = np.argwhere(~matches)
    delta = np.abs(actual.astype(object)-expected.astype(object)) if actual.dtype.kind in 'ui' and expected.dtype.kind in 'ui' else np.abs(actual.astype(np.float64)-expected.astype(np.float64))
    return {'passed': not len(errors), 'elements': int(actual.size),
            'mismatches': int(len(errors)), 'first_mismatch': errors[0].tolist() if len(errors) else None,
            'max_absolute_error': float(np.max(delta)) if actual.size else 0.0,
            'atol': atol, 'rtol': rtol}


def check_overlay(config):
    bit = Path(config['bitfile'])
    hwh = bit.with_suffix('.hwh')
    for path in (bit, hwh):
        if not path.is_file():
            raise FileNotFoundError(str(path))
    tree = ET.parse(str(hwh)).getroot()
    modules = {m.get('INSTANCE'): {p.get('NAME'): p.get('VALUE') for p in m.findall('./PARAMETERS/PARAMETER')}
               for m in tree.findall('.//MODULE')}
    dma_name = config['dma_ip']
    required = [dma_name] + list(config.get('required_ips', []))
    for name in required:
        if name not in modules:
            raise ValueError('HWH missing IP: ' + name)
    dma = modules[dma_name]
    if dma.get('C_INCLUDE_SG') != '0':
        raise ValueError('Only simple-mode DMA is supported, not scatter-gather')
    if dma.get('C_INCLUDE_MM2S') != '1' or dma.get('C_INCLUDE_S2MM') != '1':
        raise ValueError('Both MM2S and S2MM are required')
    for name, parameters in config.get('expected_parameters', {}).items():
        for key, expected in parameters.items():
            if modules.get(name, {}).get(key) != str(expected):
                raise ValueError('HWH parameter mismatch: %s.%s' % (name, key))
    length_width = int(dma['C_SG_LENGTH_WIDTH'])
    maximum = (1 << length_width) - 1
    sizes = {}
    for direction in ('input', 'output'):
        shape = config[direction + '_shape']
        if not shape or any(type(v) is not int or v <= 0 for v in shape):
            raise ValueError('Shape must contain positive integers')
        dtype = np.dtype(config[direction + '_dtype'])
        if dtype.kind not in 'uif' or not dtype.isnative:
            raise ValueError('Use a native unsigned/integer/float DMA dtype')
        size = math.prod(shape) * dtype.itemsize
        if size > maximum or size <= 0:
            raise ValueError('%s transfer %d bytes exceeds DMA limit %d' % (direction, size, maximum))
        sizes[direction + '_bytes'] = size
    hashes = {'bit_sha256': digest(bit), 'hwh_sha256': digest(hwh)}
    if config.get('manifest'):
        manifest = json.loads(Path(config['manifest']).read_text(encoding='utf-8'))
        for key, value in hashes.items():
            expected=manifest.get(key)
            if expected is None:
                expected=manifest.get('hardware_sha256',{}).get(bit.name if key=='bit_sha256' else hwh.name)
            if expected != value:
                raise ValueError('Build manifest mismatch: ' + key)
    timeout = float(config.get('timeout_s', 10))
    if not np.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout_s must be positive and finite')
    return dict(passed=True, dma_ip=dma_name, dma_limit_bytes=maximum,
                **sizes, **hashes, board_test='NOT_RUN: metadata check only')


class DmaRunner:
    def __init__(self, config, overlay=None, allocator=None):
        self.config = config
        self.metadata = check_overlay(config)
        if overlay is None:
            from pynq import Overlay
            overlay = Overlay(config['bitfile'])
        if allocator is None:
            from pynq import allocate
            allocator = allocate
        self.overlay = overlay
        for name in [config['dma_ip']] + list(config.get('required_ips', [])):
            if name not in overlay.ip_dict:
                raise ValueError('Loaded Overlay missing IP: ' + name)
        self.dma = getattr(overlay, config['dma_ip'])
        self.tx = allocator(shape=tuple(config['input_shape']), dtype=np.dtype(config['input_dtype']))
        try:
            self.rx = allocator(shape=tuple(config['output_shape']), dtype=np.dtype(config['output_dtype']))
        except Exception:
            self.tx.freebuffer()
            raise
        self.released = False
        self.last_failure = None

    def transfer(self, values, start=None, ready=None):
        values = np.asarray(values)
        if values.shape != self.tx.shape or values.dtype != self.tx.dtype:
            raise ValueError('Input shape/dtype must match the declared hardware contract')
        np.copyto(self.tx, values)
        self.rx.view(np.uint8)[:] = 0xA5
        self.tx.flush()
        # The sentinel dirties the receive cache: clean it before device writes
        # so a later CPU eviction cannot overwrite DMA output in DDR.
        self.rx.flush()
        started = time.monotonic()
        try:
            if start:
                start()
            self.dma.recvchannel.transfer(self.rx)
            self.dma.sendchannel.transfer(self.tx)
            while True:
                tx, rx = self.dma.mmio.read(0x04), self.dma.mmio.read(0x34)
                if (tx | rx) & 0x70:
                    raise RuntimeError('DMA error TX=0x%08X RX=0x%08X' % (tx, rx))
                device_ready = ready is None or ready()
                if tx & 2 and rx & 2 and device_ready:
                    break
                if time.monotonic()-started > float(self.config.get('timeout_s', 10)):
                    raise TimeoutError('DMA timeout TX=0x%08X RX=0x%08X' % (tx, rx))
                time.sleep(0.0002)
            self.dma.sendchannel.wait()
            self.dma.recvchannel.wait()
            self.rx.invalidate()
            elapsed = time.monotonic()-started
            return np.array(self.rx, copy=True), {'dma_and_pl_wall_s': elapsed,
                    'tx_status': '0x%08X' % tx, 'rx_status': '0x%08X' % rx}
        except Exception as exc:
            self.last_failure={'type':type(exc).__name__,'message':str(exc),
                'tx_status':'0x%08X'%self.dma.mmio.read(0x04),'rx_status':'0x%08X'%self.dma.mmio.read(0x34)}
            self.reset_ok = self.reset()
            self.last_failure['reset_quiescent']=bool(self.reset_ok)
            raise

    def reset(self):
        self.dma.mmio.write(0x00, 4)
        deadline = time.monotonic()+1.0
        while self.dma.mmio.read(0x00) & 4:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.001)
        return self.quiescent()

    def quiescent(self):
        return bool(self.dma.mmio.read(0x04) & 3) and bool(self.dma.mmio.read(0x34) & 3)

    def close(self):
        if self.released:
            return
        if not self.quiescent() and not self.reset():
            raise RuntimeError('DMA not quiescent; buffers retained. Restart board before reuse.')
        self.tx.freebuffer()
        self.rx.freebuffer()
        self.released = True


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check')
    check.add_argument('config')
    compare = sub.add_parser('compare')
    compare.add_argument('actual')
    compare.add_argument('expected')
    compare.add_argument('--atol', type=float, default=0)
    compare.add_argument('--rtol', type=float, default=0)
    run = sub.add_parser('loopback')
    run.add_argument('config')
    run.add_argument('--output', required=True)
    a = p.parse_args()
    if a.command == 'check':
        result = check_overlay(load_config(a.config))
    elif a.command == 'compare':
        result = compare_arrays(np.load(a.actual, allow_pickle=False), np.load(a.expected, allow_pickle=False), a.atol, a.rtol)
    else:
        config = load_config(a.config)
        folder = Path(a.output)
        folder.mkdir(parents=True, exist_ok=False)
        values = np.arange(np.prod(config['input_shape']), dtype=config['input_dtype']).reshape(config['input_shape'])
        runner = DmaRunner(config)
        try:
            actual, measurement = runner.transfer(values)
            np.save(folder/'actual.npy', actual)
            np.save(folder/'expected.npy', values)
            result = dict(compare_arrays(actual, values), measurement=measurement, physical_board_test='RUN')
        except Exception as exc:
            result={'passed':False,'physical_board_test':'RUN','error':runner.last_failure or {'type':type(exc).__name__,'message':str(exc)}}
        finally:
            runner.close()
        (folder/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
