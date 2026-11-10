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

## Daily tracker app

A local web app for daily check-ins:

```bash
python -m looksmax.web                    # open http://127.0.0.1:8000
python -m looksmax.web --host 0.0.0.0     # also reachable from your phone on the same Wi-Fi
```

- **Today:** upload (or take) today's photo. It is analysed on the spot: structure index, five component bars, photo-quality warnings and a full report.
- **Daily checklist:** habits for today, tailored to the priority areas of your latest check-in (marked *for you*), with weekday rotation (training Mon/Wed/Fri, cardio Tue/Thu/Sat, grooming and a weekly review on Sunday). Each habit shows its evidence grade. Ticks save instantly.
- **Focus for today:** one action per day, rotating through your priority areas, lesser-known habits and photo tips.
- **Progress:** 4-week completion heatmap, streak (days at 70%+ of the checklist), per-habit completion rates, trend charts for every face score (daily dots plus a 7-check-in average) and a photo strip.
- Use ‹ › to go back and fill in past days.

All data (photos and a SQLite database) stays on your machine in `~/.looksmax` (change it with `LOOKSMAX_HOME`).
Take the photo in the same place, light and distance every day; otherwise day-to-day changes mostly reflect the photo, not your face.

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
| `looksmax/daily.py` | daily checklist and tip-of-the-day logic |
| `looksmax/web/` | the daily tracker web app |
| `analysis/` | the weight-validation study |
| `docs/weight-validation.md` | results of that study |

Rebuild the reference model (needs the SCUT-FBP5500 images, which are not redistributed here):

```bash
python -m looksmax.reference <images_dir> <All_labels.csv>
```

## Limits

A frontal photo can't measure profile features (maxilla and chin projection, gonial angle), height, body, voice or style. Most reference raters were young Chinese adults. This is a self-improvement guide, not a medical assessment. Any surgical or medical step needs a qualified professional.
