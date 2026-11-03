"""Run on the PYNQ-Z2 PS, for example from a Jupyter notebook:

%run day5_pspl.py --bitfile day5_pspl.bit

Only the PYNQ board run produces board evidence. Expected ramp values are
used for comparison; every reported received value comes from MMIO reads.
"""
from __future__ import print_function

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import socket
import sys
import time

CONTROL_OFFSET = 0x00
STATUS_OFFSET = 0x08


def decode_status(value):
    value = int(value) & 0xFFFFFFFF
    return {
        'raw_hex': '0x{:08X}'.format(value),
        'signature': (value >> 28) & 0xF,
        'frame_id': (value >> 24) & 0xF,
        'ready': (value >> 23) & 1,
        'done': (value >> 22) & 1,
        'busy': (value >> 21) & 1,
        'sample_count': (value >> 16) & 0x1F,
        'sample': value & 0xFFFF,
    }


def make_control(base, address=0, start=0):
    if not 0 <= int(base) <= 65535:
        raise ValueError('base must be an integer in 0..65535')
    if not 0 <= int(address) < 16:
        raise ValueError('read address must be in 0..15')
    if start not in (0, 1):
        raise ValueError('start must be 0 or 1')
    return (int(base) << 16) | (int(address) << 2) | 0x2 | start


