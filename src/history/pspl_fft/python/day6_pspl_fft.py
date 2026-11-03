"""Board PS program: control PL, read 1000 REAL MMIO values, then run FFT.

Run in the PYNQ board Jupyter:
    %run day6_pspl_fft.py --bitfile day6_pspl_fft.bit
No host/demo-data fallback is provided. Reference values only check readback.
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

import numpy as np

N_SAMPLES = 1000
NOMINAL_FS_HZ = 100.0
COUNTS_PER_AU = 10000.0
CONTROL_OFFSET = 0x00
STATUS_OFFSET = 0x08
DATA_OFFSET = 0x00
# Filled from the same documented integer LUT used by the PL. Comparison only.
LUT_COUNTS = (0, 628, 1253, 1874, 2487, 3090, 3681, 4258, 4818, 5358, 5878, 6374, 6845, 7290, 7705, 8090, 8443, 8763, 9048, 9298, 9511, 9686, 9823, 9921, 9980, 10000, 9980, 9921, 9823, 9686, 9511, 9298, 9048, 8763, 8443, 8090, 7705, 7290, 6845, 6374, 5878, 5358, 4818, 4258, 3681, 3090, 2487, 1874, 1253, 628, 0, -628, -1253, -1874, -2487, -3090, -3681, -4258, -4818, -5358, -5878, -6374, -6845, -7290, -7705, -8090, -8443, -8763, -9048, -9298, -9511, -9686, -9823, -9921, -9980, -10000, -9980, -9921, -9823, -9686, -9511, -9298, -9048, -8763, -8443, -8090, -7705, -7290, -6845, -6374, -5878, -5358, -4818, -4258, -3681, -3090, -2487, -1874, -1253, -628)


def signed16(value):
    value = int(value) & 0xFFFF
    return value - 65536 if value >= 32768 else value


def decode_status(value):
    value = int(value) & 0xFFFFFFFF
    return {
        'raw_hex': '0x{:08X}'.format(value),
        'signature': (value >> 28) & 15,
        'frame_id': (value >> 24) & 15,
        'ready': (value >> 23) & 1,
        'done': (value >> 22) & 1,
        'busy': (value >> 21) & 1,
        'frequency_hz': 5 if (value >> 20) & 1 else 2,
        'half_amplitude': (value >> 19) & 1,
        'sample_count': value & 1023,
    }


def decode_sample(value):
    value = int(value) & 0xFFFFFFFF
    return {'signature': (value >> 28) & 15,
            'frame_id': (value >> 24) & 15,
            'valid': (value >> 23) & 1,
            'raw_u16': value & 0xFFFF,
            'counts': signed16(value),
            'raw_hex': '0x{:08X}'.format(value)}


def make_control(frequency_hz=2, half_amplitude=0, address=0, start=0):
    if frequency_hz not in (2, 5):
        raise ValueError('This PL source supports frequency_hz=2 or 5.')
    if half_amplitude not in (0, 1) or start not in (0, 1):
        raise ValueError('half_amplitude and start must be 0 or 1.')
    if not 0 <= int(address) < N_SAMPLES:
        raise ValueError('Read address must be in 0..999.')
    return ((int(half_amplitude) << 13) | (int(frequency_hz == 5) << 12)
            | (int(address) << 2) | 2 | int(start))


def reference_counts(frequency_hz, half_amplitude, n=N_SAMPLES):
    # This array is NEVER used as the FFT input. Signed division truncates
    # toward zero, matching the Verilog / 2 expression.
    values = [LUT_COUNTS[(i * int(frequency_hz)) % 100] for i in range(n)]
    if half_amplitude:
        values = [int(value / 2) for value in values]
    return values


def analyze_counts(received_counts, fs_hz=NOMINAL_FS_HZ):
    counts = np.asarray(received_counts, dtype=np.float64)
    if counts.ndim != 1 or counts.size != N_SAMPLES:
        raise ValueError('Expected exactly 1000 received samples.')
    if not np.all(np.isfinite(counts)) or fs_hz <= 0:
        raise ValueError('Invalid input values or sample rate.')
    signal = counts / COUNTS_PER_AU
    centered = signal - np.mean(signal)
    n = len(centered)
    transformed = np.fft.rfft(centered)
    frequency = np.fft.rfftfreq(n, d=1.0 / fs_hz)
    amplitude = np.abs(transformed) / n
    # N=1000 is even: double only the interior positive-frequency bins.
    amplitude[1:-1] *= 2.0
    eligible = np.flatnonzero((frequency >= 0.1) & (frequency <= 10.0))
    peak_bin = int(eligible[np.argmax(amplitude[eligible])])
    metrics = {
        'sample_count': int(n), 'nominal_fs_hz': float(fs_hz),
        'fft_bin_spacing_hz': float(fs_hz / n),
        'dominant_bin': peak_bin,
        'dominant_frequency_hz': float(frequency[peak_bin]),
        'peak_amplitude_au': float(amplitude[peak_bin]),
        'raw_fft_magnitude_at_peak': float(abs(transformed[peak_bin])),
        'mean_au': float(np.mean(signal)),
        'rms_au': float(np.sqrt(np.mean(signal ** 2))),
        'ac_rms_au': float(np.sqrt(np.mean(centered ** 2))),
        'peak_to_peak_au': float(np.max(signal) - np.min(signal)),
    }
    return metrics, signal, frequency, amplitude


class CaptureDriver(object):
    def __init__(self, control_mmio, data_mmio, poll_interval=0.02,
                 clock=time.monotonic, sleeper=time.sleep):
        self.control = control_mmio
        self.data = data_mmio
        self.poll_interval = poll_interval
        self.clock = clock
        self.sleep = sleeper
        self.trace = []

    def status(self):
        state = decode_status(self.control.read(STATUS_OFFSET))
        if state['signature'] != 0xB:
            raise RuntimeError('Day 6 status signature mismatch: {}. Check '
                               'the .bit/.hwh pair and GPIO wiring.'.format(state['raw_hex']))
        return state

    def reset(self):
        self.control.write(CONTROL_OFFSET, 0)
        self.sleep(0.002)
        self.control.write(CONTROL_OFFSET, make_control())
        deadline = self.clock() + 1.0
        while True:
            state = self.status()
            if (state['ready'] and not state['busy'] and not state['done']
                    and state['sample_count'] == 0 and state['frame_id'] == 0):
                return state
            if self.clock() >= deadline:
                raise TimeoutError('PL reset timeout: {}'.format(state))
            self.sleep(self.poll_interval)

    def capture(self, frequency_hz, half_amplitude=0, timeout=30.0):
        before = self.status()
        if not before['ready'] or before['busy']:
            raise RuntimeError('PL must be ready and idle before capture: {}'.format(before))
        expected_id = (before['frame_id'] + 1) & 15
        self.control.write(CONTROL_OFFSET, make_control(frequency_hz, half_amplitude, start=0))
        begin = self.clock()
        self.control.write(CONTROL_OFFSET, make_control(frequency_hz, half_amplitude, start=1))
        while True:
            state = self.status()
            self.trace.append({
                'requested_frequency_hz': frequency_hz,
                'requested_half_amplitude': half_amplitude,
                'elapsed_wall_s': self.clock() - begin,
                'frame_id': state['frame_id'], 'busy': state['busy'],
                'done': state['done'], 'sample_count': state['sample_count'],
                'raw_hex': state['raw_hex'],
            })
            if (state['frame_id'] == expected_id and state['ready']
                    and state['done'] and not state['busy']):
                if (state['sample_count'] != N_SAMPLES
                        or state['frequency_hz'] != frequency_hz
                        or state['half_amplitude'] != half_amplitude):
                    raise RuntimeError('PL finished with unexpected configuration/count: {}'.format(state))
                break
            if self.clock() - begin >= timeout:
                raise TimeoutError('Frame {} did not finish. Last state: {}'.format(expected_id, state))
            self.sleep(self.poll_interval)
        wait_s = self.clock() - begin
        expected_values = reference_counts(frequency_hz, half_amplitude)
        rows = []
        read_begin = self.clock()
        for address in range(N_SAMPLES):
            self.control.write(CONTROL_OFFSET, make_control(
                frequency_hz, half_amplitude, address=address, start=1))
            # Synchronous RAM + GPIO input path: discard two bus reads after
            # changing the address, then keep the third value.
            self.data.read(DATA_OFFSET)
            self.data.read(DATA_OFFSET)
            sample = decode_sample(self.data.read(DATA_OFFSET))
            if (sample['signature'] != 0xC or sample['frame_id'] != expected_id
                    or not sample['valid']):
                raise RuntimeError('Invalid sample tag at address {}: {}'.format(address, sample))
            expected = expected_values[address]
            rows.append({
                'frame_id': expected_id, 'index': address,
                'nominal_time_s': address / NOMINAL_FS_HZ,
                'received_u16': sample['raw_u16'],
                'received_counts': sample['counts'],
                'received_au': sample['counts'] / COUNTS_PER_AU,
                'reference_counts': expected,
                'match': int(sample['counts'] == expected),
                'data_word_hex': sample['raw_hex'],
            })
        after = self.status()
        if (after['frame_id'] != expected_id or not after['done'] or after['busy']
                or after['sample_count'] != N_SAMPLES):
            raise RuntimeError('Frame changed during readback: {}'.format(after))
        return {
            'frame_id': expected_id, 'requested_frequency_hz': frequency_hz,
            'half_amplitude': half_amplitude,
            'capture_wait_wall_s': wait_s,
            'readback_wall_s': self.clock() - read_begin,
            'matched_samples': sum(row['match'] for row in rows),
            'rows': rows,
            'received_counts': [row['received_counts'] for row in rows],
        }


def write_csv(path, rows):
    if rows:
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def save_plot(path, signal, frequency, amplitude, metrics, label, show=True):
    import matplotlib.pyplot as plt
    time_axis = np.arange(len(signal)) / NOMINAL_FS_HZ
    figure, axes = plt.subplots(2, 1, figsize=(9, 6))
    axes[0].plot(time_axis, signal, linewidth=1.0)
    axes[0].set_xlim(0, 2)
    axes[0].set_xlabel('Nominal time (s); first 2 s shown')
    axes[0].set_ylabel('Amplitude (a.u.)')
    axes[0].set_title(label + ' | PL source -> PS readback')
    axes[1].plot(frequency, amplitude, linewidth=1.1)
    axes[1].plot(metrics['dominant_frequency_hz'], metrics['peak_amplitude_au'], 'ro')
    axes[1].set_xlim(0, 10)
    axes[1].set_xlabel('Nominal frequency (Hz)')
    axes[1].set_ylabel('Single-sided amplitude (a.u.)')
    axes[1].set_title('Peak: {:.3f} Hz, {:.6f} a.u.'.format(
        metrics['dominant_frequency_hz'], metrics['peak_amplitude_au']))
    for axis in axes:
        axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(str(path), dpi=160)
    if show:
        plt.show()
    plt.close(figure)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='PYNQ-Z2 Day 6 PL source / PS FFT board test')
    parser.add_argument('--bitfile', default='day6_pspl_fft.bit')
    parser.add_argument('--output', default='day6_results')
    parser.add_argument('--no-show', action='store_true')
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
        raise RuntimeError('Run this program in the PYNQ board Jupyter environment.')

    output = Path(args.output).expanduser().resolve() / (
        'run_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(parents=True, exist_ok=False)
    messages = []

    def log(message):
        print(message)
        messages.append(str(message))

    summary = {
        'test': 'PL sine generation/cache, PS readback and FFT',
        'data_source': 'Internal PL LUT test signal, actual AXI GPIO MMIO readback',
        'utc_time': datetime.now(timezone.utc).isoformat(),
        'machine': platform.machine(), 'hostname': socket.gethostname(),
        'python_version': sys.version,
        'pynq_version': getattr(pynq, '__version__', 'unknown'),
        'numpy_version': np.__version__,
        'bitfile_sha256': sha256(bitfile), 'hwhfile_sha256': sha256(hwhfile),
        'nominal_pl_clock_hz': 100000000, 'sample_divider': 1000000,
        'nominal_fs_hz': NOMINAL_FS_HZ, 'counts_per_au': COUNTS_PER_AU,
        'frequency_note': 'Design clock/divider values; no independent clock calibration.',
        'timing_note': 'PS wall times include polling/readback/software overhead.',
        'frames': [], 'passed': False,
    }
    driver = None
    error = None
    result_rows = []
    try:
        log('Loading {}'.format(bitfile.name))
        overlay = Overlay(str(bitfile))
        mmios = {}
        for name in ('axi_gpio_ctrl', 'axi_gpio_data'):
            if name not in overlay.ip_dict:
                raise RuntimeError('Missing IP {}. Available: {}'.format(name, sorted(overlay.ip_dict)))
            info = overlay.ip_dict[name]
            if 'axi_gpio' not in str(info.get('type', '')):
                raise RuntimeError('IP {} must be AXI GPIO.'.format(name))
            mmios[name] = MMIO(int(info['phys_addr']), int(info['addr_range']))
            summary[name + '_base_hex'] = hex(int(info['phys_addr']))
        driver = CaptureDriver(mmios['axi_gpio_ctrl'], mmios['axi_gpio_data'])
        log('RESET: {}'.format(driver.reset()))
        # Two configurations in ONE bitstream; the PS requests each frame.
        for frequency_hz, half in ((2, 0), (5, 1)):
            label = 'f{}_a{}'.format(frequency_hz, '0p5' if half else '1')
            log('CAPTURING {}: nominal frame duration 10 s; please wait.'.format(label))
            frame = driver.capture(frequency_hz, half)
            rows = frame.pop('rows')
            # Save the actual raw readback BEFORE FFT/plotting.
            write_csv(output / (label + '_samples.csv'), rows)
            metrics, signal, frequency, amplitude = analyze_counts(frame.pop('received_counts'))
            target_amplitude = 0.5 if half else 1.0
            metrics.update({
                'case': label, 'frame_id': frame['frame_id'],
                'target_frequency_hz': frequency_hz,
                'target_amplitude_au': target_amplitude,
                'absolute_frequency_error_hz': abs(metrics['dominant_frequency_hz'] - frequency_hz),
                'amplitude_relative_error_percent': abs(
                    metrics['peak_amplitude_au'] - target_amplitude) / target_amplitude * 100.0,
                'matched_samples': frame['matched_samples'],
            })
            metrics['passed'] = bool(frame['matched_samples'] == N_SAMPLES
                                     and metrics['absolute_frequency_error_hz'] <= 0.05
                                     and metrics['amplitude_relative_error_percent'] <= 0.1)
            frame['metrics'] = metrics
            summary['frames'].append(frame)
            result_rows.append(metrics)
            write_csv(output / (label + '_spectrum.csv'), [
                {'frequency_hz_nominal': float(f), 'single_sided_amplitude_au': float(a)}
                for f, a in zip(frequency, amplitude)])
            save_plot(output / (label + '_time_spectrum.png'), signal,
                      frequency, amplitude, metrics, label, show=not args.no_show)
            log('{}: count={} matched={}/1000 peak={:.3f} Hz, A={:.6f} a.u., '
                'amplitude error={:.6f}%'.format(
                    label, metrics['sample_count'], metrics['matched_samples'],
                    metrics['dominant_frequency_hz'], metrics['peak_amplitude_au'],
                    metrics['amplitude_relative_error_percent']))
        summary['passed'] = len(result_rows) == 2 and all(row['passed'] for row in result_rows)
        if summary['passed']:
            log('DAY 6 BOARD TEST PASSED (2000/2000 sample values matched)')
        else:
            error = RuntimeError('Readback or spectrum validation failed; retain all result files.')
    except Exception as exc:
        error = exc
    finally:
        if error is not None:
            summary['error'] = '{}: {}'.format(type(error).__name__, error)
            log('DAY 6 BOARD TEST FAILED: {}'.format(summary['error']))
        write_csv(output / 'analysis_results.csv', result_rows)
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
