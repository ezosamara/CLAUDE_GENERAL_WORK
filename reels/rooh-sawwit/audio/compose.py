#!/usr/bin/env python3
"""Original procedural score + SFX for both reels (no samples, no rights issues).
Reads render/timeline.json so every hit lands on the real cue (re-run after Polly timing exists).
Writes audio/out/reel1_bed.wav and audio/out/reel2_bed.wav (48 kHz stereo, peaks ~ -3 dBFS)."""
import json, numpy as np
from pathlib import Path
from scipy import signal as sg

SR = 48000
ROOT = Path(__file__).resolve().parent.parent
TL = json.loads((ROOT / "render/timeline.json").read_text(encoding="utf-8"))
OUT = ROOT / "audio/out"; OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)

def n(sec): return int(sec * SR)
def tt(N): return np.arange(N) / SR
def sine(f, N, ph=0.0):
    f = np.broadcast_to(f, N) if np.ndim(f) else np.full(N, float(f))
    return np.sin(2 * np.pi * np.cumsum(f) / SR + ph)
def saw(f, N, det=0.0):
    ph = np.cumsum(np.full(N, f * (1 + det))) / SR
    return 2 * (ph % 1.0) - 1
def lp(x, fc, order=2):
    fc = np.clip(fc, 20, SR / 2 - 100)
    return sg.sosfilt(sg.butter(order, fc, 'low', fs=SR, output='sos'), x)
def hp(x, fc, order=2): return sg.sosfilt(sg.butter(order, fc, 'high', fs=SR, output='sos'), x)
def bp(x, lo, hi, order=2): return sg.sosfilt(sg.butter(order, [lo, hi], 'band', fs=SR, output='sos'), x)
def sweep_lp(x, fc_from, fc_to, steps=48):
    """time-varying low-pass by crossfading chunks (cheap, click-free enough for pads)."""
    N = len(x); out = np.zeros(N); edges = np.linspace(0, N, steps + 1).astype(int)
    for i in range(steps):
        fc = fc_from + (fc_to - fc_from) * (i / max(steps - 1, 1)) ** 2
        seg = lp(x[max(0, edges[i] - 2000):edges[i + 1]], fc)
        out[edges[i]:edges[i + 1]] = seg[-(edges[i + 1] - edges[i]):]
    return out
def decay(N, tau, start=1.0): return start * np.exp(-tt(N) / tau)
def ar(N, a, r):  # attack/release linear-ish envelope
    e = np.ones(N); A = min(n(a), N); R = min(n(r), N)
    e[:A] = np.linspace(0, 1, A) ** 2
    if R: e[-R:] *= np.linspace(1, 0, R) ** 1.5
    return e
def reverb(x, decay_s=1.8, wet=0.35, pre=0.02, tone=4000):
    ir = rng.standard_normal(n(decay_s)) * np.exp(-tt(n(decay_s)) / (decay_s / 3.5))
    ir = lp(ir, tone); ir /= np.abs(ir).sum() ** 0.5 * 8
    w = sg.fftconvolve(x, ir)[:len(x) + n(decay_s)]
    y = np.zeros(len(w)); y[:len(x)] += x; y[n(pre):] += wet * w[:len(w) - n(pre)]
    return y
def ramp(x, a, b, p=1.0):
    e = np.ones(len(x)); e[:] = np.linspace(a, b, len(x)) ** p
    return x * e
def place(buf, x, at, gain=1.0):
    i = n(at); j = min(len(buf), i + len(x))
    if i < len(buf): buf[i:j] += gain * x[:j - i]
def stereo(mono, width=0.006):
    d = n(width); L = mono.copy(); Rr = np.concatenate([np.zeros(d), mono[:-d]]) if d else mono
    return np.stack([0.5 * L + 0.5 * Rr * 0.9, 0.5 * Rr + 0.5 * L * 0.9], 1)
def write(path, st):
    st = np.tanh(st * 1.05) * 0.7
    st = st / max(np.abs(st).max(), 1e-6) * 0.7  # ~ -3 dBFS
    import wave
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())

# ---------------- instruments ----------------
def tick(tock=False):
    """BOLD mechanical clock tick: click + wooden knock + low thump + sub, small room."""
    N = n(0.42); x = np.zeros(N)
    click = hp(rng.standard_normal(n(0.004)), 3000) * 0.9; place(x, click, 0)
    knock = bp(rng.standard_normal(n(0.05)), 700 if tock else 1000, 2200 if tock else 3000) * decay(n(0.05), 0.012) * 2.4; place(x, knock, 0.001)
    thump = sine(np.linspace(70 if tock else 84, 44, n(0.24)), n(0.24)) * decay(n(0.24), 0.07) * 1.6; place(x, thump, 0.002)
    sub = sine(38, n(0.2)) * decay(n(0.2), 0.06) * 0.9; place(x, sub, 0.003)
    return reverb(x, 0.6, 0.22, 0.008, 3000)
