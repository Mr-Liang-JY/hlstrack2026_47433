# -*- coding: utf-8 -*-
r"""第二天实验：读取第一天样本，计算FFT并提取主频和谱峰幅度。

在FPGA_Thesis文件夹运行：
    .venv\Scripts\python.exe day2_fft.py
指定其他第一天实验目录：
    .venv\Scripts\python.exe day2_fft.py --input "day1_outputs/f1_a1_fs100_n1000"
本实验分析Python生成的模拟数据，采用矩形窗、无零填充。
"""

import argparse
import csv
import json
import platform
from pathlib import Path

import numpy as np
import matplotlib
import matplotlib.pyplot as plt


# 分析频段内的最大非直流谱峰定义为本实验的主频。
SEARCH_MIN_HZ = 0.1
SEARCH_MAX_HZ = 10.0
ROOT = Path(__file__).resolve().parent


def single_sided_spectrum(samples, fs_hz):
    """由实数样本得到单边幅值谱；不倍增直流与奈奎斯特点。"""
    n = len(samples)
    # 第一步：减去平均值，去除直流分量。
    centered = samples - np.mean(samples)
    # 第二步：使用rfft计算实数样本的FFT。
    fft_values = np.fft.rfft(centered)
    # 第三步：采样间隔为1/fs，建立以Hz为单位的频率轴。
    frequency = np.fft.rfftfreq(n, d=1.0 / fs_hz)
    # 第四步：默认FFT未归一化，因此先除以实际样本数量。
    amplitude = np.abs(fft_values) / n
    if n % 2 == 0:
        amplitude[1:-1] *= 2.0
    else:
        amplitude[1:] *= 2.0
    return frequency, amplitude, fft_values


