"""Host-side protocol tests with a fake backend, NOT board evidence.

Run with normal Python: python tests/test_driver.py
RTL behavior is checked separately by sim/tb_pspl_capture_top.v.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from day5_pspl import CaptureDriver, decode_status


class FakeMMIO(object):
    def __init__(self):
        self.now = 0.0
        self.control = 0
        self.ready = 0
        self.frame = 0
        self.busy = 0
        self.done = 0
        self.count = 0
        self.base = 0
        self.never_start = False
        self.corrupt_address = None
        self.stale = None

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def raw(self):
        address = (self.control >> 2) & 15
        value = ((self.base + address) & 65535) if address < self.count else 0
        if address == self.corrupt_address:
            value ^= 1
        return (0xA0000000 | (self.frame << 24) | (self.ready << 23)
                | (self.done << 22) | (self.busy << 21)
                | (self.count << 16) | value)

    def write(self, offset, value):
        assert offset == 0
        old = self.control
        self.control = value
        if not value & 2:
            self.ready = self.frame = self.busy = self.done = self.count = 0
            self.stale = None
            return
        self.ready = 1
        if value & 1 and not old & 1 and not self.busy and not self.never_start:
            # Simulate one old response immediately after a new request.
            self.stale = self.raw()
            self.frame = (self.frame + 1) & 15
            self.busy, self.done, self.count = 1, 0, 0
            self.base = (value >> 16) & 65535

    def read(self, offset):
        assert offset == 8
        if self.stale is not None:
            value, self.stale = self.stale, None
            return value
        if self.busy:
            self.count = min(16, self.count + 4)
            if self.count == 16:
                self.busy, self.done = 0, 1
        return self.raw()


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.mmio = FakeMMIO()
        self.driver = CaptureDriver(self.mmio, clock=self.mmio.clock,
                                    sleeper=self.mmio.sleep)
        self.driver.reset()

    def test_two_frames_and_stale_done_response(self):
        a = self.driver.capture(0)
        b = self.driver.capture(100)
        self.assertEqual(a['received_samples'], list(range(16)))
        self.assertEqual(b['received_samples'], list(range(100, 116)))
        self.assertEqual((a['frame_id'], b['frame_id']), (1, 2))
        self.assertTrue(a['passed'] and b['passed'])

    def test_timeout_when_request_is_not_accepted(self):
        self.driver.capture(0)
        self.mmio.never_start = True
        with self.assertRaises(TimeoutError):
            self.driver.capture(100, timeout=0.01)

    def test_refuses_busy_core(self):
        self.mmio.busy = 1
        with self.assertRaisesRegex(RuntimeError, 'already busy'):
            self.driver.capture(0)

    def test_signature_failure(self):
        self.mmio.read = lambda offset: 0
        with self.assertRaisesRegex(RuntimeError, 'signature mismatch'):
            self.driver.status()

    def test_corrupt_data_is_reported_as_received(self):
        self.mmio.corrupt_address = 3
        result = self.driver.capture(100)
        self.assertFalse(result['passed'])
        self.assertEqual(result['matched_samples'], 15)
        self.assertNotEqual(result['received_samples'][3], 103)

    def test_frame_id_wrap(self):
        self.mmio.frame = 15
        result = self.driver.capture(65530)
        self.assertEqual(result['frame_id'], 0)
        self.assertEqual(result['received_samples'], [(65530+i) & 65535 for i in range(16)])

    def test_decoder_against_rtl_example(self):
        # Literal status for signature A, frame 1, released reset,
        # done, not busy, count16, sample15.
        result = decode_status(0xA1D0000F)
        self.assertEqual(result['sample'], 15)
        self.assertEqual(result['sample_count'], 16)
        self.assertEqual(result['frame_id'], 1)
        self.assertEqual((result['ready'], result['done'], result['busy']), (1, 1, 0))


if __name__ == '__main__':
    unittest.main()
