"""PS video decoding; GStreamer crops/scales YUV before grayscale conversion."""
from pathlib import Path
import os
import numpy as np

def source_frames(path,roi=None,crop=None,max_frames=900,decoder='auto'):
    path=Path(path)
    if path.suffix.lower()=='.npz':
        with np.load(path,allow_pickle=False) as data:
            frames=data['frames'];fs=float(data['fps']);times=data['times_s'];region=roi or tuple(map(int,data['roi']))
            if frames.dtype!=np.uint8 or frames.ndim!=3 or frames.shape[1:]!=(128,128):raise ValueError('Invalid prepared frames')
            if not np.isfinite(fs) or fs<=0 or len(times)!=len(frames) or not np.allclose(np.diff(times),1/fs,atol=1e-5):raise ValueError('Nonuniform timestamps')
            frames=frames[:max_frames].copy()
        return fs,region,iter(frames),len(frames),'prepared grayscale frames; no raw-video decoding'
    plugins=Path(__file__).resolve().parents[1]/'data/optional_decoder/usr/lib/arm-linux-gnueabihf/gstreamer-1.0'
    if os.name=='posix' and (plugins/'libgstlibav.so').is_file():
        os.environ['GST_PLUGIN_PATH']=str(plugins)+os.pathsep+os.environ.get('GST_PLUGIN_PATH','')
        os.environ.setdefault('GST_REGISTRY',str(plugins.parents[4]/'gst_registry_ready.bin'))
    import cv2
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise ValueError('Cannot open video: '+path.name)
    fs=float(cap.get(cv2.CAP_PROP_FPS));total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not np.isfinite(fs) or not 0<fs<=240:cap.release();raise ValueError('Unsupported source FPS')
    if crop:
        x,y,w,h=map(int,crop)
        if min(x,y)<0 or min(w,h)<=0 or x+w>width or y+h>height:cap.release();raise ValueError('Crop exceeds source dimensions')
    native=False
    if crop and decoder in ('auto','gstreamer') and 'GStreamer:                   YES' in cv2.getBuildInformation():
        # URI escaping prevents filenames from introducing pipeline elements.
        pipeline=('uridecodebin uri="'+path.resolve().as_uri()+'" ! videocrop left=%d right=%d top=%d bottom=%d '%(x,width-x-w,y,height-y-h)+
                  '! videoscale ! video/x-raw,width=128,height=128 ! videoconvert ! video/x-raw,format=GRAY8 '
                  '! appsink sync=false max-buffers=2 drop=false')
        candidate=cv2.VideoCapture(pipeline,cv2.CAP_GSTREAMER)
        if candidate.isOpened():cap.release();cap=candidate;native=True
        else:
            candidate.release()
            if decoder=='gstreamer':cap.release();raise RuntimeError('Requested GStreamer decoder unavailable')
    elif decoder=='gstreamer':cap.release();raise RuntimeError('GStreamer crop path not supported')
    def frames():
        previous_ms=None
        try:
            for i in range(max_frames):
                ok,frame=cap.read()
                if not ok:break
                stamp=float(cap.get(cv2.CAP_PROP_POS_MSEC))
                if previous_ms is not None and np.isfinite(stamp) and stamp>0 and previous_ms>0 and abs(stamp-previous_ms-1000/fs)>max(2,100/fs):
                    raise ValueError('Nonuniform source timestamps')
                previous_ms=stamp
                if native:
                    if frame.ndim!=2 or frame.shape!=(128,128):raise ValueError('Unexpected GStreamer pixel format')
                    image=frame
                else:
                    if crop:frame=frame[y:y+h,x:x+w]
                    image=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
                    if crop:image=cv2.resize(image,(128,128),interpolation=cv2.INTER_AREA)
                    else:
                        hh,ww=image.shape;scale=min(128/ww,128/hh);nh,nw=max(1,round(hh*scale)),max(1,round(ww*scale))
                        small=cv2.resize(image,(nw,nh),interpolation=cv2.INTER_AREA)
                        image=np.zeros((128,128),np.uint8);image[(128-nh)//2:(128-nh)//2+nh,(128-nw)//2:(128-nw)//2+nw]=small
                yield cv2.GaussianBlur(image,(3,3),0)
        finally:cap.release()
    label='PS GStreamer decode / crop-YUV / scale / gray / Gaussian' if native else 'PS OpenCV decode / crop / gray / scale / Gaussian'
    return fs,roi or (1,1,127,127),frames(),min(max_frames,total) if total>0 else max_frames,label
