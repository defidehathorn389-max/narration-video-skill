"""Validate a rendered MP4. Does not claim to validate logic, listening quality or style."""
import argparse
import json
import re
import subprocess
from pathlib import Path
import cv2
import imageio_ffmpeg

parser = argparse.ArgumentParser()
parser.add_argument('video', type=Path)
parser.add_argument('--expected-seconds', type=float)
parser.add_argument('--tolerance', type=float, default=3)
parser.add_argument('--full-hd', action='store_true')
args = parser.parse_args()
if not args.video.is_file():
    raise SystemExit('Missing video: '+str(args.video))
cap = cv2.VideoCapture(str(args.video))
if not cap.isOpened():
    raise SystemExit('Video could not be opened')
width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
cap.release()
if fps <= 0:
    raise SystemExit('Invalid FPS')
duration = count/fps
errors = []
if abs(width/height-16/9) > .001:
    errors.append('Not 16:9')
if args.full_hd and (width, height) != (1920, 1080):
    errors.append('Not 1920x1080')
if args.full_hd and abs(fps-30) > .1:
    errors.append('Not 30 fps')
if args.expected_seconds is not None and abs(duration-args.expected_seconds) > args.tolerance:
    errors.append('Duration is outside the requested tolerance')
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
probe = subprocess.run([ffmpeg, '-hide_banner', '-i', str(args.video)], capture_output=True, text=True)
# The no-output probe intentionally returns nonzero; inspect its stream descriptions.
info = probe.stderr
for pattern, label in [(r'Video:\s*h264', 'H.264 video'), (r'yuv420p', 'yuv420p'), (r'Audio:\s*aac', 'AAC audio')]:
    if not re.search(pattern, info, flags=re.I):
        errors.append('Missing expected '+label)
full = subprocess.run([ffmpeg, '-v', 'error', '-i', str(args.video), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'], capture_output=True, text=True)
if full.returncode or full.stderr.strip():
    errors.append('Decode failed or reported errors: '+full.stderr.strip())
# Read top-level MP4 atom headers to verify moov occurs before mdat.
atoms = []
with args.video.open('rb') as f:
    length = args.video.stat().st_size
    while f.tell()+8 <= length:
        start = f.tell(); header = f.read(8)
        size = int.from_bytes(header[:4], 'big'); kind = header[4:].decode('ascii', 'replace')
        header_size = 8
        if size == 1:
            extra = f.read(8)
            if len(extra) != 8: break
            size = int.from_bytes(extra, 'big'); header_size = 16
        elif size == 0: size = length-start
        if size < header_size or start+size > length: break
        atoms.append(kind); f.seek(start+size)
if 'moov' not in atoms or 'mdat' not in atoms or atoms.index('moov') > atoms.index('mdat'):
    errors.append('Could not confirm faststart atom order')
report = {'file': str(args.video), 'width': width, 'height': height, 'fps': fps,
          'duration_seconds': round(duration, 3), 'bytes': args.video.stat().st_size,
          'full_decode_ok': full.returncode == 0, 'errors': errors}
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(1 if errors else 0)
