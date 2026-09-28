#!/usr/bin/env python3
"""Final assembly: video (from render.mjs) + music bed + Polly VO (when vo/out exists) -> loudness-normalised MP4s.
usage: python3 render/build.py reel1|reel2 [--w 1080 --h 1920]
Mix rules: VO on top, bed ducked -9 dB under speech (sidechain), master to -14 LUFS / -1 dBTP (Instagram/TikTok)."""
import argparse, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(); ap.add_argument("reel"); ap.add_argument("--w", type=int, default=1080); ap.add_argument("--h", type=int, default=1920)
a = ap.parse_args()
tl = json.loads((ROOT / "render/timeline.json").read_text(encoding="utf-8"))
T = tl[a.reel]; dur = T["duration"]
video = ROOT / f"out/{a.reel}_{a.w}x{a.h}_video.mp4"; bed = ROOT / f"audio/out/{a.reel}_bed.wav"
assert video.exists(), f"render first: node render/render.mjs {a.reel} --w {a.w} --h {a.h}"
vo_dir = ROOT / "vo/out"
# VO cue list: (start_time, wav)
cues = []
if a.reel == "reel1":
    for sc in T["scenes"]:
        if "vo_start" in sc and (vo_dir / f"{sc['id']}.wav").exists(): cues.append((sc["vo_start"], vo_dir / f"{sc['id']}.wav"))
else:
    for tk in T["ticks"]:
        if (vo_dir / f"{tk['vo_id']}.wav").exists(): cues.append((tk["at"] + 0.12, vo_dir / f"{tk['vo_id']}.wav"))
    if (vo_dir / "r2_final.wav").exists(): cues.append((T["final_start"], vo_dir / "r2_final.wav"))
inputs = ["-i", str(video), "-i", str(bed)]
fc = []
for i, (t, w) in enumerate(cues):
    inputs += ["-i", str(w)]; fc.append(f"[{i+2}:a]adelay={int(t*1000)}|{int(t*1000)},aformat=channel_layouts=stereo[v{i}]")
if cues:
    fc.append("".join(f"[v{i}]" for i in range(len(cues))) + f"amix=inputs={len(cues)}:normalize=0,alimiter=limit=0.95[vo]")
    fc.append("[vo]asplit=2[vo1][vo2]")
    fc.append("[1:a][vo2]sidechaincompress=threshold=0.02:ratio=6:attack=8:release=350:makeup=1[bedd]")
    fc.append("[bedd][vo1]amix=inputs=2:normalize=0:weights=0.55 1.0[mix]")
    vo_note = f"{len(cues)} VO segments"
else:
    fc.append("[1:a]volume=0.75[mix]"); vo_note = "NO VO (Polly not run yet) — music bed only"
fc.append(f"[mix]atrim=0:{dur},loudnorm=I=-14:TP=-1.5:LRA=9,alimiter=limit=0.7:attack=3:release=80:level=false[aout]")
suffix = "9x16" if a.h > a.w * 1.4 else "4x5"
out = ROOT / f"out/{a.reel}_{suffix}.mp4"
cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[aout]",
       "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", str(dur), "-movflags", "+faststart", str(out)]
subprocess.run(cmd, check=True)
print(f"{out.name}: {dur:.2f}s, {vo_note}")
# 720p preview for the review page (small enough to stream on a phone)
prev = ROOT / "out/preview"; prev.mkdir(exist_ok=True)
pw = 720; ph = round(a.h * 720 / a.w / 2) * 2
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-vf", f"scale={pw}:{ph}", "-c:v", "libx264", "-preset", "medium", "-crf", "25",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(prev / out.name)], check=True)
print("preview ->", prev / out.name)
