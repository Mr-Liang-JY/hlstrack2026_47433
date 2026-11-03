# -*- coding: utf-8 -*-
r"""第三天实验：幅度变化验证和双频信号分析。

运行幅度实验：.venv\Scripts\python.exe day3_experiments.py --case amplitude
运行双频实验：.venv\Scripts\python.exe day3_experiments.py --case dual
全部运行且不打开图窗：python day3_experiments.py --no-show
只依赖已安装的NumPy和Matplotlib，不需要修改前两天的脚本。
所有输入均为Python生成的模拟信号，图中的a.u.不是实测电压。
"""

import argparse
import csv
import json
import platform
from pathlib import Path

import numpy as np
import matplotlib
import matplotlib.pyplot as plt


# 两组基础实验均使用100 Hz采样率、1000点，即10秒、0.1 Hz频率间隔。
SAMPLE_RATE_HZ = 100.0
SAMPLE_COUNT = 1000
SINGLE_FREQUENCY_HZ = 2.0
AMPLITUDE_LEVELS = (0.5, 1.0, 1.5)
DUAL_COMPONENTS = ((2.0, 1.0), (5.0, 0.4))  # 每一对为频率Hz、峰值幅度a.u.

# 谱峰检测使用分析频段、相对阈值和峰间距，不读取输入的参考频率。
SEARCH_MIN_HZ = 0.1
SEARCH_MAX_HZ = 10.0
MIN_RELATIVE_PEAK_HEIGHT = 0.05
MIN_PEAK_SEPARATION_HZ = 0.3
ROOT = Path(__file__).resolve().parent
COLORS = ('#1763A6', '#C36C23', '#32824A')


def spectrum(samples, fs_hz):
    n = len(samples)
    centered = samples - np.mean(samples)
    values = np.fft.rfft(centered)
    frequency = np.fft.rfftfreq(n, d=1.0 / fs_hz)
    amplitude = np.abs(values) / n
    if n % 2 == 0:
        amplitude[1:-1] *= 2.0
    else:
        amplitude[1:] *= 2.0
    return frequency, amplitude


def find_spectral_peaks(frequency, amplitude, max_peaks):
    """检测局部最大值，按幅度排序，并抑制距离过近的候选峰。"""
    local = np.flatnonzero(
        (amplitude[1:-1] > amplitude[:-2]) &
        (amplitude[1:-1] >= amplitude[2:])) + 1
    band = ((frequency >= SEARCH_MIN_HZ) &
            (frequency <= SEARCH_MAX_HZ) & (frequency > 0))
    eligible = np.flatnonzero(band)
    if not len(eligible):
        raise ValueError('分析频段内没有频点。')
    threshold = float(np.max(amplitude[eligible])) * MIN_RELATIVE_PEAK_HEIGHT
    local = local[band[local] & (amplitude[local] >= threshold)]
    ranked = sorted(local, key=lambda k: float(amplitude[k]), reverse=True)
    chosen = []
    for k in ranked:
        if all(abs(float(frequency[k] - frequency[j])) >= MIN_PEAK_SEPARATION_HZ
               for j in chosen):
            chosen.append(int(k))
        if len(chosen) == max_peaks:
            break
    if len(chosen) < max_peaks:
        raise ValueError('只检测到{}个合格谱峰，本实验需要{}个。'.format(len(chosen), max_peaks))
    return chosen


