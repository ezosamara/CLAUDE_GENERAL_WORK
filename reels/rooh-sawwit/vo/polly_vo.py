#!/usr/bin/env python3
"""Amazon Polly voice-over pipeline for روح صوّت reels.

Usage:
  python3 vo/polly_vo.py --dry-run          # validate SSML, print requests, no AWS call
  python3 vo/polly_vo.py                    # synthesize every segment + word speech marks
  python3 vo/polly_vo.py --voice Hala       # switch voice (Zayd = male neural, Hala = female neural)

Needs AWS credentials with polly:SynthesizeSpeech (and polly:DescribeVoices for --list-voices).
Outputs: vo/out/<segment>.wav (48 kHz mono) and vo/timing.json (durations + word marks).
"""
import argparse, json, os, subprocess, sys, xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "script" / "scripts.json"
OUT = ROOT / "vo" / "out"
TIMING = ROOT / "vo" / "timing.json"


def segments():
    d = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    segs = []
    for s in d["reel1"]["segments"]:
        if s.get("vo"):
            segs.append({"id": s["id"], "ssml": s["ssml"], "text": s["vo"]})
    for i, t in enumerate(d["reel2"]["ticks"]):
        segs.append({"id": f"r2_tick{i+1}", "ssml": f"<speak><prosody rate=\"85%\">{t['vo']}</prosody></speak>", "text": t["vo"]})
    segs.append({"id": "r2_final", "ssml": d["reel2"]["final"]["ssml"], "text": d["reel2"]["final"]["vo"]})
    return segs


def validate(ssml):
    xml.dom.minidom.parseString(ssml.encode("utf-8"))  # raises on malformed SSML
    for bad in ("ـ",):  # kashida breaks Polly's Arabic tokenizer
        if bad in ssml:
            raise ValueError("kashida found in SSML")


def synth(polly, seg, voice, engine, lang):
    common = dict(Engine=engine, VoiceId=voice, LanguageCode=lang, TextType="ssml", Text=seg["ssml"])
    audio = polly.synthesize_speech(OutputFormat="mp3", SampleRate="24000", **common)["AudioStream"].read()
    mp3 = OUT / f"{seg['id']}.mp3"
    mp3.write_bytes(audio)
    wav = OUT / f"{seg['id']}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "48000", "-ac", "1",
                    "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse,apad=pad_dur=0.05",
                    str(wav)], check=True)
    marks_raw = polly.synthesize_speech(OutputFormat="json", SpeechMarkTypes=["word"], **common)["AudioStream"].read().decode("utf-8")
    words = [json.loads(l) for l in marks_raw.splitlines() if l.strip()]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                               capture_output=True, text=True).stdout.strip() or 0) if shutil_which("ffprobe") else wav_duration(wav)
    return {"dur": round(dur, 3), "words": [{"t": w["time"] / 1000.0, "value": w["value"]} for w in words]}


def shutil_which(x):
    import shutil
    return shutil.which(x)


def wav_duration(path):
    import wave
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--voice", default="Zayd")
    ap.add_argument("--engine", default="neural")
    ap.add_argument("--lang", default="ar-AE")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    ap.add_argument("--list-voices", action="store_true")
    a = ap.parse_args()
    segs = segments()
    for s in segs:
        validate(s["ssml"])
    print(f"{len(segs)} segments, SSML valid.")
    if a.dry_run:
        for s in segs:
            print(f"  {s['id']:10s} {s['text']}")
        return
    import boto3
    polly = boto3.client("polly", region_name=a.region)
    if a.list_voices:
        for v in polly.describe_voices()["Voices"]:
            if v["LanguageCode"].startswith("ar"):
                print(v["Id"], v["Gender"], v["LanguageCode"], v["SupportedEngines"])
        return
    OUT.mkdir(parents=True, exist_ok=True)
    timing = {}
    for s in segs:
        timing[s["id"]] = synth(polly, s, a.voice, a.engine, a.lang)
        print(f"  {s['id']:10s} {timing[s['id']]['dur']:.2f}s  {len(timing[s['id']]['words'])} words")
    timing["_voice"] = {"voiceId": a.voice, "engine": a.engine, "languageCode": a.lang}
    TIMING.write_text(json.dumps(timing, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", TIMING)


if __name__ == "__main__":
    main()
