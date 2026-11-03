"""Host unit tests with an explicitly fake bus, never board measurement data.
Run from the package root: python -m unittest discover -s tests -v
"""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / 'python' / 'day6_pspl_fft.py'
SPEC = importlib.util.spec_from_file_location('day6', str(MODULE))
day6 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(day6)


class FakeClock(object):
    def __init__(self):
        self.now = 0.0
    def clock(self):
        return self.now
    def sleep(self, duration):
        self.now += duration


class FakeBus(object):
    def __init__(self):
        self.control = 0
        self.frame_id = 0
        self.count = 0
        self.busy = 0
        self.done = 0
        self.frequency = 2
        self.half = 0
        self.polls = 0
        self.pending = None
        self.stuck = False
        self.corrupt_index = None
        self.wrong_data_tag = False
        self.wrong_signature = False
        self.wrong_count = False
        self.old_data = 0
        self.stale_reads = 0

    def write(self, offset, value):
        assert offset == 0
        old = self.control
        self.control = value
        if not value & 2:
            self.frame_id = self.count = self.busy = self.done = 0
            self.frequency = 2
            self.half = 0
            self.pending = None
        elif value & 1 and not old & 1 and not self.busy:
            # Leave the previous done/id visible for a poll, like an input
            # pipeline, to exercise stale-completion rejection.
            self.pending = (5 if value & 4096 else 2, (value >> 13) & 1)
            self.polls = 0
        if ((value >> 2) & 1023) != ((old >> 2) & 1023):
            self.stale_reads = 2

    def status_read(self):
        if self.pending is not None and not self.stuck:
            self.polls += 1
            if self.polls == 2:
                self.frequency, self.half = self.pending
                self.frame_id = (self.frame_id + 1) & 15
                self.busy, self.done, self.count = 1, 0, 500
            elif self.polls >= 3:
                self.busy, self.done = 0, 1
                self.count = 999 if self.wrong_count else 1000
                self.pending = None
        return ((0xA if self.wrong_signature else 0xB) << 28
                | self.frame_id << 24 | bool(self.control & 2) << 23
                | self.done << 22 | self.busy << 21
                | int(self.frequency == 5) << 20 | self.half << 19 | self.count)

    def data_read(self):
        if self.stale_reads:
            self.stale_reads -= 1
            return self.old_data
        address = (self.control >> 2) & 1023
        counts = day6.reference_counts(self.frequency, self.half)[address]
        if self.corrupt_index == address:
            counts += 7
        frame_id = (self.frame_id + int(self.wrong_data_tag)) & 15
        self.old_data = 0xC0000000 | frame_id << 24 | self.done << 23 | (counts & 65535)
        return self.old_data


class ControlMMIO(object):
    def __init__(self, bus): self.bus = bus
    def write(self, offset, value): self.bus.write(offset, value)
    def read(self, offset):
        assert offset == 8
        return self.bus.status_read()


class DataMMIO(object):
    def __init__(self, bus): self.bus = bus
    def read(self, offset):
        assert offset == 0
        return self.bus.data_read()


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.bus = FakeBus()
        self.timer = FakeClock()
        self.driver = day6.CaptureDriver(ControlMMIO(self.bus), DataMMIO(self.bus),
                                        clock=self.timer.clock, sleeper=self.timer.sleep)
        self.driver.reset()

    def test_two_frames_with_stale_done_and_two_stale_data_reads(self):
        for frequency, half, frame in ((2, 0, 1), (5, 1, 2)):
            actual = self.driver.capture(frequency, half)
            self.assertEqual(actual['frame_id'], frame)
            self.assertEqual(actual['matched_samples'], 1000)
            self.assertTrue(any(x < 0 for x in actual['received_counts']))

    def test_timeout_instead_of_reusing_previous_done(self):
        self.driver.capture(2)
        self.bus.stuck = True
        with self.assertRaises(TimeoutError):
            self.driver.capture(5, timeout=0.1)

    def test_frame_id_wrap(self):
        self.bus.frame_id = 15
        actual = self.driver.capture(2)
        self.assertEqual(actual['frame_id'], 0)

    def test_wrong_signature_rejected(self):
        self.bus.wrong_signature = True
        with self.assertRaises(RuntimeError): self.driver.status()

    def test_busy_rejected(self):
        self.bus.busy = 1
        with self.assertRaises(RuntimeError): self.driver.capture(2)

    def test_wrong_count_rejected(self):
        self.bus.wrong_count = True
        with self.assertRaises(RuntimeError): self.driver.capture(2)

    def test_wrong_data_frame_rejected(self):
        self.bus.wrong_data_tag = True
        with self.assertRaises(RuntimeError): self.driver.capture(2)

    def test_bad_value_is_retained_never_replaced_by_reference(self):
        self.bus.corrupt_index = 17
        actual = self.driver.capture(2)
        expected = day6.reference_counts(2, 0)
        self.assertEqual(actual['matched_samples'], 999)
        self.assertEqual(actual['received_counts'][17], expected[17] + 7)
        self.assertEqual(actual['rows'][17]['match'], 0)


class SpectrumTests(unittest.TestCase):
    def test_literal_decoding_and_signed_boundaries(self):
        self.assertEqual(day6.signed16(0xFFFF), -1)
        self.assertEqual(day6.signed16(0x8000), -32768)
        self.assertEqual(day6.signed16(0x7FFF), 32767)
        self.assertEqual(day6.decode_sample(0xC180D8F0)['counts'], -10000)
        state = day6.decode_status(0xB2D803E8)
        self.assertEqual((state['signature'], state['frame_id'], state['frequency_hz'],
                          state['half_amplitude'], state['sample_count']), (11, 2, 5, 1, 1000))

    def test_ideal_sine_normalization_and_dc_removal(self):
        t = np.arange(1000) / 100.0
        x = (0.7 * np.sin(2*np.pi*3*t) + 0.2) * 10000
        metrics = day6.analyze_counts(x)[0]
        self.assertAlmostEqual(metrics['dominant_frequency_hz'], 3.0)
        self.assertAlmostEqual(metrics['peak_amplitude_au'], 0.7)
        self.assertAlmostEqual(metrics['mean_au'], 0.2)
        self.assertAlmostEqual(metrics['raw_fft_magnitude_at_peak'], 350.0)

    def test_quantized_modes_detected_without_passing_expected_peak(self):
        for f, h, a in ((2,0,1), (5,1,0.5), (2,1,0.5), (5,0,1)):
            metrics = day6.analyze_counts(day6.reference_counts(f,h))[0]
            self.assertEqual(metrics['dominant_frequency_hz'], f)
            self.assertLess(abs(metrics['peak_amplitude_au']-a), 0.0001)

    def test_wrong_number_of_samples_rejected(self):
        with self.assertRaises(ValueError): day6.analyze_counts([0]*999)

    def test_nyquist_bin_not_doubled(self):
        x = 10000 * (-1.0) ** np.arange(1000)
        amplitude = day6.analyze_counts(x)[3]
        self.assertAlmostEqual(amplitude[-1], 1.0)


if __name__ == '__main__':
    unittest.main()
