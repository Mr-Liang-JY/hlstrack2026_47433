# -*- coding: utf-8 -*-
"""第一天实验：生成正弦信号、显示时域波形并保存原始样本。

在脚本所在文件夹运行：python day1_signal.py
依赖：numpy、matplotlib。使用 --no-show 可仅保存图形、不打开窗口。
本实验数据由Python生成，用于学习采样和程序验证，不属于板卡采集数据。
本脚本尚未执行FFT，参数中的信号频率是输入设定值。
"""

import argparse
import csv
import json
import platform
import sys
from pathlib import Path

import numpy as np
import matplotlib
import matplotlib.pyplot as plt


# 今天先理解并修改下面四个参数。
SAMPLE_RATE_HZ = 100.0   # 每秒采样点数；相邻样本间隔为1 / SAMPLE_RATE_HZ。
SAMPLE_COUNT = 1000     # 总样本数量。
SIGNAL_FREQ_HZ = 1.0   # 正弦信号每秒振动次数；这是输入参数，不是测量结果。
AMPLITUDE_AU = 1.0      # 正弦的峰值幅度，a.u.表示归一化单位，不表示电压。


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-show', action='store_true', help='Save without opening a plot window.')
    args = parser.parse_args()

    if SAMPLE_RATE_HZ <= 0 or SIGNAL_FREQ_HZ <= 0 or AMPLITUDE_AU <= 0:
        raise ValueError('采样率、信号频率与幅度应为正数。')
    if not isinstance(SAMPLE_COUNT, int) or SAMPLE_COUNT < 2:
        raise ValueError('SAMPLE_COUNT应为不小于2的整数。')
    if SIGNAL_FREQ_HZ >= SAMPLE_RATE_HZ / 2:
        raise ValueError('本次正弦实验需满足信号频率小于采样率的一半。')

    # 先生成整数序号0至999，再把序号换算成时间；不重复区间终点。
    sample_index = np.arange(SAMPLE_COUNT)
    time_s = sample_index / SAMPLE_RATE_HZ

    # sin函数的输入是角度的弧度值。2πf乘以时间得到相位。
    signal = AMPLITUDE_AU * np.sin(2 * np.pi * SIGNAL_FREQ_HZ * time_s)

    # 参数改变时使用不同目录，保留原始实验结果。
    tag = 'f{:g}_a{:g}_fs{:g}_n{}'.format(
        SIGNAL_FREQ_HZ, AMPLITUDE_AU, SAMPLE_RATE_HZ, SAMPLE_COUNT)
    out = Path(__file__).resolve().parent / 'day1_outputs' / tag
    out.mkdir(parents=True, exist_ok=True)

    csv_path = out / 'day1_signal.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['sample_index', 'time_s', 'amplitude_au'])
        for i, t, value in zip(sample_index, time_s, signal):
            writer.writerow([int(i), '{:.8f}'.format(float(t)), '{:.10f}'.format(float(value))])

    # 上图为全部样本；下图为前1秒的局部波形。
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 6.2))
    color = '#1763A6'
    axes[0].plot(time_s, signal, color=color, linewidth=1.2)
    axes[0].set_title('Simulated sine wave: {} Hz'.format(SIGNAL_FREQ_HZ))
    axes[0].set_xlim(0, SAMPLE_COUNT / SAMPLE_RATE_HZ)
    zoom = time_s < min(1.0, SAMPLE_COUNT / SAMPLE_RATE_HZ)
    axes[1].plot(time_s[zoom], signal[zoom], '-o', color=color, linewidth=1.2, markersize=2.6)
    axes[1].set_title('First second: dots represent samples')
    axes[1].set_xlim(0, min(1.0, SAMPLE_COUNT / SAMPLE_RATE_HZ))
    for ax in axes:
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (a.u.)')
        ax.set_ylim(-1.2 * AMPLITUDE_AU, 1.2 * AMPLITUDE_AU)
        ax.grid(True, color='#D9DDE2', linewidth=0.6)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    fig.tight_layout()
    png_path = out / 'day1_waveform.png'
    fig.savefig(str(png_path), dpi=300, facecolor='white')

    params = {
        'data_source': 'Python-generated sine wave; not hardware acquisition',
        'sample_rate_hz': SAMPLE_RATE_HZ,
        'sample_count': SAMPLE_COUNT,
        'source_frequency_hz': SIGNAL_FREQ_HZ,
        'source_peak_amplitude_au': AMPLITUDE_AU,
        'sample_interval_s': 1 / SAMPLE_RATE_HZ,
        'record_duration_s': SAMPLE_COUNT / SAMPLE_RATE_HZ,
        'last_sample_time_s': float(time_s[-1]),
        'signal_period_s': 1 / SIGNAL_FREQ_HZ,
        'frequency_estimation_performed': False,
        'python': platform.python_version(),
        'numpy': np.__version__,
        'matplotlib': matplotlib.__version__,
    }
    with (out / 'day1_parameters.json').open('w', encoding='utf-8') as stream:
        json.dump(params, stream, ensure_ascii=False, indent=2)

    environment = '\n'.join([
        'Python executable: ' + sys.executable,
        'Python version: ' + platform.python_version(),
        'NumPy version: ' + np.__version__,
        'Matplotlib version: ' + matplotlib.__version__,
        'Operating system: ' + platform.platform(),
        'Data source: Python-generated sine wave, not hardware acquisition.',
    ])
    (out / 'day1_environment.txt').write_text(environment + '\n', encoding='utf-8')

    print('第一天实验运行完成。')
    print('采样率：{} Hz；样本数量：{}；输入频率：{} Hz。'.format(
        SAMPLE_RATE_HZ, SAMPLE_COUNT, SIGNAL_FREQ_HZ))
    print('采样间隔：{:.2f} s；记录时长：{:g} s；最后一个样本时刻：{:.2f} s。'.format(
        1 / SAMPLE_RATE_HZ, SAMPLE_COUNT / SAMPLE_RATE_HZ, time_s[-1]))
    print('信号周期：{:g} s；幅度单位：a.u.。'.format(1 / SIGNAL_FREQ_HZ))
    print('前5个样本：', np.round(signal[:5], 6))
    print('输出文件夹：', out)
    print('已保存CSV、波形图、参数记录和环境记录。今天的脚本未执行FFT。')
    if not args.no_show:
        plt.show()
    plt.close(fig)


if __name__ == '__main__':
    main()