def save_csv(path, headers, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


def save_case(folder, name, time_s, samples, frequency, amplitude, components):
    save_csv(folder / (name + '_samples.csv'),
             ['sample_index', 'time_s', 'amplitude_au'],
             ([i, '{:.8f}'.format(float(t)), '{:.12g}'.format(float(x))]
              for i, (t, x) in enumerate(zip(time_s, samples))))
    save_csv(folder / (name + '_spectrum.csv'),
             ['frequency_hz', 'single_sided_amplitude_au'],
             ([float(f), float(a)] for f, a in zip(frequency, amplitude)))
    parameters = {
        'data_source': 'Python-generated simulated sine signal; not hardware acquisition',
        'sample_rate_hz': SAMPLE_RATE_HZ,
        'sample_count': SAMPLE_COUNT,
        'record_duration_s': SAMPLE_COUNT / SAMPLE_RATE_HZ,
        'frequency_bin_spacing_hz': SAMPLE_RATE_HZ / SAMPLE_COUNT,
        'window': 'rectangular', 'zero_padding': False, 'mean_removed': True,
        'reference_components': [
            {'frequency_hz': float(f), 'peak_amplitude_au': float(a)} for f, a in components],
    }
    (folder / (name + '_parameters.json')).write_text(
        json.dumps(parameters, ensure_ascii=False, indent=2), encoding='utf-8')


def result_row(case_name, ref_f, ref_a, frequency, amplitude, k):
    estimated_f = float(frequency[k])
    estimated_a = float(amplitude[k])
    return {
        'case': case_name,
        'reference_frequency_hz': float(ref_f),
        'reference_amplitude_au': float(ref_a),
        'estimated_frequency_hz': estimated_f,
        'estimated_amplitude_au': estimated_a,
        'frequency_absolute_error_hz': abs(estimated_f - ref_f),
        'amplitude_relative_error_pct': abs(estimated_a - ref_a) / ref_a * 100,
    }


def save_results(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def style_axis(ax, xlabel, ylabel):
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, color='#D9DDE2', linewidth=.6)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


def run_amplitude(out):
    folder = out / 'amplitude'
    folder.mkdir(parents=True, exist_ok=True)
    time_s = np.arange(SAMPLE_COUNT) / SAMPLE_RATE_HZ
    zoom = time_s < 1.0
    results = []
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 6.2))
    for index, level in enumerate(AMPLITUDE_LEVELS):
        color = COLORS[index % len(COLORS)]
        samples = level * np.sin(2 * np.pi * SINGLE_FREQUENCY_HZ * time_s)
        frequency, amplitude = spectrum(samples, SAMPLE_RATE_HZ)
        peak = find_spectral_peaks(frequency, amplitude, 1)[0]
        results.append(result_row('single_A{:g}'.format(level),
                                  SINGLE_FREQUENCY_HZ, level, frequency, amplitude, peak))
        name = 'A{:g}'.format(level)
        save_case(folder, name, time_s, samples, frequency, amplitude,
                  [(SINGLE_FREQUENCY_HZ, level)])
        label = 'Input A = {:g}'.format(level)
        axes[0].plot(time_s[zoom], samples[zoom], color=color, linewidth=1.1, label=label)
        axes[1].plot(frequency, amplitude, color=color, linewidth=1.1, label=label)
        axes[1].plot(frequency[peak], amplitude[peak], 'o', color=color, markersize=5)
    axes[0].set_title('Amplitude experiment: first second')
    axes[0].set_xlim(0, 1)
    axes[1].set_title('Single-sided amplitude spectra: rectangular window')
    axes[1].set_xlim(0, SEARCH_MAX_HZ)
    axes[1].set_ylim(0, max(AMPLITUDE_LEVELS) * 1.25)
    style_axis(axes[0], 'Time (s)', 'Amplitude (a.u.)')
    style_axis(axes[1], 'Frequency (Hz)', 'Amplitude (a.u.)')
    for ax in axes:
        ax.legend(frameon=False, loc='upper right')
    fig.tight_layout()
    fig.savefig(str(folder / 'amplitude_waveforms_and_spectra.png'), dpi=300, facecolor='white')

    reference = np.array([r['reference_amplitude_au'] for r in results])
    estimated = np.array([r['estimated_amplitude_au'] for r in results])
    fig2, ax = plt.subplots(figsize=(6.6, 4.7))
    limit = float(np.max(reference)) * 1.15
    ax.plot([0, limit], [0, limit], '--', color='#777777', linewidth=1, label='Ideal: output = input')
    ax.scatter(reference, estimated, color=COLORS[0], s=45, zorder=3, label='FFT estimates')
    ax.set_xlim(0, limit)
    ax.set_ylim(0, limit)
    ax.set_title('Known amplitude versus FFT estimate')
    style_axis(ax, 'Reference peak amplitude (a.u.)', 'Estimated peak amplitude (a.u.)')
    ax.legend(frameon=False)
    fig2.tight_layout()
    fig2.savefig(str(folder / 'amplitude_calibration.png'), dpi=300, facecolor='white')
    save_results(folder / 'amplitude_results.csv', results)
    print('\n幅度变化实验完成：')
    for r in results:
        print('输入幅度{:.1f} -> 主频{:.6f} Hz，谱峰幅度{:.6f}，幅度误差{:.6e} %'.format(
            r['reference_amplitude_au'], r['estimated_frequency_hz'],
            r['estimated_amplitude_au'], r['amplitude_relative_error_pct']))
    print('输出文件夹：', folder)
    return results


