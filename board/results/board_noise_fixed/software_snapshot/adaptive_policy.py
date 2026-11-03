"""Causal contrast/noise policy with an explicit spectral ablation."""
import numpy as np

DEFAULTS={'window':64,'warmup':8,'alpha':0.25,'max_step':4.0,'contrast_fraction':0.7,
          'noise_factor':2.2,'spectral_gain':0.65,'minimum':20.0,'maximum':200.0}
MODES=('fixed','time','spectral_v1','spatial','spectral')

class AdaptivePolicy:
    def __init__(self,mode,fs,threshold=80,params=None):
        if mode not in MODES or not np.isfinite(fs) or fs<=0:raise ValueError('Invalid policy')
        self.mode,self.fs,self.base=mode,float(fs),float(threshold)
        self.p=dict(DEFAULTS,**(params or {}));self.value=float(threshold)
        self.history=[];self.contrast=None;self.edge_tail=None;self.noise=None;self.ratio=0.;self.steps=0
        self.last_decision={}
    def _record(self,value):
        self.last_decision={'threshold':int(value),'contrast':self.contrast,'edge_tail':self.edge_tail,
                            'noise_gradient_median':self.noise,'high_frequency_ratio':self.ratio,'history_samples':len(self.history)}
        return int(value)
    def next(self):
        if self.mode=='fixed':return self._record(round(self.base))
        n=len(self.history)
        if self.mode in ('time','spectral_v1'):
            if n<64:return self._record(round(self.value))
            a=np.asarray(self.history[-64:],float)
            if self.mode=='time':ratio=min(1.,float(a.mean())/24.)
            else:
                p=np.abs(np.fft.rfft((a-a.mean())*np.hanning(len(a))))**2
                f=np.fft.rfftfreq(len(a),1/self.fs)
                ratio=float(p[f>=.2*self.fs].sum()/max(float(p[1:].sum()),1e-30))
            target=np.clip(self.base*(1+.5*ratio),self.base*.75,min(255,self.base*1.5))
            self.value+=float(np.clip(.2*(target-self.value),-2,2))
        else:
            if n<self.p['warmup'] or self.contrast is None:return self._record(round(self.value))
            if self.mode=='spectral' and n>=self.p['window'] and n%4==0:
                a=np.asarray(self.history[-self.p['window']:],float)
                p=np.abs(np.fft.rfft((a-a.mean())*np.hanning(len(a))))**2
                f=np.fft.rfftfreq(len(a),1/self.fs)
                self.ratio=float(p[f>=.2*self.fs].sum()/max(float(p[1:].sum()),1e-30))
            # Preserve the baseline when measured high-gradient pixels already
            # clear it. Lowering T merely because brightness is low can create
            # background edges even though the object remains detectable.
            contrast=self.base if self.edge_tail>=self.base else max(self.p['minimum'],self.p['contrast_fraction']*self.edge_tail)
            noise=self.p['noise_factor']*self.noise
            if self.mode=='spectral':noise*=1+self.p['spectral_gain']*self.ratio
            target=float(np.clip(max(contrast,noise),self.p['minimum'],self.p['maximum']))
            self.value+=float(np.clip(self.p['alpha']*(target-self.value),-self.p['max_step'],self.p['max_step']))
        return self._record(round(self.value))
    def observe(self,now,previous,roi,magnitude=None):
        x0,y0,x1,y1=roi;a=np.asarray(now[y0:y1,x0:x1],dtype=np.int16)
        mad=None
        if previous is not None:
            mad=float(np.abs(a-previous[y0:y1,x0:x1].astype(np.int16)).mean());self.history.append(mad)
        self.steps+=1
        if self.mode in ('spatial','spectral') and (self.steps%4==1 or self.contrast is None):
            lo,hi=np.percentile(a[::2,::2],[1,99]);self.contrast=float(hi-lo)
            if magnitude is not None:
                g=magnitude[max(1,y0):min(127,y1),max(1,x0):min(127,x1)]
                self.noise=float(np.median(g));self.edge_tail=float(np.percentile(g[::2,::2],99))
            else:
                v=a.astype(np.int32)
                gx=v[:-2,2:]+2*v[1:-1,2:]+v[2:,2:]-v[:-2,:-2]-2*v[1:-1,:-2]-v[2:,:-2]
                gy=v[2:,:-2]+2*v[2:,1:-1]+v[2:,2:]-v[:-2,:-2]-2*v[:-2,1:-1]-v[:-2,2:]
                g=np.minimum(np.abs(gx)+np.abs(gy),255)
                self.noise=float(np.median(g));self.edge_tail=float(np.percentile(g[::2,::2],99))
        return mad
