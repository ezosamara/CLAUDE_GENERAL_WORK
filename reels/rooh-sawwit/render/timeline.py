#!/usr/bin/env python3
"""Build render/timeline.json from script/scripts.json (+ vo/timing.json when Polly has run).
Without real VO, word marks are estimated evenly across est_dur so the whole montage can be previewed."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "script/scripts.json").read_text(encoding="utf-8"))
tp = ROOT / "vo/timing.json"
timing = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else {}
GAP = 0.25  # breath between segments

def words_for(seg_id, display, est):
    if seg_id in timing:
        return timing[seg_id]["dur"], timing[seg_id]["words"]
    ws = display.split()
    n = max(len(ws), 1)
    return est, [{"t": round(i * est / n * 0.9, 3), "value": w} for i, w in enumerate(ws)]

# ---- reel 1
t = 0.0
scenes = []
for s in d["reel1"]["segments"]:
    if s["vo"] is None:
        scenes.append({"id": s["id"], "scene": s["scene"], "display": s["display"], "start": t, "end": t + s["est_dur"], "words": []})
        t += s["est_dur"]
        continue
    dur, words = words_for(s["id"], s["vo"], s["est_dur"])
    lead = 0.35 if s["scene"] != "black" else 0.6
    sc = {"id": s["id"], "scene": s["scene"], "display": s["display"], "start": t, "vo_start": t + lead,
          "end": t + lead + dur + GAP, "words": [{"t": t + lead + w["t"], "value": w["value"]} for w in words]}
    for k in ("sign", "cta"):
        if k in s: sc[k] = s[k]
    scenes.append(sc)
    t = sc["end"]
reel1 = {"scenes": scenes, "duration": round(t + 0.8, 3)}

# ---- reel 2
ticks = []
for i, tk in enumerate(d["reel2"]["ticks"]):
    tid = f"r2_tick{i+1}"
    dur = timing[tid]["dur"] if tid in timing else 0.9
    ticks.append({"at": tk["at"], "display": tk["display"], "vo_id": tid, "vo_dur": dur})
clock_end = 12.0
f = d["reel2"]["final"]
fdur, fwords = words_for("r2_final", f["vo"], f["est_dur"])
final_start = clock_end + 0.9
reel2 = {"ticks": ticks, "clock_end": clock_end, "final_start": final_start,
         "final": {"display_1": f["display_1"], "display_2": f["display_2"], "cta": f["cta"], "vo_dur": fdur,
                   "words": [{"t": final_start + w["t"], "value": w["value"]} for w in fwords]},
         "duration": round(final_start + fdur + 1.2, 3)}
out = {"reel1": reel1, "reel2": reel2, "vo_real": bool(timing)}
(ROOT / "render/timeline.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("reel1 %.2fs, reel2 %.2fs, real VO: %s" % (reel1["duration"], reel2["duration"], bool(timing)))
