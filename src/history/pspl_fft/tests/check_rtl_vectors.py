"""Check actual RTL simulation output through the PS decoding/FFT functions.
This produces simulation evidence only, not physical board evidence.
Usage: python tests/check_rtl_vectors.py --csv /path/to/rtl_samples.csv
"""
import argparse
import csv
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'python' / 'day6_pspl_fft.py'
spec = importlib.util.spec_from_file_location('day6', str(path))
day6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(day6)

parser = argparse.ArgumentParser()
parser.add_argument('--csv', required=True)
args = parser.parse_args()
with open(args.csv, newline='') as stream:
    rows = list(csv.DictReader(stream))
assert len(rows) == 3000, len(rows)
for row in rows:
    status = day6.decode_status(int(row['status_hex'], 16))
    sample = day6.decode_sample(int(row['data_hex'], 16))
    assert status['signature'] == 11 and status['sample_count'] == 1000
    assert status['done'] == 1 and status['busy'] == 0
    assert status['frequency_hz'] == int(row['frequency_hz'])
    assert sample['frame_id'] == status['frame_id'] and sample['valid']
    assert sample['counts'] == int(row['received_counts'])
for f,h in ((2,0), (5,1), (5,0)):
    counts = [int(row['received_counts']) for row in rows
              if int(row['frequency_hz']) == f and int(row['half_amplitude']) == h]
    assert len(counts) == 1000
    assert counts == day6.reference_counts(f,h)
    metrics = day6.analyze_counts(counts)[0]
    target_a = 0.5 if h else 1.0
    assert metrics['dominant_frequency_hz'] == f
    assert abs(metrics['peak_amplitude_au']-target_a) < 0.0001
    print('RTL->Python FFT: f={} Hz, half={}, A={:.9f}, raw|X|={:.9f}'.format(
        f,h,metrics['peak_amplitude_au'],metrics['raw_fft_magnitude_at_peak']))
print('PASS: 3000 RTL data/status vectors decoded and analyzed; simulation only.')
