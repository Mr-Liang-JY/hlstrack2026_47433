"""Meaningful PC tests. These do not constitute a PYNQ board test."""
from pathlib import Path
import sys
import unittest
import numpy as np
from shm_common import sobel_reference,roi_stats,spectrum,next_threshold,harmonic_fit
from run_board import status_fields,check_hwh

class ReferenceTests(unittest.TestCase):
    def test_scalar_convolution_independent(self):
        frame=np.random.RandomState(2).randint(0,256,(11,13)).astype(np.uint8)
        kx=np.array([[-1,0,1],[-2,0,2],[-1,0,1]])
        ky=kx.T
        for threshold in (0,1,80,255):
            expected=np.zeros(frame.shape,dtype=np.uint8)
            for y in range(1,10):
                for x in range(1,12):
                    patch=frame[y-1:y+2,x-1:x+2].astype(int)
                    mag=abs(int((patch*kx).sum()))+abs(int((patch*ky).sum()))
                    expected[y,x]=255 if min(mag,255)>=threshold else 0
            np.testing.assert_array_equal(sobel_reference(frame,threshold),expected)

    def test_roi_exclusive_bounds(self):
        image=np.zeros((8,8),dtype=np.uint8)
        image[2,3]=255;image[4,5]=255;image[5,5]=255
        self.assertEqual(roi_stats(image,[3,2,6,5]),(2,6))

    def test_fft_against_direct_dft_and_amplitude(self):
        fs=30.;t=np.arange(300)/fs
        values=2+1.5*np.sin(2*np.pi*0.9*t)
        frequency,amplitude,_=spectrum(values,fs)
        k=9;window=np.hanning(300)
        direct=2*abs(np.sum((values-values.mean())*window*np.exp(-2j*np.pi*k*np.arange(300)/300)))/window.sum()
        self.assertAlmostEqual(amplitude[k],direct,places=12)
        self.assertAlmostEqual(frequency[k],0.9)
        self.assertAlmostEqual(amplitude[k],1.5,places=3)

    def test_harmonic_frequency_not_imposed(self):
        fs=30.;t=np.arange(301)/fs
        y=7+3*np.cos(2*np.pi*1.137*t+0.4)+0.03*t
        result,_=harmonic_fit(t,y,fs)
        self.assertLess(abs(result['fitted_frequency_hz']-1.137),0.0003)
        self.assertGreater(result['r_squared'],0.9999)

    def test_absolute_difference_can_double_frequency(self):
        fs=30.;t=np.arange(601)/fs
        position=np.sin(2*np.pi*t)
        mad=np.abs(np.diff(position))
        f,a,_=spectrum(mad,fs)
        self.assertAlmostEqual(f[1+np.argmax(a[1:])],2.0)

    def test_feedback_warmup_and_step_limit(self):
        self.assertEqual(next_threshold(80,[1]*63,30),(80,None))
        value,ratio=next_threshold(80,[(i%2)*10 for i in range(64)],30)
        self.assertGreater(ratio,0.9)
        self.assertEqual(value,82)

    def test_status_protocol(self):
        fields=status_fields(0xD7300001)
        self.assertEqual(fields['signature'],13)
        self.assertEqual(fields['frame_id'],7)
        self.assertEqual(fields['error_code'],3)
        self.assertTrue(fields['done'])
        self.assertFalse(fields['busy'])

if __name__=='__main__':unittest.main(verbosity=2)
