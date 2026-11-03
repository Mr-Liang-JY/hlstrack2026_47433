"""PC only: decode public spring-mass video into the exact grayscale board input."""
from pathlib import Path
import argparse
import json
import sys
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
# Convenience for THIS PC only; the delivered package does not depend on day8.
local_vendor = ROOT.parent/'day8/vendor'
if local_vendor.is_dir():
    sys.path.insert(0, str(local_vendor))
import cv2
import numpy as np
from shm_common import sha256, sobel_reference, roi_stats, save_analysis, write_csv

SOURCE_PAGE = 'https://www.sg.iwant2study.org/ospsg/index.php/interactive-resources/physics/02-newtonian-mechanics/09-oscillations/225-tracker-modeling-in-spring-mass-system'
SOURCE_VIDEO = 'https://iwant2study.org/lookangejss/02_newtonianmechanics_8oscillations/trz/springmass/videos/Spring%20and%20mass.mp4'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    video = ROOT/'inputs/spring_mass.mp4'
    if args.download or not video.exists():
        if video.exists():
            raise FileExistsError('Existing video preserved. Rename it yourself before re-downloading.')
        urllib.request.urlretrieve(SOURCE_VIDEO, str(video))
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError('Cannot decode source video')
    fs = float(capture.get(cv2.CAP_PROP_FPS))
    frames, times, body_positions = [], [], []
    crop = [820, 420, 240, 440]
    roi = [1, 22, 127, 126]  # x0,y0,x1,y1; exclusive right/bottom
    x, y, w, h = crop
    while True:
        ok, bgr = capture.read()
        if not ok:
            break
        if bgr.shape[:2] != (1088, 1920):
            raise ValueError('Default crop is for the supplied 1920x1088 video only')
        times.append(capture.get(cv2.CAP_PROP_POS_MSEC)/1000)
        gray = cv2.cvtColor(bgr[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)
        # Independent body detector for a frequency cross-check, not PL input replacement.
        row_count = (gray < 100).sum(axis=1)
        candidates = np.flatnonzero(row_count > 45)
        body_positions.append(float(candidates.mean()) if len(candidates) else np.nan)
        resized = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        frames.append(cv2.GaussianBlur(resized, (3, 3), 0, borderType=cv2.BORDER_REFLECT_101))
    capture.release()
    frames, times = np.asarray(frames, dtype=np.uint8), np.asarray(times)
    if len(frames) < 100 or not np.allclose(np.diff(times), 1/fs, atol=1e-6):
        raise ValueError('Too short or non-uniform timestamps; do not silently impose FPS')
    target = ROOT/'inputs/prepared_frames.npz'
    np.savez_compressed(str(target), frames=frames, times_s=times,
                        fps=np.array(fs), roi=np.asarray(roi, dtype=np.uint32))
    source = {'page_url': SOURCE_PAGE, 'video_url': SOURCE_VIDEO,
              'video_sha256': sha256(video), 'prepared_sha256': sha256(target),
              'publisher': 'Open Educational Resources / Open Source Physics @ Singapore',
              'license': 'CC BY-SA 4.0 as declared in the source page footer',
              'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/',
              'modifications': 'crop, resize 128x128, grayscale, Gaussian 3x3; derived frames kept under CC BY-SA 4.0',
              'crop_xywh': crop, 'roi_xyxy': roi, 'frame_count': len(frames),
              'fps_container_hz': fs, 'max_timestamp_error_s': float(np.max(np.abs(np.diff(times)-1/fs))),
              'clock_note': 'Video metadata/timestamps, no independent camera-clock calibration',
              'boundary_policy': 'Sobel output outer one-pixel border is ZERO, unlike day8 reflect border'}
    (ROOT/'inputs/source.json').write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = []
    previous = None
    for index, frame in enumerate(frames):
        edge = sobel_reference(frame, 80)
        count, ysum = roi_stats(edge, roi)
        x0, y0, x1, y1 = roi
        mad = None if previous is None else float(np.abs(frame[y0:y1, x0:x1].astype(np.int16)-previous[y0:y1, x0:x1].astype(np.int16)).mean())
        rows.append({'frame_index': index, 'time_s': float(times[index]), 'threshold': 80,
                     'roi_edge_count': count, 'roi_edge_y_sum': ysum,
                     'centroid_y': ysum/count if count else None, 'motion_mad': mad,
                     'pixel_mismatches': 0, 'roi_stat_mismatches': 0})
        if index in (0, len(frames)//2, len(frames)-1):
            cv2.imwrite(str(ROOT/'reference'/('frame_%03d_gray.png'%index)), frame)
            cv2.imwrite(str(ROOT/'reference'/('frame_%03d_edge.png'%index)), edge)
        previous = frame
    summary = save_analysis(ROOT/'reference', rows, fs, source, 'NOT_RUN: PC reference only')
    from shm_common import harmonic_fit
    body_fit, _ = harmonic_fit(times, body_positions, fs)
    summary['independent_dark_body_fit'] = body_fit
    (ROOT/'reference/summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv(ROOT/'reference/independent_body_position.csv',
              [{'frame_index': i, 'time_s': float(t), 'body_mask_y_pixels': float(v)} for i,(t,v) in enumerate(zip(times,body_positions))])
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('PREPARE VIDEO PASSED:', target)

if __name__ == '__main__':
    main()
