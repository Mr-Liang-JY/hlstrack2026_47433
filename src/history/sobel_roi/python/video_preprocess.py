"""Optional PC/PS preprocessing. OpenCV is imported only when this is called."""
import numpy as np

def decode_frames(video, crop_xywh):
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError('Video mode needs ARM OpenCV. Use prepared_frames.npz mode with the same real video frames if cv2 is unavailable.') from exc
    capture=cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError('Cannot decode video: '+str(video))
    frames,times=[],[]
    fps=float(capture.get(cv2.CAP_PROP_FPS))
    x,y,w,h=[int(v) for v in crop_xywh]
    while True:
        ok,bgr=capture.read()
        if not ok:break
        if bgr.shape[:2]!=(1088,1920):
            raise ValueError('Crop is calibrated to the supplied video dimensions')
        gray=cv2.cvtColor(bgr[y:y+h,x:x+w],cv2.COLOR_BGR2GRAY)
        gray=cv2.resize(gray,(128,128),interpolation=cv2.INTER_AREA)
        frames.append(cv2.GaussianBlur(gray,(3,3),0,borderType=cv2.BORDER_REFLECT_101))
        times.append(capture.get(cv2.CAP_PROP_POS_MSEC)/1000)
    capture.release()
    frames,times=np.asarray(frames,dtype=np.uint8),np.asarray(times,dtype=float)
    if len(frames)<8 or not np.allclose(np.diff(times),1/fps,atol=1e-6):
        raise ValueError('Invalid or nonuniform video timeline')
    return frames,times,fps