def braam(f=36.7, dur=1.6, gain=1.0):
    N = n(dur); x = (saw(f, N) + saw(f, N, .006) + saw(f, N, -.005) + 0.6 * saw(f * 2, N, .003)) / 3.2
    x = sweep_lp(x, 1400, 260, 24) * ar(N, 0.03, dur * 0.7) * decay(N, dur * 0.55, 1.2)
    return reverb(x, 2.5, 0.4) * gain
def impact():
    N = n(2.4); x = sine(np.linspace(95, 27, N), N) * decay(N, 0.55) * 1.4
    x += lp(rng.standard_normal(N), 900) * decay(N, 0.12) * 1.1
    x += hp(rng.standard_normal(N), 2500) * decay(N, 0.03) * 0.8
    return reverb(x, 3.5, 0.5)
def drone(f, dur, gain=1.0, fc=180):
    N = n(dur); x = (saw(f, N) + saw(f, N, .004) + saw(f, N, -.003) + 0.5 * sine(f, N)) / 3
    x = lp(x, fc) * (1 + 0.12 * sine(0.33, N)) * ar(N, 1.2, 1.5)
    return x * gain
def strings(freqs, dur, gain=1.0, fc_from=500, fc_to=3200):
    N = n(dur); x = np.zeros(N); vib = 1 + 0.003 * sine(5.6, N)
    for f in freqs:
        for det in (-.004, 0, .005):
            x += saw(f * (1 + det), N) * 0.6
            x = x if det else x  # keep
    x = np.zeros(N)
    for f in freqs:
        for det in (-.004, 0, .005):
            ph = np.cumsum(f * (1 + det) * vib) / SR; x += (2 * (ph % 1) - 1)
    x /= (3 * len(freqs)); x = sweep_lp(x, fc_from, fc_to, 40) * ar(N, 2.5, 0.3)
    return reverb(x, 2.2, 0.3) * gain
def riser(dur):
    N = n(dur); x = rng.standard_normal(N)
    out = np.zeros(N); steps = 40; e = np.linspace(0, N, steps + 1).astype(int)
    for i in range(steps):
        k = i / (steps - 1); lo = 200 + 3000 * k ** 2; hi = lo * 2.2
        out[e[i]:e[i + 1]] = bp(x[e[i]:e[i + 1]], lo, hi)
    out = out * np.linspace(0, 1, N) ** 2.2 * 1.2
    out += sine(np.linspace(110, 880, N), N) * np.linspace(0, 0.35, N) ** 2
    return out
def heartbeat():
    N = n(0.9); x = np.zeros(N)
    for at, g in ((0.0, 1.0), (0.19, 0.7)):
        place(x, lp(sine(np.linspace(62, 40, n(0.16)), n(0.16)) * decay(n(0.16), 0.045), 120) * g, at)
    return x
def piano(f, dur=4.0, gain=1.0):
    N = n(dur); x = np.zeros(N)
    for k, g in enumerate((1, .45, .25, .12, .08, .05)):
        x += sine(f * (k + 1) * (1 + 0.0004 * k * k), N) * g * decay(N, dur / (2.2 + k))
    x *= ar(N, 0.004, 0.2); x = reverb(x, 2.8, 0.42, 0.015, 5000)
    return x * gain
def whoosh(dur=0.5, rev=False):
    N = n(dur); x = rng.standard_normal(N); out = np.zeros(N); steps = 20; e = np.linspace(0, N, steps + 1).astype(int)
    for i in range(steps):
        k = i / (steps - 1); lo = 150 + 2500 * (k if not rev else 1 - k) ** 2
        out[e[i]:e[i + 1]] = bp(x[e[i]:e[i + 1]], lo, lo * 3)
    w = np.sin(np.pi * np.linspace(0, 1, N)) ** 2
    return out * w * 0.9
def pulse(): return lp(rng.standard_normal(n(0.05)), 500) * decay(n(0.05), 0.012) * 1.5