class CaptureDriver(object):
    def __init__(self, mmio, poll_interval=0.002,
                 clock=time.monotonic, sleeper=time.sleep):
        self.mmio = mmio
        self.poll_interval = poll_interval
        self.clock = clock
        self.sleep = sleeper
        self.trace = []

    def status(self):
        state = decode_status(self.mmio.read(STATUS_OFFSET))
        if state['signature'] != 0xA:
            raise RuntimeError(
                'PL signature mismatch: {}. Check the loaded .bit/.hwh, '
                'AXI GPIO directions, widths, clock, and wiring.'.format(state['raw_hex']))
        return state

    def reset(self):
        self.mmio.write(CONTROL_OFFSET, 0)
        self.sleep(0.002)
        self.mmio.write(CONTROL_OFFSET, make_control(0))
        deadline = self.clock() + 1.0
        while True:
            state = self.status()
            if (state['ready'] and not state['busy'] and not state['done']
                    and state['sample_count'] == 0 and state['frame_id'] == 0):
                return state
            if self.clock() >= deadline:
                raise TimeoutError('PL reset did not finish: {}'.format(state))
            self.sleep(self.poll_interval)

    def capture(self, base, timeout=3.0):
        before = self.status()
        if not before['ready']:
            raise RuntimeError('Release/reset the PL core before capture.')
        if before['busy']:
            raise RuntimeError('PL is already busy. Wait or reset before a new capture.')
        expected_frame = (before['frame_id'] + 1) & 0xF
        # A low-to-high transition requests one frame. Hardware makes this
        # a one-clock event even if Linux leaves start high for milliseconds.
        self.mmio.write(CONTROL_OFFSET, make_control(base, start=0))
        begin = self.clock()
        self.mmio.write(CONTROL_OFFSET, make_control(base, start=1))
        deadline = begin + timeout
        while True:
            state = self.status()
            self.trace.append({
                'requested_base': int(base),
                'elapsed_wall_s': self.clock() - begin,
                'frame_id': state['frame_id'], 'ready': state['ready'],
                'busy': state['busy'], 'done': state['done'],
                'sample_count': state['sample_count'],
                'raw_hex': state['raw_hex'],
            })
            # The frame id prevents the previous frame's sticky done flag
            # from being mistaken for completion of this request.
            if (state['frame_id'] == expected_frame and state['ready']
                    and state['done'] and not state['busy']):
                if state['sample_count'] != 16:
                    raise RuntimeError('PL completed with the wrong sample count: {}'.format(state))
                break
            if self.clock() >= deadline:
                raise TimeoutError(
                    'New frame did not finish; expected frame {}. Last status: {}'.format(
                        expected_frame, state))
            self.sleep(self.poll_interval)

        capture_wait_s = self.clock() - begin
        rows = []
        for address in range(16):
            self.mmio.write(CONTROL_OFFSET, make_control(base, address, start=1))
            # One extra bus read allows the GPIO input path to settle after
            # an address change. This lab prioritizes clarity over throughput.
            self.mmio.read(STATUS_OFFSET)
            state = self.status()
            if (state['frame_id'] != expected_frame or not state['done']
                    or state['busy'] or state['sample_count'] != 16):
                raise RuntimeError('Frame changed while reading it: {}'.format(state))
            received = state['sample']
            expected = (int(base) + address) & 0xFFFF
            rows.append({
                'base': int(base), 'frame_id': expected_frame, 'address': address,
                'expected_value': expected, 'read_value': received,
                'match': int(received == expected), 'status_hex': state['raw_hex'],
            })
        return {
            'base': int(base), 'frame_id': expected_frame,
            'sample_count': state['sample_count'],
            'capture_wait_wall_s': capture_wait_s,
            'matched_samples': sum(row['match'] for row in rows),
            'passed': all(row['match'] for row in rows),
            'received_samples': [row['read_value'] for row in rows],
            'rows': rows,
        }


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='PYNQ-Z2 PS/PL 16-sample board test')
    parser.add_argument('--bitfile', default='day5_pspl.bit')
    parser.add_argument('--ip-name', default='axi_gpio_0')
    parser.add_argument('--output', default='day5_results')
    args = parser.parse_args()
    bitfile = Path(args.bitfile).expanduser().resolve()
    hwhfile = bitfile.with_suffix('.hwh')
    for path in (bitfile, hwhfile):
        if not path.is_file():
            raise FileNotFoundError('Missing overlay file: {}'.format(path))
    try:
        import pynq
        from pynq import Overlay, MMIO
    except ImportError:
        raise RuntimeError('Run this script in the PYNQ board Jupyter environment.')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output = Path(args.output).expanduser().resolve() / ('run_' + timestamp)
    output.mkdir(parents=True, exist_ok=False)
    messages = []

    def log(message):
        print(message)
        messages.append(str(message))

    summary = {
        'test': 'PYNQ-Z2 PS/PL hardware-generated ramp readback',
        'data_source': 'PL test ramp, read back through AXI GPIO MMIO',
        'utc_time': datetime.now(timezone.utc).isoformat(),
        'hostname': socket.gethostname(), 'machine': platform.machine(),
        'python_version': sys.version, 'pynq_version': getattr(pynq, '__version__', 'unknown'),
        'bitfile': str(bitfile), 'bitfile_sha256': sha256(bitfile),
        'hwhfile_sha256': sha256(hwhfile),
        'nominal_pl_clock_hz': 100000000,
        'test_sample_divider': 1000000, 'nominal_test_sample_rate_hz': 100,
        'sample_rate_note': 'Design settings, not an independent clock measurement.',
        'timing_note': 'Wait times include PS polling and software overhead.',
        'frames': [], 'passed': False,
    }
    all_rows = []
    driver = None
    error = None
    try:
        log('Loading {}'.format(bitfile.name))
        overlay = Overlay(str(bitfile))
        if args.ip_name not in overlay.ip_dict:
            raise RuntimeError('IP {} missing. Available IP: {}'.format(
                args.ip_name, sorted(overlay.ip_dict)))
        info = overlay.ip_dict[args.ip_name]
        if 'axi_gpio' not in str(info.get('type', '')):
            raise RuntimeError('Selected IP is not AXI GPIO: {}'.format(info))
        summary['ip_name'] = args.ip_name
        summary['ip_type'] = info.get('type')
        summary['mmio_base_hex'] = hex(int(info['phys_addr']))
        mmio = MMIO(int(info['phys_addr']), int(info['addr_range']))
        driver = CaptureDriver(mmio)
        log('RESET: {}'.format(driver.reset()))
        for base in (0, 100):
            frame = driver.capture(base)
            all_rows.extend(frame.pop('rows'))
            summary['frames'].append(frame)
            log('FRAME base={} id={} count={} matched={}/16'.format(
                base, frame['frame_id'], frame['sample_count'], frame['matched_samples']))
            log('RECEIVED: {}'.format(frame['received_samples']))
        summary['matched_samples'] = sum(row['match'] for row in all_rows)
        summary['checked_samples'] = len(all_rows)
        summary['passed'] = len(all_rows) == 32 and all(row['match'] for row in all_rows)
        if summary['passed']:
            log('PS-PL BOARD TEST PASSED (32/32 sample values matched)')
        else:
            error = RuntimeError('Board readback did not match all expected samples.')
    except Exception as exc:
        error = exc
    finally:
        if error is not None:
            summary['error'] = '{}: {}'.format(type(error).__name__, error)
            log('PS-PL BOARD TEST FAILED: {}'.format(summary['error']))
        write_csv(output / 'readback.csv', all_rows)
        if driver is not None:
            write_csv(output / 'status_trace.csv', driver.trace)
        (output / 'summary.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        log('RESULT DIRECTORY: {}'.format(output))
        (output / 'run_log.txt').write_text('\n'.join(messages) + '\n', encoding='utf-8')
    if error is not None:
        raise error


if __name__ == '__main__':
    main()
