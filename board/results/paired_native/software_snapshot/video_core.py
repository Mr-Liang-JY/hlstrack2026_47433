"""Portable file-video processing and display composition; no network access."""
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 128, 128
CANVAS = (640, 360)
ROOT = Path(__file__).resolve().parents[1]

def reference(frame, threshold):
    a = np.asarray(frame, dtype=np.int32)
    gx = a[:-2,2:]+2*a[1:-1,2:]+a[2:,2:]-a[:-2,:-2]-2*a[1:-1,:-2]-a[2:,:-2]
    gy = a[2:,:-2]+2*a[2:,1:-1]+a[2:,2:]-a[:-2,:-2]-2*a[:-2,1:-1]-a[:-2,2:]
    mag = np.zeros((H,W),np.uint8)
    mag[1:-1,1:-1]=np.minimum(np.abs(gx)+np.abs(gy),255).astype(np.uint8)
    edge = np.zeros_like(mag)
    edge[1:-1,1:-1]=(mag[1:-1,1:-1]>=threshold).astype(np.uint8)*255
    return edge,mag

def statistics(edge,roi):
    x0,y0,x1,y1=roi
    mask=edge[y0:y1,x0:x1]!=0
    n=int(mask.sum())
    s=int((mask*np.arange(y0,y1,dtype=np.uint32)[:,None]).sum())
    return n,s

class Policy:
    def __init__(self,mode,fs,threshold):
        self.mode,self.fs,self.base=mode,fs,threshold
        self.value=float(threshold); self.history=[]
    def next(self):
        if len(self.history)<64 or self.mode=='fixed':return int(round(self.value))
        a=np.asarray(self.history[-64:],float)
        if self.mode=='time':ratio=min(1.0,float(a.mean())/24.0)
        else:
            p=np.abs(np.fft.rfft((a-a.mean())*np.hanning(len(a))))**2
            f=np.fft.rfftfreq(len(a),1/self.fs)
            ratio=float(p[f>=0.2*self.fs].sum()/max(p[1:].sum(),1e-30))
        target=np.clip(self.base*(1+0.5*ratio),self.base*0.75,min(255,self.base*1.5))
        self.value+=float(np.clip(0.2*(target-self.value),-2,2))
        return int(round(self.value))
    def observe(self,now,previous,roi):
        if previous is None:return None
        x0,y0,x1,y1=roi
        mad=float(np.abs(now[y0:y1,x0:x1].astype(np.int16)-previous[y0:y1,x0:x1]).mean())
        self.history.append(mad)
        return mad

def estimate_frequency(values,fs):
    # Only a contiguous suffix is used: never fill a missing centroid with zero.
    contiguous=[]
    for value in reversed(values[-256:]):
        if value is None or not math.isfinite(value):break
        contiguous.append(value)
    a=np.asarray(contiguous[::-1],dtype=float)
    info={'valid':False,'frequency_hz':None,'samples':len(a),
          'bin_spacing_hz':fs/len(a) if len(a) else None,'reason':'collecting samples'}
    if len(a)<64:return info,[],[]
    if np.std(a)<0.3:
        info['reason']='motion too small';return info,[],[]
    # Remove a fitted linear trend to limit illumination/drift leakage.
    t=np.arange(len(a),dtype=float); fit=np.polyfit(t,a,1)
    centered=a-np.polyval(fit,t)
    spectrum=np.abs(np.fft.rfft(centered*np.hanning(len(a))))
    freq=np.fft.rfftfreq(len(a),1/fs)
    select=np.flatnonzero((freq>=0.2)&(freq<=min(5,fs/2)))
    if not len(select):return info,[],[]
    k=int(select[np.argmax(spectrum[select])]); peak=float(freq[k])
    if 0<k<len(spectrum)-1:
        log=np.log(np.maximum(spectrum[k-1:k+2],1e-20))
        denom=log[0]-2*log[1]+log[2]
        if abs(denom)>1e-12:
            peak=(k+float(np.clip(0.5*(log[0]-log[2])/denom,-0.5,0.5)))*fs/len(a)
    power=spectrum**2
    concentration=float(power[max(1,k-1):k+2].sum()/max(power[select].sum(),1e-30))
    info.update(peak_bin_hz=float(freq[k]),peak_concentration=concentration)
    if peak*len(a)/fs<2:info['reason']='need at least two cycles'
    elif concentration<0.45:info['reason']='weak periodicity'
    elif not 0.2<=peak<=min(5,fs/2):info['reason']='peak outside band'
    else:info.update(valid=True,frequency_hz=float(peak),reason='centroid-y FFT estimate')
    return info,freq.tolist(),spectrum.tolist()

def load_font(size):
    path=ROOT/'data/DejaVuSans.ttf'
    if path.exists():return ImageFont.truetype(str(path),size)
    return ImageFont.load_default()

def _plot(draw,box,values,fill=180,limits=None):
    x0,y0,x1,y1=box
    draw.rectangle(box,outline=55)
    finite=[float(v) for v in values if v is not None and math.isfinite(v)]
    if len(finite)<2:return
    lo,hi=limits or (min(finite),max(finite))
    span=max(hi-lo,0.01); points=[]
    for i,v in enumerate(values):
        if v is None or not math.isfinite(v):
            if len(points)>1:draw.line(points,fill=fill,width=1)
            points=[];continue
        points.append((x0+i*(x1-x0)/max(1,len(values)-1),y1-(float(v)-lo)/span*(y1-y0)))
    if len(points)>1:draw.line(points,fill=fill,width=1)

