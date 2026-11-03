"""Frequency-deviation indication; never labels a physical machine fault."""
import numpy as np
class DriftMonitor:
 def __init__(self,reference_hz=None,tolerance=.15):
  if reference_hz is not None and reference_hz<=0:raise ValueError('Reference frequency must be positive')
  if not 0<tolerance<1:raise ValueError('Invalid relative tolerance')
  self.reference=reference_hz;self.tolerance=tolerance;self.calibration=[];self.last=None;self.streak=0
 def update(self,estimate):
  token=estimate.get('updated_at_frame')
  frequency=estimate.get('frequency_hz')
  valid=bool(estimate.get('valid',False) and frequency is not None and np.isfinite(frequency) and frequency>0)
  if token!=self.last:
   self.last=token
   if valid:
    if self.reference is None:
     self.calibration.append(frequency)
     if len(self.calibration)>=5:self.reference=float(np.median(self.calibration))
    delta=abs(frequency-self.reference)/self.reference if self.reference else None
    self.streak=self.streak+1 if delta is not None and delta>self.tolerance else 0
   else:self.streak=0
  delta=abs(frequency-self.reference)/self.reference if valid and self.reference else None
  return {'reference_hz':self.reference,'deviation_fraction':delta,'alarm':valid and self.streak>=3}
