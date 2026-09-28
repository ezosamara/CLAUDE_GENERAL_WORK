// Deterministic frame renderer: loads reelN.html, calls window.seek(t) per frame, screenshots to JPEG, then ffmpeg encodes.
// usage: node render/render.mjs reel1 [--fps 30] [--w 1080 --h 1920] [--out out/reel1_9x16.mp4] [--preview] [--stills 1.0,5.2]
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { readFileSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url)); const ROOT = resolve(here, '..');
const args = process.argv.slice(2); const reel = args[0]; const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const FPS = +opt('fps', 30), W = +opt('w', 1080), H = +opt('h', 1920), preview = args.includes('--preview'), stills = opt('stills', null);
const tl = JSON.parse(readFileSync(resolve(ROOT, 'render/timeline.json'), 'utf8'))[reel];
const frames = resolve(ROOT, `render/frames_${reel}_${W}x${H}`); rmSync(frames, { recursive: true, force: true }); mkdirSync(frames, { recursive: true });
const browser = await chromium.launch(); const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
await page.addInitScript(`window.PARAMS = ${JSON.stringify({ timeline: tl, W, H })}`);
await page.goto('file://' + resolve(ROOT, `render/${reel}.html`)); await page.evaluate(() => window.READY);
const total = Math.ceil(tl.duration * FPS);
if (stills) { const ts = stills.split(',').map(Number); for (const t of ts) { await page.evaluate(t => window.seek(t), t); await page.screenshot({ path: resolve(frames, `still_${t.toFixed(2)}.png`) }); } console.log('stills in', frames); await browser.close(); process.exit(0); }
const step = preview ? 3 : 1; let n = 0; const t0 = Date.now();
for (let i = 0; i < total; i += step) { await page.evaluate(t => window.seek(t), i / FPS); await page.screenshot({ path: resolve(frames, `f_${String(n++).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 93 }); }
await browser.close(); console.log(`${n} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
const out = opt('out', resolve(ROOT, `out/${reel}_${W}x${H}_video.mp4`)); mkdirSync(dirname(out), { recursive: true });
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS / step), '-i', resolve(frames, 'f_%05d.jpg'),
  '-vf', `noise=alls=7:allf=t+u,format=yuv420p`, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-r', String(FPS), '-movflags', '+faststart', out], { stdio: 'inherit' });
console.log('video ->', out);
