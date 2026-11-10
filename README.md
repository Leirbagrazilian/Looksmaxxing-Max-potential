# Looksmaxxing: Max Potential

Data-driven face assessment and improvement plan. Give it a frontal photo and it:

1. Measures 478 facial landmarks, head pose and skin texture.
2. Compares you with **5,500 faces rated by 60 people each** (SCUT-FBP5500), after removing the effect of head pose, expression and photo sharpness.
3. Writes a report with:
   - percentile scores for **leanness, sex-typical features, symmetry, harmony and skin**
   - 17 measurements (canthal tilt, chin/philtrum ratio, fWHR, eye spacing, midface ratio and more), each showing **whether it actually predicted ratings in the data**
   - your top priority areas, ranked by gap × importance × how changeable they are
   - concrete actions, each graded by **evidence** (●●● strong to ○○○ none) and **risk**
   - core habits, lesser-known habits, popular-but-overrated practices, and practices to avoid

## Usage

```bash
pip install -r requirements.txt
python -m looksmax photo.jpg --sex M                 # compare with rated men
python -m looksmax photo.jpg --sex F --ethnicity asian --out my_report
```

The first run downloads the MediaPipe face model (~4 MB) to `~/.cache/looksmax/`. On minimal Linux
images, MediaPipe also needs `libegl1` and `libgles2` (`apt-get install libegl1 libgles2`).

Output in the `--out` folder: `report.md`, `landmarks.jpg` (annotated photo), `assessment.json` (all numbers).

**For best results:** use a straight-on photo with a level head and a neutral, closed-mouth expression, in even light, taken from 1.5 m or more (close selfies distort the nose and jaw).

## Ascend: the daily app

A dark, phone-first web app that runs on your own computer. Every day you scan your face, clear your quests and climb the ranks.

**Start it (easiest):**

| System | Do this |
|---|---|
| macOS / Linux | double-click or run `./start.sh` |
| Windows | double-click `start.bat` |

The first run sets everything up (needs Python 3.10-3.12 and internet once; takes a few minutes). After that it opens in your browser.
To use it from your **phone**, run `./start.sh --phone` (or `start.bat --phone`) and open the address it prints on your phone, on the same Wi-Fi.

Manual start: `pip install -r requirements.txt && python -m looksmax.web`.

**Tabs:**

- **Quests:** a progress ring and one direct coach line ("3 done, 9 to go. Next: protein target."). Quests are split into Morning / Day / Evening, and the current block opens by default. Quests tagged *for you* target the weak areas from your latest scan. Tap ⓘ for the why and the evidence grade. Every tick saves instantly and earns XP. One focus tip per day.
- **Scan:** take or upload a photo (JPEG, PNG or iPhone HEIC; phone rotation is handled). You get a structure-index percentile, **your biggest lever** with a link to the quests that target it, the five component bars and photo-quality warnings. *Full breakdown* has priorities, actions, all measurements and habits, in collapsible sections.
- **Progress:** streak, weekly completion and scan count, then three panes: a habit heatmap with per-habit rates, face trend charts, and a photo gallery.
- **Profile:** rank and XP, plus reference-group settings.

**Ranks** (Initiate, Apprentice, Adept, Vanguard, Ascendant, Paragon, Apex) measure **consistency, not looks**. XP per quest: strong-evidence habit 15, moderate 10, weak 5, scan 20.

**Photos:** every photo is cropped and resized to the same framing as the reference faces before measuring, so a 12 MP phone photo is comparable with the reference set. For a meaningful trend, scan in the same place, light and distance daily, with your head level.

All data (photos plus a SQLite database) stays on your computer in `~/.looksmax` (change it with `LOOKSMAX_HOME`).

## Ascend on your phone (hosted version)

`webapp/` is the same app as a static, installable web app (PWA):

- **On-device:** MediaPipe runs in the phone's browser. Photos are analysed on the phone and never uploaded. Scans, quests and settings live in the browser's storage (IndexedDB).
- **Install:** open the link, then on iPhone use Safari *Share → Add to Home Screen*, or on Android use Chrome *⋮ → Install app*. Installed, it opens full-screen, works offline, and the browser won't clear its data.
- **Backup:** *Profile → Backup & data* exports one file with everything (photos included). Import it on a new phone.
- **Same scoring:** the web reference model is fitted from the 5,500 reference faces measured by the web app's own code (`webapp/tools/measure_dataset.cjs` in headless Chromium). Phone and reference measurements are therefore identical, and JS scoring matches the Python package to within 0.1 percentile points.

Build and deploy:

```bash
cd webapp && npm install && python3 build.py   # -> webapp/dist (static files)
node tools/serve.cjs dist 8800                 # local test with production headers
./deploy.sh                                    # Netlify (NETLIFY_AUTH_TOKEN=...)
```

## What the data says (summary)

From `docs/weight-validation.md` and the reference model:

- **Facial leanness** is the most reliable facial predictor of ratings, and also the most changeable.
- **Head angle in the photo** (slightly tilted down) predicts ratings more strongly than any facial measure (r ≈ 0.5).
- After controlling for pose, the measures that still matter for men include eyes that are larger relative to the gap between them, lower-set brows, a longer chin relative to the philtrum, and a leaner, longer face shape.
- **Canthal tilt**, a community favourite, lost its link to ratings once head angle was controlled.
- The measurable geometry explains only a small share of ratings. Hair, grooming, eyes, lighting and expression matter a lot.

## Project layout

| Path | What |
|---|---|
| `looksmax/` | the assessment tool (measurement, reference model, report, habits knowledge base) |
| `looksmax/data/reference.npz` | derived statistics from SCUT-FBP5500 (no images) |
| `looksmax/habits.py` | actions and habits with evidence and risk grades |
| `looksmax/daily.py` | quests, XP/ranks, coach lines and tip of the day |
| `looksmax/web/` | the Ascend web app |
| `analysis/` | the weight-validation study |
| `docs/weight-validation.md` | results of that study |

Rebuild the reference model (needs the SCUT-FBP5500 images, which are not redistributed here):

```bash
python -m looksmax.reference <images_dir> <All_labels.csv>
```

## Limits

A frontal photo can't measure profile features (maxilla and chin projection, gonial angle), height, body, voice or style. Most reference raters were young Chinese adults. This is a self-improvement guide, not a medical assessment. Any surgical or medical step needs a qualified professional.
