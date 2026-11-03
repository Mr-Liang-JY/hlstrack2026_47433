"""Compact images/ASCII/plots packet consumed by the native PL compositor."""
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
PACKET_BYTES=33792
PACKET_WORDS=8448
META=32768

def _text(packet,offset,text,length):
    data=str(text).upper().encode('ascii',errors='replace')[:length].ljust(length,b' ')
    packet[META+offset:META+offset+length]=np.frombuffer(data,np.uint8)

def make_packet(gray,processed,roi,metrics,history,freq,amplitude,reference_only=False):
    packet=np.zeros(PACKET_BYTES,np.uint8)
    for i,source in enumerate((gray,processed)):
        tile=np.array(source,dtype=np.uint8,copy=True)
        x0,y0,x1,y1=roi
        tile[y0,x0:x1]=150;tile[y1-1,x0:x1]=150;tile[y0:y1,x0]=150;tile[y0:y1,x1-1]=150
        cy=metrics.get('centroid_y')
        if cy is not None:tile[int(np.clip(round(cy),0,127)),x0:min(x0+5,x1)]=235
        packet[i*16384:(i+1)*16384]=tile.ravel()
    _text(packet,0,'FPGA MOTION SPECTRUM',64)
    _text(packet,64,'PC REFERENCE / PL NOT RUN' if reference_only else 'PS VIDEO / PL STREAM SOBEL + ROI / PS FFT / PL NATIVE HDMI',80)
    _text(packet,144,'01 SOURCE GRAYSCALE',32)
    _text(packet,176,metrics.get('processed_label','02 ADAPTIVE EDGES'),32)
    est=metrics['frequency'];f=est.get('frequency_hz')
    values=['ANALYSIS','T%5.2f S'%metrics['time_s'],'FRAME%5d'%metrics['frame_index'],
            'THR%7d'%metrics['threshold'],'EDGES%5d'%metrics['roi_edge_count'],
            'Y%9.2f'%metrics['centroid_y'] if metrics.get('centroid_y') is not None else 'Y MISSING',
            'FFT / HZ','%8.3f'%f if est.get('valid') else 'COLLECTING',
            'N%9d'%est.get('samples',0),'DF%8.3f'%est['bin_spacing_hz'] if est.get('bin_spacing_hz') else 'DF --',
            'FREQ ALERT' if metrics.get('alarm') else 'PERIODIC' if est.get('valid') else 'UNCERTAIN',metrics.get('policy','spectral'),
            '720P / 60','%2dFPS PLAY'%metrics.get('playback_fps',30)]
    for i,value in enumerate(values):_text(packet,208+10*i,value,10)
    _text(packet,348,'POSITION',16);_text(packet,364,'SPECTRUM',16)
    _text(packet,380,'NATIVE PL UI / 128X128 COMPUTE / 720P60 SIGNAL / %dFPS FILE PLAYBACK'%metrics.get('playback_fps',30),80)
    spans=np.full((128,2),255,np.uint8)
    v=history[-128:]
    if len(v)>1 and all(x is not None and np.isfinite(x) for x in v):
        a=np.interp(np.linspace(0,len(v)-1,128),np.arange(len(v)),np.asarray(v,float))
        height=np.rint(24*(a.max()-a)/max(float(np.ptp(a)),0.01)).astype(np.uint8)
        prior=np.r_[height[0],height[:-1]]
        spans[:,0]=np.minimum(prior,height);spans[:,1]=np.maximum(prior,height)
    packet[META+512:META+768]=spans.ravel()
    if len(freq)>1:
        sample=np.interp(np.linspace(0,5,128),freq,amplitude,left=0,right=0)
        heights=np.clip(np.rint(24*sample/max(float(np.max(sample)),1e-12)),0,24).astype(np.uint8)
        packet[META+768:META+896]=heights
    return packet.view('<u4')

def render_packet(words):
    """Independent vectorized pixel reference, used for tests/PC export only."""
    p=np.asarray(words,dtype='<u4').view(np.uint8)
    if p.size!=PACKET_BYTES:raise ValueError('Invalid native display packet')
    out=np.full((720,1280),10,np.uint8)
    out[94:661,1090]=45;out[94:661,1260]=45;out[94,1090:1261]=45;out[660,1090:1261]=45
    for k,x in enumerate((24,556)):
        tile=p[k*16384:(k+1)*16384].reshape(128,128)
        out[130:642,x:x+512]=tile.repeat(4,0).repeat(4,1)
    font=np.load(ROOT/'data/font_bitmap.npy')
    def line(offset,n,x,y,width,color):
        codes=p[META+offset:META+offset+n]&127
        rows=font[codes,:12]
        bitmap=np.unpackbits(rows[:,:,None],axis=2).transpose(1,0,2).reshape(12,n*8)
        bitmap=bitmap.repeat(2,0).repeat(2,1)[:,:width]
        out[y:y+24,x:x+width]=np.where(bitmap,color,10)
    line(0,64,24,12,1024,205);line(64,78,24,55,1248,135)
    line(144,32,24,94,512,180);line(176,32,556,94,512,180)
    for i in range(14):line(208+10*i,10,1092,104+i*32,160,185)
    line(348,10,1092,550,160,150);out[550:552,1092:1252]=10
    line(364,10,1092,606,160,150);line(380,78,24,680,1248,115)
    spans=p[META+512:META+768].reshape(128,2)
    yy=np.arange(25)[:,None]
    on=(spans[None,:,0]!=255)&(yy>=spans[None,:,0])&(yy<=spans[None,:,1])
    out[578:603,1102:1230]=np.where(on,185,10)
    h=p[META+768:META+896]
    on=(h[None,:]!=255)&(h[None,:]!=0)&(yy>=24-h.astype(int)[None,:])
    out[634:659,1102:1230]=np.where(on,165,10)
    return out

class NativeComposer:
    def render(self,gray,magnitude,edge,roi,metrics,history,freq,amplitude,binary=True,reference_only=False):
        label='02 SOBEL MAGNITUDE' if not binary else '02 FIXED EDGES' if metrics.get('policy')=='fixed' else '02 ADAPTIVE EDGES'
        return make_packet(gray,edge if binary else magnitude,roi,dict(metrics,processed_label=label),history,freq,amplitude,reference_only)