# ---------------- REEL 2 ----------------
def compose_reel2():
    T = TL["reel2"]; D = T["duration"]; buf = np.zeros(n(D) + n(4))
    clock_end = T["clock_end"]; fs = T["final_start"]
    # bed: sub drone D1 rising, strings D minor entering at 3s and swelling to the hit
    place(buf, ramp(drone(36.71, clock_end + 0.3, 0.8, 160), 0.35, 1.0), 0)
    place(buf, ramp(strings([146.83, 174.61, 220.0], clock_end - 3.0 + 0.4, 0.48, 380, 3800), 0.15, 1.0, 1.4), 3.0)
    place(buf, ramp(strings([293.66, 349.23, 440.0, 587.33], 4.4, 0.5, 900, 6000), 0.2, 1.0, 1.2), clock_end - 4.4)
    # bold ticks every second (tock on odd), last tick replaced by the impact
    for s in range(0, int(clock_end)):
        place(buf, tick(tock=bool(s % 2)), s, 2.1 + 0.06 * s)
    # word hits
    for k, tk in enumerate(T["ticks"]):
        place(buf, braam(36.71 if k % 2 == 0 else 32.70, 1.7, 0.8), tk["at"] + 0.01)
        place(buf, whoosh(0.45, rev=True), tk["at"] - 0.42, 0.6)
    # accelerating pulse + riser into 12
    t_ = 8.0; gap = 0.5
    while t_ < clock_end - 0.05:
        place(buf, pulse(), t_, 0.5 + 0.9 * (t_ - 8) / 4); gap = max(gap * 0.86, 0.06); t_ += gap
    place(buf, riser(3.2), clock_end - 3.2, 1.0)
    place(buf, impact(), clock_end, 1.9)
    # dramatic silence, then heartbeat + low pad under the final line, stinger on "روح صوّت"
    words = T["final"]["words"]; stinger_t = words[-2]["t"] if len(words) >= 2 else fs + T["final"]["vo_dur"] - 1.0
    hb = fs - 0.2
    while hb < D - 1.0:
        place(buf, heartbeat(), hb, 0.9); hb += 1.05
    place(buf, drone(36.71, D - fs + 0.5, 0.5, 140), fs - 0.3)
    place(buf, strings([146.83, 174.61, 220.0, 293.66], D - stinger_t + 0.3, 0.45, 300, 2600), stinger_t - 0.05)
    place(buf, braam(36.71, 2.6, 1.1), stinger_t)
    place(buf, impact(), stinger_t, 0.55)
    buf = buf[:n(D)]; buf[-n(0.8):] *= np.linspace(1, 0, n(0.8))
    write(OUT / "reel2_bed.wav", stereo(buf))
    # separate tick-only stem (handy for the editor / mix tweaks)
    tk = np.zeros(n(D))
    for s in range(0, int(clock_end)): place(tk, tick(tock=bool(s % 2)), s)
    write(OUT / "reel2_ticks_only.wav", stereo(tk))

# ---------------- REEL 1 ----------------
def compose_reel1():
    T = TL["reel1"]; D = T["duration"]; buf = np.zeros(n(D) + n(4))
    sc = {s["scene"]: s for s in T["scenes"]}
    black = sc["black"]["start"]
    # paper room-tone + first piano note on the fake title card
    place(buf, lp(rng.standard_normal(n(sc["titlecard"]["end"])), 1200) * 0.05 * ar(n(sc["titlecard"]["end"]), 0.05, 0.1), 0)
    place(buf, piano(146.83, 3.5, 0.8), 0.15)
    # dark bed until the cut to black
    place(buf, ramp(drone(36.71, black + 0.2, 0.75, 150), 0.5, 1.0), sc["couch"]["start"] - 0.1)
    place(buf, ramp(strings([73.42, 87.31, 110.0], black - sc["street"]["start"] + 0.2, 0.32, 260, 1400), 0.3, 1.0), sc["street"]["start"])
    motif = {"couch": 293.66, "corridor": 349.23, "street": 220.0, "silhouette": 233.08, "closeup": 146.83}
    for name, f in motif.items():
        s = sc[name]
        place(buf, piano(f, 4.5, 0.55), s["start"] + 0.05)
        place(buf, whoosh(0.5), s["start"] - 0.35, 0.55)
    hb = sc["silhouette"]["start"]
    while hb < black - 0.6:
        place(buf, heartbeat(), hb, 0.55); hb += 1.1
    # reveal hit on the word «المستفيد» (last word of the closeup line)
    w = sc["closeup"]["words"]; reveal = w[-1]["t"] if w else sc["closeup"]["vo_start"] + 1.6
    place(buf, braam(32.70, 2.2, 1.0), reveal); place(buf, impact(), reveal, 0.5)
    # hard cut to black: kill everything, 0.45 s of silence, then heartbeat and the stinger on «روح صوّت»
    buf[n(black):] = 0
    hb = black + 0.45
    while hb < D - 1.2:
        place(buf, heartbeat(), hb, 0.8); hb += 1.05
    place(buf, drone(36.71, D - black, 0.35, 120), black + 0.4)
    w = sc["black"]["words"]; stinger_t = w[-2]["t"] if len(w) >= 2 else D - 1.5
    place(buf, strings([146.83, 174.61, 220.0, 293.66], D - stinger_t + 0.3, 0.42, 300, 2600), stinger_t - 0.05)
    place(buf, braam(36.71, 2.6, 1.1), stinger_t); place(buf, impact(), stinger_t, 0.5)
    buf = buf[:n(D)]; buf[-n(0.8):] *= np.linspace(1, 0, n(0.8))
    write(OUT / "reel1_bed.wav", stereo(buf))

if __name__ == "__main__":
    compose_reel2(); compose_reel1()
    print("wrote", sorted(p.name for p in OUT.iterdir()))
