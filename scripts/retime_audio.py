"""Pitch-preserving speech retiming before timeline construction.

Example:
  python retime_audio.py --input audio/voice02_raw --output audio/voice02_speed125 \
    --speed 1.25 --narration narration_voice02_speed125.mp3 --report timing_voice02_speed125.json

Raw files are never modified. Segment times are measured by decoding the actual
output MP3s. The report is input for the project's timeline, NOT forced alignment.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def ffmpeg_path():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        p = shutil.which('ffmpeg')
        if not p:
            raise RuntimeError('Install imageio-ffmpeg or provide ffmpeg on PATH')
        return p


def pcm(ff, path):
    return subprocess.check_output([ff, '-v', 'error', '-i', str(path),
                                    '-f', 's16le', '-ac', '1', '-ar', '24000', '-'])


def run(input_dir, output_dir, speed, narration, report, lead=1.6, gap=.34, tail=2.2):
    src, dst = Path(input_dir).resolve(), Path(output_dir).resolve()
    if src == dst or dst in src.parents:
        raise ValueError('Input and output must be separate; preserve originals')
    if not .5 <= speed <= 2:
        raise ValueError('This helper supports speed 0.5 through 2.0')
    files = sorted(src.glob('seg*.mp3'))
    if not files:
        raise ValueError('No seg*.mp3 input files')
    dst.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_path()
    speech = bytearray(b'\0' * (round(lead * 24000) * 2))
    rows = []
    for f in files:
        raw = pcm(ff, f)
        out = dst / f.name
        tmp = out.with_name(out.stem + '.partial.mp3')
        subprocess.run([ff, '-y', '-v', 'error', '-i', str(f), '-af', f'atempo={speed}',
                        '-ac', '1', '-ar', '24000', '-b:a', '128k', str(tmp)], check=True)
        decoded = pcm(ff, tmp)
        if not decoded:
            raise RuntimeError('Empty retimed audio: ' + str(f))
        tmp.replace(out)
        rows.append({'filename': f.name, 'raw_duration': len(raw) / 48000,
                     'duration': len(decoded) / 48000, 'speed': speed})
        speech.extend(decoded)
        # Keep the historical pipeline's GAP after every segment, including last.
        speech.extend(b'\0' * (round(gap * 24000) * 2))
        print(f'{f.name}: {rows[-1]["raw_duration"]:.3f}s -> {rows[-1]["duration"]:.3f}s', flush=True)
    speech.extend(b'\0' * (round(tail * 24000) * 2))
    output = Path(narration)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.stem + '.partial.mp3')
    subprocess.run([ff, '-y', '-v', 'error', '-f', 's16le', '-ac', '1', '-ar', '24000',
                    '-i', '-', '-af', 'loudnorm=I=-20:TP=-3:LRA=11',
                    '-b:a', '128k', str(temp)], input=speech, check=True)
    measured = len(pcm(ff, temp)) / 48000
    expected = len(speech) / 48000
    if abs(measured - expected) > .1:
        raise RuntimeError(f'Unexpected output duration: {measured} vs {expected}')
    temp.replace(output)
    result = {'speed': speed, 'lead': lead, 'gap': gap, 'gap_after_last': True,
              'tail': tail, 'segments': rows, 'timeline_duration': expected,
              'measured_narration_duration': measured,
              'subtitle_alignment': 'segment durations only; not forced alignment'}
    Path(report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--speed', type=float, default=1.25)
    p.add_argument('--narration', required=True)
    p.add_argument('--report', required=True)
    a = p.parse_args()
    run(a.input, a.output, a.speed, a.narration, a.report)
