from pathlib import Path
import sys,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from video_core import reference,statistics
from adaptive_policy import AdaptivePolicy
from frequency_tracker import estimate
from drift_monitor import DriftMonitor
from native_codec import make_packet,render_packet,PACKET_WORDS

class UpgradeChecks(unittest.TestCase):
 def test_reference_matches_opencv(self):
  import cv2
  rng=np.random.default_rng(443)
  for a in [np.zeros((128,128),np.uint8),np.full((128,128),255,np.uint8),rng.integers(0,256,(128,128),dtype=np.uint8)]:
   e,m=reference(a,80);gx=cv2.Sobel(a,cv2.CV_16S,1,0,ksize=3);gy=cv2.Sobel(a,cv2.CV_16S,0,1,ksize=3)
   expected=np.minimum(abs(gx.astype(int))+abs(gy.astype(int)),255).astype(np.uint8);expected[[0,-1],:]=0;expected[:,[0,-1]]=0
   self.assertTrue(np.array_equal(m,expected));self.assertTrue(np.array_equal(e,(expected>=80).astype(np.uint8)*255))
 def test_known_frequencies(self):
  t=np.arange(300)/30
  for f in [.5,.8,1.25,2.]:
   result=estimate((60+10*np.sin(2*np.pi*f*t)).tolist(),30)[0]
   self.assertTrue(result['valid']);self.assertLess(abs(result['frequency_hz']-f)/f,.05)
 def test_invalid_motion(self):
  self.assertFalse(estimate([63.]*300,30)[0]['valid'])
  self.assertFalse(estimate([1.]*200+[None]*10+[5.]*20,30)[0]['valid'])
 def test_packet_and_image_mapping(self):
  a=np.arange(16384,dtype=np.uint16).astype(np.uint8).reshape(128,128)
  m={'time_s':1.,'frame_index':30,'threshold':80,'roi_edge_count':100,'centroid_y':None,
     'frequency':{'valid':False,'frequency_hz':None,'samples':31,'bin_spacing_hz':None}}
  p=make_packet(a,a,(1,1,127,127),m,[],[],[]);self.assertEqual(p.shape,(PACKET_WORDS,));self.assertEqual(p.nbytes,33792)
  image=render_packet(p);self.assertEqual(image.shape,(720,1280));self.assertEqual(int(image[130+4*64,24+4*64]),int(a[64,64]))
 def test_causal_threshold(self):
  p=AdaptivePolicy('spectral',30);a=np.zeros((128,128),np.uint8);a[40:80,40:80]=180
  before=p.next();p.observe(a,None,(1,1,127,127),reference(a,80)[1]);self.assertEqual(before,80)
  self.assertEqual(p.last_decision['history_samples'],0)
 def test_no_hardware_import(self):self.assertNotIn('pynq',sys.modules)
 def test_drift_requires_three_distinct_valid_updates(self):
  m=DriftMonitor(1.,.15)
  for i in range(2):self.assertFalse(m.update(dict(valid=True,frequency_hz=1.5,updated_at_frame=i))['alarm'])
  self.assertFalse(m.update(dict(valid=True,frequency_hz=1.5,updated_at_frame=1))['alarm'])
  self.assertTrue(m.update(dict(valid=True,frequency_hz=1.5,updated_at_frame=2))['alarm'])
  self.assertFalse(m.update(dict(valid=False,frequency_hz=None,updated_at_frame=3))['alarm'])
  self.assertFalse(m.update(dict(valid=True,frequency_hz=1.,updated_at_frame=4))['alarm'])
 def test_drift_calibration_and_invalid_estimate(self):
  m=DriftMonitor()
  for i in range(5):result=m.update(dict(valid=True,frequency_hz=1.,updated_at_frame=i))
  self.assertEqual(result['reference_hz'],1.);self.assertFalse(result['alarm'])
  self.assertFalse(m.update(dict(valid=True,frequency_hz=float('nan'),updated_at_frame=5))['alarm'])

if __name__=='__main__':unittest.main(verbosity=2)
