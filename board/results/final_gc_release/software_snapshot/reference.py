"""Shared PC/PS reference: NumPy only; never silently substitutes for PL output."""
from pathlib import Path
import csv
import hashlib
import json
import math
import numpy as np

WIDTH = HEIGHT = 128
DEFAULT_THRESHOLD = 80

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_csv(path, records):
    if not records:
        return
    with Path(path).open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

def sobel_reference(frame, threshold):
    """Existing L1 Sobel arithmetic; output border forced to zero on both PS/PL."""
    a = np.asarray(frame, dtype=np.int32)
    gx = a[:-2, 2:] + 2*a[1:-1, 2:] + a[2:, 2:] - a[:-2, :-2] - 2*a[1:-1, :-2] - a[2:, :-2]
    gy = a[2:, :-2] + 2*a[2:, 1:-1] + a[2:, 2:] - a[:-2, :-2] - 2*a[:-2, 1:-1] - a[:-2, 2:]
    raw = np.abs(gx) + np.abs(gy)
    edge = np.zeros(a.shape, dtype=np.uint8)
    edge[1:-1, 1:-1] = (np.minimum(raw, 255) >= int(threshold)).astype(np.uint8)*255
    return edge

def roi_stats(edge, roi):
    x0, y0, x1, y1 = [int(v) for v in roi]
    mask = np.asarray(edge[y0:y1, x0:x1]) != 0
    count = int(mask.sum())
    ysum = int((mask.astype(np.uint32)*np.arange(y0, y1, dtype=np.uint32)[:, None]).sum())
    return count, ysum

def spectrum(values, fs):
    a = np.asarray(values, dtype=np.float64)
    if a.ndim != 1 or len(a) < 8 or not np.isfinite(a).all() or fs <= 0:
        raise ValueError('FFT needs >=8 finite samples and a positive sample rate')
    window = np.hanning(len(a))
    transform = np.fft.rfft((a-a.mean())*window)
    amplitude = np.abs(transform)/window.sum()
    if len(a) % 2 == 0:
        amplitude[1:-1] *= 2
    else:
        amplitude[1:] *= 2
    freq = np.fft.rfftfreq(len(a), d=1.0/fs)
    return freq, amplitude, np.abs(transform)**2

def dominant_frequency(values, fs, lower=0.2, upper=5.0):
    freq, amp, _ = spectrum(values, fs)
    eligible = np.flatnonzero((freq >= lower) & (freq <= min(upper, fs/2)))
    k = int(eligible[np.argmax(amp[eligible])])
    return float(freq[k]), freq, amp

def next_threshold(previous, previous_mad, fs):
    # Identical causal intent to day8: current sample is NOT yet in history.
    if len(previous_mad) < 64:
        return previous, None
    f, _, power = spectrum(previous_mad[-64:], fs)
    ratio = float(power[(f >= 0.2*fs) & (f > 0)].sum()/max(power[f > 0].sum(), 1e-30))
    target = float(np.clip(80*(1+0.5*ratio), 60, 120))
    return previous + float(np.clip(0.2*(target-previous), -2, 2)), ratio

def harmonic_fit(times, positions, fs):
    """Frequency is fitted from measured centroid, not imposed from a target."""
    t = np.asarray(times, dtype=float)
    y = np.asarray(positions, dtype=float)
    if not np.isfinite(y).all():
        raise ValueError('Missing ROI centroid; adjust ROI/threshold instead of inventing samples')
    peak, _, _ = dominant_frequency(y, fs)
    span = fs/len(y)
    frequencies = np.linspace(max(0.2, peak-1.5*span), min(5.0, peak+1.5*span), 1501)
    best = None
    for frequency in frequencies:
        angle = 2*np.pi*frequency*t
        design = np.column_stack((np.sin(angle), np.cos(angle), np.ones(len(t)), t-t.mean()))
        coef, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
        fitted = design.dot(coef)
        mse = float(np.mean((y-fitted)**2))
        if best is None or mse < best[0]:
            best = (mse, float(frequency), coef, fitted)
    mse, frequency, coef, fitted = best
    variance = float(np.mean((y-y.mean())**2))
    return {'fft_peak_hz': peak, 'fft_bin_spacing_hz': fs/len(y),
            'fitted_frequency_hz': frequency, 'fitted_period_s': 1/frequency,
            'fitted_amplitude_processed_pixels': float(np.hypot(coef[0], coef[1])),
            'r_squared': 1-mse/max(variance, 1e-30), 'rmse_pixels': math.sqrt(mse)}, fitted

def save_analysis(folder, rows, fs, source, board_status):
    """Shared plots work on older PYNQ NumPy/Matplotlib; no OpenCV on board."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder = Path(folder)
    write_csv(folder/'frame_metrics.csv', rows)
    valid = [r for r in rows if r['centroid_y'] is not None]
    if len(valid) != len(rows):
        raise ValueError('ROI empty in one or more frames; data saved, frequency result refused')
    times = np.array([r['time_s'] for r in rows])
    position = np.array([r['centroid_y'] for r in rows])
    fit, fitted = harmonic_fit(times, position, fs)
    fft_records = []
    fig, axes = plt.subplots(3, 2, figsize=(12, 10))
    series = [('edge_centroid_y', position, times),
              ('edge_count', np.array([r['roi_edge_count'] for r in rows]), times),
              ('gray_frame_mad', np.array([r['motion_mad'] for r in rows[1:]]), times[1:])]
    for axis, (name, data, tx) in zip(axes, series):
        f, amplitude, _ = spectrum(data, fs)
        axis[0].plot(tx, data, linewidth=1)
        if name == 'edge_centroid_y':
            axis[0].plot(times, fitted, '--', label='sinusoid + linear trend fit')
            axis[0].legend()
        axis[0].set(title=name, xlabel='Video time (s)')
        axis[1].plot(f, amplitude)
        axis[1].set(xlim=(0, min(5, fs/2)), xlabel='Frequency (Hz)', ylabel='One-sided amplitude')
        for frequency, value in zip(f, amplitude):
            fft_records.append({'series': name, 'frequency_hz': float(frequency), 'amplitude': float(value)})
    fig.tight_layout()
    fig.savefig(folder/'motion_and_spectra.png', dpi=160)
    plt.close(fig)
    write_csv(folder/'spectra.csv', fft_records)
    summary = {'status': 'PASS', 'physical_board_test': board_status,
               'processed_frames': len(rows), 'sample_rate_hz': fs,
               'motion_samples': len(rows)-1, 'position_unit': 'processed image pixels; not calibrated metres',
               'frequency_interpretation': 'centroid-y estimates displacement fundamental; MAD/count can contain harmonics',
               'source': source, 'harmonic_fit': fit,
               'pixel_mismatches': sum(r.get('pixel_mismatches', 0) for r in rows),
               'roi_stat_mismatches': sum(r.get('roi_stat_mismatches', 0) for r in rows)}
    (folder/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary
