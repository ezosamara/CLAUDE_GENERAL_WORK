# روح صوّت — Reels v3 (Levantine, AWS Polly pipeline)

Non-partisan turnout campaign, Knesset election 27/10/2026. Two reels, rebuilt end-to-end:
Levantine scripts, original procedural score + bold clock SFX, HTML/Playwright motion renderer,
and an Amazon Polly voice-over pipeline with word-level speech marks driving the kinetic type.

## Layout
| Path | What |
|---|---|
| `script/scripts.json` | v3 scripts: display text (unvocalized, for screen) + fully vocalized VO + SSML per segment, captions |
| `vo/polly_vo.py` | Polly synthesis (Zayd neural ar-AE) + word speech marks → `vo/out/*.wav`, `vo/timing.json` |
| `render/timeline.py` | Builds `render/timeline.json` from scripts (+ real VO timing when present) |
| `audio/compose.py` | Original score + SFX from the timeline → `audio/out/*_bed.wav` (no samples, no rights) |
| `render/reel1.html`, `render/reel2.html` | Deterministic `seek(t)` scenes, 1080×1920 (and 1080×1350 feed) |
| `render/render.mjs` | Headless Chromium frame renderer → `out/*_video.mp4` (grain added in ffmpeg) |
| `render/build.py` | Mix bed + VO (sidechain duck) → −14 LUFS → `out/reel1_9x16.mp4`, `out/reel2_9x16.mp4`, `out/reel1_4x5.mp4` |
| `assets/plates/` | Background plates (cleaned from the v2 renders, text inpainted, bottom darkened) |

## Full pipeline (run in this order)
```bash
pip install boto3 numpy scipy pillow opencv-python-headless playwright
python3 vo/polly_vo.py --dry-run        # validates SSML, no AWS call
python3 vo/polly_vo.py                  # needs AWS creds with polly:SynthesizeSpeech
python3 render/timeline.py              # picks up vo/timing.json automatically
python3 audio/compose.py                # hits re-align to the real word marks
node render/render.mjs reel1 && python3 render/build.py reel1
node render/render.mjs reel2 && python3 render/build.py reel2
node render/render.mjs reel1 --w 1080 --h 1350 && python3 render/build.py reel1 --w 1080 --h 1350
```
Without `vo/timing.json` the same commands produce **preview** renders with estimated word timing and music only.

## Arabic VO on Polly — what makes it read correctly
1. **Vocalize everything.** Polly runs a built-in MSA diacritizer on unvocalized text; on dialect words it guesses wrong
   (e.g. reads بيصير as MSA). Every VO line here carries fatha/damma/kasra, sukun on closed syllables and shadda.
2. **Numbers as words.** "27/10" → سَبْعَة وْعِشْرينْ عَشَرَة; "12" → اثْنَعْشْ. Digits get read in MSA otherwise.
3. **SSML for rhythm, not text punctuation.** `<break time>` between beats, `<prosody rate="88–92%">` for weight,
   the CTA at `volume="loud"`. Neural voices ignore `pitch`, so contrast comes from rate + breaks.
4. **Speech marks = captions.** `SpeechMarkTypes=["word"]` returns each word's start ms; the renderer lights each word on its mark.
5. **Voice choice (AWS only).** Arabic voices are Zeina (standard, MSA), Hala (neural, Gulf, F) and Zayd (neural, Gulf, M).
   No generative Arabic voice exists. Zayd reads vocalized Levantine phonetically with a Gulf timbre — accept the accent or
   record a human Palestinian VO with these timings.
6. **Verify.** Run each segment through an ASR (Whisper) and compare against the display text; fix stubborn words with
   `<phoneme alphabet="ipa">` (Arabic phoneme table exists for these voices) before re-rendering.
7. **Never** use kashida (ـ), Arabic-Indic digits mixed with Latin, or Fusha connectors (سوف، لن، الذي) in a dialect read.

## Status
- AWS credentials present in this environment are not valid AWS keys (rejected by STS; wrong format). The Polly step
  has not run; renders in `out/` are previews with the score only. Everything else is final.