def read_day1(folder):
    csv_path = folder / 'day1_signal.csv'
    meta_path = folder / 'day1_parameters.json'
    if not csv_path.is_file() or not meta_path.is_file():
        raise FileNotFoundError(
            '输入目录需要同时包含day1_signal.csv和day1_parameters.json：\n' + str(folder))
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    fs_hz = float(meta['sample_rate_hz'])
    with csv_path.open('r', encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    index = np.array([int(r['sample_index']) for r in rows])
    time_s = np.array([float(r['time_s']) for r in rows])
    samples = np.array([float(r['amplitude_au']) for r in rows])
    if len(samples) < 4:
        raise ValueError('样本数量过少。')
    if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(samples)):
        raise ValueError('输入数据包含无效数值。')
    if not np.isfinite(fs_hz) or fs_hz <= 0:
        raise ValueError('采样率应为正数。')
    if not np.array_equal(index, np.arange(len(samples))):
        raise ValueError('样本序号需要从0开始连续排列。')
    if int(meta['sample_count']) != len(samples):
        raise ValueError('CSV实际点数与参数文件中的sample_count不一致。')
    if not np.allclose(np.diff(time_s), 1.0 / fs_hz, rtol=1e-5, atol=2e-8):
        raise ValueError('时间间隔与采样率记录不一致。')
    return time_s, samples, fs_hz, meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', help='第一天结果目录，或其中的day1_signal.csv路径。')
    parser.add_argument('--no-show', action='store_true', help='仅保存图形，不打开窗口。')
    args = parser.parse_args()

    if args.input:
        folder = Path(args.input)
        if not folder.is_absolute():
            folder = ROOT / folder
        if folder.is_file():
            folder = folder.parent
    else:
        candidates = [
            ROOT / 'day1_outputs' / 'f2_a1_fs100_n1000',
            ROOT / 'day1_outputs' / 'f2_fs100_n1000',
        ]
        folder = next((p for p in candidates if (p / 'day1_signal.csv').is_file()), None)
        if folder is None:
            print('没有找到第一天的2 Hz基础实验数据。')
            print('请先将第一天参数恢复为100 Hz、1000点、2 Hz、幅度1，然后运行：')
            print(r'.venv\Scripts\python.exe day1_signal.py')
            raise SystemExit(1)

    try:
        time_s, samples, fs_hz, meta = read_day1(folder)
    except (OSError, ValueError, KeyError) as exc:
        print('读取数据失败：', exc)
        raise SystemExit(1)

    frequency, amplitude, fft_values = single_sided_spectrum(samples, fs_hz)
    candidates = np.flatnonzero(
        (frequency > 0) & (frequency >= SEARCH_MIN_HZ) & (frequency <= SEARCH_MAX_HZ))
    if not len(candidates):
        print('当前频率栅格在所设分析频段内没有频点，请检查采样率、点数或分析频段。')
        raise SystemExit(1)
    peak_index = int(candidates[np.argmax(amplitude[candidates])])
    peak_frequency = float(frequency[peak_index])
    peak_amplitude = float(amplitude[peak_index])

    # 参考值只用于计算误差；主频和幅度的估计来自CSV中的样本。
    reference_frequency = meta.get('source_frequency_hz')
    reference_amplitude = meta.get('source_peak_amplitude_au')
    frequency_error = None if reference_frequency is None else abs(
        peak_frequency - float(reference_frequency))
    amplitude_error_pct = None if reference_amplitude is None or float(reference_amplitude) <= 0 else (
        abs(peak_amplitude - float(reference_amplitude)) / float(reference_amplitude) * 100.0)

    n = len(samples)
    summary = {
        'data_source': meta.get('data_source', 'See input metadata'),
        'input_csv': str((folder / 'day1_signal.csv').resolve()),
        'sample_rate_hz': fs_hz,
        'sample_count': n,
        'record_duration_s': n / fs_hz,
        'frequency_bin_spacing_hz': fs_hz / n,
        'window': 'rectangular',
        'zero_padding': False,
        'mean_removed_au': float(np.mean(samples)),
        'analysis_band_hz': [SEARCH_MIN_HZ, SEARCH_MAX_HZ],
        'peak_bin_index': peak_index,
        'peak_frequency_hz': peak_frequency,
        'peak_amplitude_au': peak_amplitude,
        'raw_fft_peak_magnitude': float(abs(fft_values[peak_index])),
        'reference_frequency_hz': reference_frequency,
        'reference_peak_amplitude_au': reference_amplitude,
        'frequency_absolute_error_hz': frequency_error,
        'amplitude_relative_error_pct': amplitude_error_pct,
        'python': platform.python_version(),
        'numpy': np.__version__,
        'matplotlib': matplotlib.__version__,
    }
    out = ROOT / 'day2_outputs' / folder.name
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'day2_spectrum.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['frequency_hz', 'single_sided_amplitude_au'])
        for f, a in zip(frequency, amplitude):
            writer.writerow(['{:.10g}'.format(float(f)), '{:.12g}'.format(float(a))])
    with (out / 'day2_summary.csv').open('w', encoding='utf-8', newline='') as stream:
        columns = [
            'sample_rate_hz', 'sample_count', 'reference_frequency_hz',
            'reference_peak_amplitude_au', 'peak_frequency_hz', 'peak_amplitude_au',
            'frequency_absolute_error_hz', 'amplitude_relative_error_pct',
            'frequency_bin_spacing_hz',
        ]
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerow(summary)
    (out / 'day2_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    fig, axes = plt.subplots(2, 1, figsize=(9.5, 6.2))
    color = '#1763A6'
    elapsed = time_s - time_s[0]
    zoom_duration = min(1.0, n / fs_hz)
    zoom = elapsed < zoom_duration
    axes[0].plot(elapsed[zoom], samples[zoom], '-o', color=color, linewidth=1.2, markersize=2.5)
    axes[0].set_title('Input waveform: first second')
    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('Amplitude (a.u.)')
    axes[0].set_xlim(0, zoom_duration)
    axes[1].plot(frequency, amplitude, color=color, linewidth=1.2)
    axes[1].plot(peak_frequency, peak_amplitude, 'o', color=color, markersize=5)
    axes[1].set_title('Single-sided amplitude spectrum: rectangular window')
    axes[1].set_xlabel('Frequency (Hz)')
    axes[1].set_ylabel('Amplitude (a.u.)')
    display_max = min(SEARCH_MAX_HZ, fs_hz / 2)
    axes[1].set_xlim(0, display_max)
    axes[1].set_ylim(0, max(peak_amplitude * 1.25, 0.1))
    label_x = min(peak_frequency + display_max * .1, display_max * .65)
    axes[1].annotate(
        'Peak: {:.4f} Hz\nAmplitude: {:.4f} a.u.'.format(peak_frequency, peak_amplitude),
        xy=(peak_frequency, peak_amplitude), xytext=(label_x, peak_amplitude * .72),
        arrowprops={'arrowstyle': '->', 'color': '#555555'}, fontsize=10)
    for ax in axes:
        ax.grid(True, color='#D9DDE2', linewidth=.6)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    fig.tight_layout()
    fig.savefig(str(out / 'day2_time_and_spectrum.png'), dpi=300, facecolor='white')

    print('第二天FFT实验运行完成。')
    print('输入数据：', folder / 'day1_signal.csv')
    print('采样率：{:g} Hz；点数：{}；记录时长：{:g} s。'.format(fs_hz, n, n / fs_hz))
    print('频率间隔：{:.6f} Hz；谱峰所在频点序号：{}。'.format(fs_hz / n, peak_index))
    print('计算得到的主频：{:.6f} Hz。'.format(peak_frequency))
    print('计算得到的谱峰幅度：{:.6f} a.u.。'.format(peak_amplitude))
    print('该频点未经归一化的FFT模值：{:.6f}。'.format(abs(fft_values[peak_index])))
    if frequency_error is not None:
        print('频率绝对误差：{:.6e} Hz。'.format(frequency_error))
    if amplitude_error_pct is not None:
        print('幅度相对误差：{:.6e} %。'.format(amplitude_error_pct))
    print('输出文件夹：', out)
    print('已保存时域与频谱图、完整幅值谱以及结果表。')
    print('本次分析对象是第一天生成的模拟信号，结果用于算法验证。')
    if not args.no_show:
        plt.show()
    plt.close(fig)


if __name__ == '__main__':
    main()