class Composer:
    def __init__(self):
        self.font=load_font(11);self.small=load_font(9);self.title=load_font(16)
    def render(self,gray,magnitude,edge,roi,metrics,history,freq,amplitude,binary=False,reference_only=False):
        im=Image.new('L',CANVAS,10);d=ImageDraw.Draw(im)
        d.text((12,6),'MOTION SPECTRUM  /  FILE VIDEO',font=self.title,fill=200)
        label='PC REFERENCE - PL NOT RUN' if reference_only else 'PS + PL  |  SOBEL + ROI + HDMI'
        d.text((12,28),label,font=self.small,fill=125)
        d.text((12,46),'01  SOURCE GRAYSCALE',font=self.font,fill=180)
        d.text((278,46),'02  '+('BINARY EDGES' if binary else 'SOBEL MAGNITUDE'),font=self.font,fill=180)
        # Pillow <=9 and newer releases both accept the numeric nearest constant.
        im.paste(Image.fromarray(gray).resize((256,256),0),(12,65))
        im.paste(Image.fromarray(edge if binary else magnitude).resize((256,256),0),(278,65))
        x0,y0,x1,y1=roi
        for ox in (12,278):
            d.rectangle((ox+2*x0,65+2*y0,ox+2*x1-1,65+2*y1-1),outline=150,width=1)
            cy=metrics['centroid_y']
            if cy is not None:
                yy=65+2*cy;d.line((ox+2*x0,yy,ox+2*x0+16,yy),fill=235,width=1)
        d.rectangle((545,46,629,321),outline=45)
        def text(y,value,fill=170):d.text((551,y),value,font=self.small,fill=fill)
        text(53,'ANALYSIS',205);text(72,'t %.2f s'%metrics['time_s'])
        text(87,'frame %d'%metrics['frame_index'])
        text(108,'T = %d'%metrics['threshold']);text(123,'edges %d'%metrics['roi_edge_count'])
        cy=metrics['centroid_y'];text(138,'y '+('--' if cy is None else '%.2f'%cy))
        est=metrics['frequency'];text(160,'FFT (Hz)',205)
        text(176,'%.3f'%est['frequency_hz'] if est['valid'] else 'collecting')
        text(191,'N = %d'%est['samples'])
        if est['bin_spacing_hz']:text(206,'df %.3f'%est['bin_spacing_hz'])
        text(227,'POSITION',205)
        _plot(d,(551,242,623,267),history[-128:])
        text(275,'SPECTRUM',205)
        if len(freq):
            n=sum(f<=5 for f in freq)
            _plot(d,(551,290,623,315),amplitude[:n],fill=160)
        d.text((12,330),'VIDEO: 30 FPS PLAYBACK  |  HDMI: 720p60  |  ROI centroid in pixels',font=self.small,fill=115)
        return np.asarray(im,dtype=np.uint8).copy()

def source_frames(path,roi=None,crop=None,max_frames=900):
    path=Path(path)
    if path.suffix.lower()=='.npz':
        with np.load(path,allow_pickle=False) as src:
            frames=src['frames'];fs=float(src['fps']);times=src['times_s']
            region=roi or tuple(map(int,src['roi']))
            if frames.dtype!=np.uint8 or frames.ndim!=3 or frames.shape[1:]!=(128,128):
                raise ValueError('NPZ frames must be uint8 [N,128,128]')
            if not fs>0 or not np.isfinite(fs) or len(times)!=len(frames) or not np.allclose(np.diff(times),1/fs,atol=1e-5):
                raise ValueError('Frequency analysis requires uniformly spaced finite timestamps')
            # Own arrays after the ZIP file is closed.
            frames=frames[:max_frames].copy()
        return fs,region,iter(frames),len(frames),'prepared grayscale frames'
    import cv2
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise ValueError('Cannot decode video file: '+path.name)
    fs=float(cap.get(cv2.CAP_PROP_FPS))
    total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not np.isfinite(fs) or fs<=0 or fs>240:
        cap.release();raise ValueError('Missing/unsupported video frame rate')
    def generate():
        previous_ms=None
        try:
            for i in range(max_frames):
                ok,bgr=cap.read()
                if not ok:break
                stamp=float(cap.get(cv2.CAP_PROP_POS_MSEC))
                if previous_ms is not None and stamp>0 and previous_ms>0 and abs((stamp-previous_ms)-1000/fs)>max(2,100/fs):
                    raise ValueError('Variable-frame-rate input: resample to CFR before frequency analysis')
                previous_ms=stamp
                if crop:
                    x,y,w,h=map(int,crop)
                    if min(x,y)<0 or min(w,h)<=0 or x+w>bgr.shape[1] or y+h>bgr.shape[0]:
                        raise ValueError('Crop exceeds video dimensions')
                    bgr=bgr[y:y+h,x:x+w]
                image=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
                if crop:image=cv2.resize(image,(128,128),interpolation=cv2.INTER_AREA)
                else:
                    hh,ww=image.shape;scale=min(128/ww,128/hh)
                    nh,nw=max(1,round(hh*scale)),max(1,round(ww*scale))
                    small=cv2.resize(image,(nw,nh),interpolation=cv2.INTER_AREA)
                    image=np.zeros((128,128),np.uint8);image[(128-nh)//2:(128-nh)//2+nh,(128-nw)//2:(128-nw)//2+nw]=small
                yield cv2.GaussianBlur(image,(3,3),0)
        finally:cap.release()
    return fs,roi or (1,1,127,127),generate(),min(max_frames,total) if total>0 else max_frames,'PS decode / grayscale / resize / Gaussian'