def run_dual(out):
    folder = out / 'dual'
    folder.mkdir(parents=True, exist_ok=True)
    time_s = np.arange(SAMPLE_COUNT) / SAMPLE_RATE_HZ
    samples = np.zeros(SAMPLE_COUNT)
    for f, a in DUAL_COMPONENTS:
        samples += a * np.sin(2 * np.pi * f * time_s)
    frequency, amplitude = spectrum(samples, SAMPLE_RATE_HZ)
    peaks = find_spectral_peaks(frequency, amplitude, 2)
    # 检测结束后，才将所得谱峰与参考频率配对，计算验证误差。
    unused = list(peaks)
    results = []
    for ref_f, ref_a in sorted(DUAL_COMPONENTS):
        k = min(unused, key=lambda j: abs(float(frequency[j]) - ref_f))
        unused.remove(k)
        results.append(result_row('dual', ref_f, ref_a, frequency, amplitude, k))
    save_case(folder, 'dual', time_s, samples, frequency, amplitude, DUAL_COMPONENTS)
    save_results(folder / 'dual_results.csv', results)

    fig, axes = plt.subplots(2, 1, figsize=(9.5, 6.2))
    zoom = time_s < 1.0
    axes[0].plot(time_s[zoom], samples[zoom], '-o', color=COLORS[0], linewidth=1.1, markersize=2)
    axes[0].set_title('Two-tone input: first second')
    axes[0].set_xlim(0, 1)
    style_axis(axes[0], 'Time (s)', 'Amplitude (a.u.)')
    axes[1].plot(frequency, amplitude, color=COLORS[0], linewidth=1.2)
    axes[1].set_xlim(0, SEARCH_MAX_HZ)
    axes[1].set_ylim(0, float(np.max(amplitude[peaks])) * 1.3)
    axes[1].set_title('Detected local spectral peaks')
    style_axis(axes[1], 'Frequency (Hz)', 'Amplitude (a.u.)')
    for i, k in enumerate(sorted(peaks, key=lambda j: frequency[j])):
        color = COLORS[i]
        axes[1].plot(frequency[k], amplitude[k], 'o', color=color, markersize=5)
        axes[1].annotate(
            '{:.3f} Hz; {:.3f} a.u.'.format(frequency[k], amplitude[k]),
            xy=(frequency[k], amplitude[k]),
            xytext=(frequency[k] + .45, amplitude[k] + .10),
            arrowprops={'arrowstyle': '->', 'color': '#555555'}, fontsize=9)
    fig.tight_layout()
    fig.savefig(str(folder / 'dual_time_and_spectrum.png'), dpi=300, facecolor='white')
    print('\n双频实验完成：')
    for r in results:
        print('输入{:.1f} Hz、幅度{:.1f} -> 检测{:.6f} Hz、幅度{:.6f}；频率误差{:.3e} Hz，幅度误差{:.3e} %'.format(
            r['reference_frequency_hz'], r['reference_amplitude_au'],
            r['estimated_frequency_hz'], r['estimated_amplitude_au'],
            r['frequency_absolute_error_hz'], r['amplitude_relative_error_pct']))
    main_peak = peaks[0]
    print('本次主频：{:.6f} Hz；另一个峰是另一频率成分。'.format(frequency[main_peak]))
    print('输出文件夹：', folder)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['amplitude', 'dual', 'all'], default='all')
    parser.add_argument('--no-show', action='store_true', help='只保存图形，不打开窗口。')
    args = parser.parse_args()
    if SAMPLE_RATE_HZ <= 0 or SAMPLE_COUNT < 4:
        raise ValueError('请检查采样率和点数。')
    components = [(SINGLE_FREQUENCY_HZ, a) for a in AMPLITUDE_LEVELS] + list(DUAL_COMPONENTS)
    if any(not (0 < f < SAMPLE_RATE_HZ / 2) or a <= 0 for f, a in components):
        raise ValueError('各频率应在0与采样率一半之间，各幅度应为正数。')
    out = ROOT / 'day3_outputs'
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    print('第三天模拟信号实验：采样率{:g} Hz，点数{}，频率间隔{:g} Hz。'.format(
        SAMPLE_RATE_HZ, SAMPLE_COUNT, SAMPLE_RATE_HZ / SAMPLE_COUNT))
    if args.case in ['amplitude', 'all']:
        results['amplitude'] = run_amplitude(out)
    if args.case in ['dual', 'all']:
        results['dual'] = run_dual(out)
    record = {
        'data_source': 'Python-generated simulated data; algorithm validation only',
        'python': platform.python_version(), 'numpy': np.__version__,
        'matplotlib': matplotlib.__version__, 'case': args.case,
        'peak_detector': {'band_hz': [SEARCH_MIN_HZ, SEARCH_MAX_HZ],
                          'relative_height_threshold': MIN_RELATIVE_PEAK_HEIGHT,
                          'minimum_separation_hz': MIN_PEAK_SEPARATION_HZ},
        'results': results,
    }
    (out / ('run_' + args.case + '.json')).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n已保存原始样本、完整频谱、参数、结果表和图片。')
    print('保留本次实际运行结果，填写开题报告中的幅度变化与双频实验记录。')
    if not args.no_show:
        plt.show()
    plt.close('all')


if __name__ == '__main__':
    main()
