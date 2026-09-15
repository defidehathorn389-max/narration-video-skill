# -*- coding: utf-8 -*-
"""把 10 段 TTS 拼接成完整旁白音轨（段间插入停顿，首尾留白）。"""
import glob
import os
import wave

import imageio_ffmpeg

from script import LEAD, GAP, TAIL, SEGMENTS

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(os.path.dirname(HERE), "audio")
OUT = os.path.join(HERE, "narration.wav")
FF = imageio_ffmpeg.get_ffmpeg_exe()


def mp3_to_wav(src: str, dst: str) -> None:
    import subprocess
    subprocess.run([FF, "-y", "-v", "error", "-i", src, "-ar", "44100", "-ac", "2",
                    "-c:a", "pcm_s16le", dst], check=True)


def main():
    segs = sorted(glob.glob(os.path.join(AUDIO, "seg*.mp3")))
    assert len(segs) == len(SEGMENTS), "分段数量与音频文件数量不一致"

    params = None
    chunks = []
    for f in segs:
        w = f[:-4] + ".wav"
        if not os.path.exists(w):
            mp3_to_wav(f, w)
        with wave.open(w, "rb") as wf:
            if params is None:
                params = wf.getparams()
            chunks.append(wf.readframes(wf.getnframes()))
        print("%s  %.2fs" % (os.path.basename(f), os.path.getsize(w) / (params.framerate * params.sampwidth * params.nchannels)))

    silent = b"\x00" * (params.sampwidth * params.nchannels)
    lead = silent * int(params.framerate * LEAD)
    gap = silent * int(params.framerate * GAP)
    tail = silent * int(params.framerate * TAIL)

    body = []
    for i, c in enumerate(chunks):
        body.append(c)
        body.append(gap)
    data = lead + b"".join(body) + tail

    with wave.open(OUT, "wb") as out:
        out.setnchannels(params.nchannels)
        out.setsampwidth(params.sampwidth)
        out.setframerate(params.framerate)
        out.writeframes(data)

    dur = len(data) / (params.framerate * params.sampwidth * params.nchannels)
    print("\n音轨: %s\n时长 %.2fs（%.1f 分钟）  %dHz %dch"
          % (OUT, dur, dur / 60, params.framerate, params.nchannels))


if __name__ == "__main__":
    main()
