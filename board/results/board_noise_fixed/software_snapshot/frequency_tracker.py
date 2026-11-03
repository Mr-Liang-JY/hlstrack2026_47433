"""Causal, bounded-window displacement spectrum with explicit validity gates."""
import numpy as np

def estimate(values,fs,window=512):
    suffix=[]
    for v in reversed(values[-window:]):
        if v is None or not np.isfinite(v):break
        suffix.append(float(v))
    a=np.asarray(suffix[::-1],float);n=len(a)
    result={'valid':False,'frequency_hz':None,'samples':n,'bin_spacing_hz':fs/n if n else None,'reason':'collecting samples'}
    if n<64:return result,[],[]
    if np.std(a)<.3:result['reason']='motion too small';return result,[],[]
    t=np.arange(n,dtype=float);a=a-np.polyval(np.polyfit(t,a,1),t)
    amp=np.abs(np.fft.rfft(a*np.hanning(n)));f=np.fft.rfftfreq(n,1/fs)
    eligible=np.flatnonzero((f>=.2)&(f<=min(5,fs/2)))
    if not len(eligible):return result,[],[]
    k=int(eligible[np.argmax(amp[eligible])]);peak=float(f[k])
    if 0<k<len(amp)-1:
        b=np.log(np.maximum(amp[k-1:k+2],1e-20));d=b[0]-2*b[1]+b[2]
        if abs(d)>1e-12:peak=(k+float(np.clip(.5*(b[0]-b[2])/d,-.5,.5)))*fs/n
    power=amp**2;concentration=float(power[max(1,k-1):k+2].sum()/max(float(power[eligible].sum()),1e-30))
    result.update(peak_bin_hz=float(f[k]),peak_concentration=concentration)
    if peak*n/fs<2:result['reason']='need two cycles'
    elif concentration<.45:result['reason']='weak periodicity'
    elif not .2<=peak<=min(5,fs/2):result['reason']='outside analysis band'
    else:result.update(valid=True,frequency_hz=peak,period_s=1/peak,reason='centroid-y spectral estimate')
    return result,f.tolist(),amp.tolist()

class FrequencyTracker:
    def __init__(self,fs,window=512,every=6):
        self.fs,self.window,self.every=fs,window,every;self.values=[]
        self.last=({'valid':False,'frequency_hz':None,'samples':0,'bin_spacing_hz':None,'reason':'collecting samples'},[],[])
    def observe(self,value):
        self.values.append(value)
        if value is None or not np.isfinite(value) or len(self.values)<=64 or len(self.values)%self.every==0:
            self.last=estimate(self.values,self.fs,self.window)
            self.last[0]['updated_at_frame']=len(self.values)
        return self.last
    def finish(self):return estimate(self.values,self.fs,self.window)
