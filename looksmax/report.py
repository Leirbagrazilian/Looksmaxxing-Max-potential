"""Turn an assessment into a Markdown improvement report."""

from datetime import date

import cv2
import numpy as np

from . import habits as H
from .measure import (ALAR_L, ALAR_R, CHIN, GON_L, GON_R, L_BROW_MID, L_EYE_IN,
                      L_EYE_OUT, L_LID_TOP, NASION, R_BROW_MID, R_EYE_IN,
                      R_EYE_OUT, R_LID_TOP, SUBNASALE, ZYG_L, ZYG_R)

# metric -> (label, area, short explanation)
METRICS = {
    "cheek_jaw": ("Cheekbone-to-jaw width", "leanness", "higher = more taper from cheekbones to jaw"),
    "fwhr": ("Width-to-height ratio (fWHR)", "leanness", "face width / brow-to-lip height"),
    "jaw_width_ratio": ("Jaw width / cheekbone width", "leanness", "lower = more taper"),
    "face_height_width": ("Face height / width", "leanness", "higher = longer, leaner-looking face"),
    "intercanthal_eye_ratio": ("Eye gap / eye width", "eyes", "lower = eyes larger relative to the gap"),
    "brow_eye_distance": ("Brow-to-eyelid distance", "eyes", "lower = lower-set brows ('hunter eyes')"),
    "canthal_tilt": ("Canthal tilt (degrees)", "eyes", "positive = outer eye corner higher"),
    "eye_separation_ratio": ("Pupil distance / face width", "eyes", "community ideal ~0.45-0.47"),
    "chin_philtrum_ratio": ("Chin / philtrum ratio", "lower_third", "community ideal ~2.0-2.25"),
    "mid_lower_third": ("Midface / lower-face height", "lower_third", "nasion-subnasale vs subnasale-chin"),
    "midface_ratio": ("Midface ratio", "midface", "pupil distance / pupils-to-lip height"),
    "nose_width_ratio": ("Nose width / eye gap", "harmony", "classic ideal ~1.0"),
    "lip_height_ratio": ("Lip height / mouth width", "harmony", "lip fullness"),
    "avg_dist": ("Distance from average face", "harmony", "lower = more average (harmonious)"),
    "asym": ("Asymmetry", "symmetry", "lower = more symmetric"),
    "masc": ("Masculinity axis", "dimorphism", "higher = more male-typical shape"),
    "skin_rough": ("Skin texture roughness", "skin", "lower = smoother"),
    "skin_uneven": ("Skin colour unevenness", "skin", "lower = more even"),
}
COMP_LABEL = {"leanness": "Facial leanness", "dimorphism": "Sex-typical features",
              "symmetry": "Symmetry", "harmony": "Harmony", "skin": "Skin (photo-based)"}
R_MIN = 0.10  # minimum |r| with ratings for a metric to drive advice


def ordinal(n):
    n = int(round(n))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _bar(pct, width=20):
    filled = int(round(pct / 100 * width))
    return "█" * filled + "░" * (width - filled)


def _grade(e):
    return {"strong": "●●●", "moderate": "●●○", "weak": "●○○", "none": "○○○"}[e]


def _band(pct):
    if pct < 20:
        return "well below average"
    if pct < 40:
        return "below average"
    if pct <= 60:
        return "average"
    if pct <= 80:
        return "above average"
    return "well above average"


def photo_warnings(m):
    w = []
    if abs(m["yaw"]) > 10:
        w.append(f"Head turned {abs(m['yaw']):.0f}° sideways; face the camera straight on.")
    if abs(m["roll"]) > 8:
        w.append(f"Head tilted {abs(m['roll']):.0f}° to the side; keep it level.")
    if m["pitch"] < -8 or m["pitch"] > 15:
        w.append(f"Strong up/down head tilt ({m['pitch']:.0f}°); keep the head level for analysis.")
    if m["mouth_open"] > 0.12:
        w.append("Mouth open; use a neutral closed-mouth expression.")
    if m["face_px"] < 60:
        w.append("Face is small in the picture; use a higher-resolution, closer crop.")
    return w


def flagged_metrics(a):
    """Metrics linked to ratings (|r| >= R_MIN) where the person sits on the unfavourable side."""
    out = []
    for name, (label, area, _) in METRICS.items():
        r = a["rating_corr_adj"][name]
        if abs(r) < R_MIN:
            continue
        pct = a["metric_pct"][name]
        favourable_pct = pct if r > 0 else 100 - pct
        if favourable_pct < 35:
            out.append((name, label, area, r, favourable_pct))
    return sorted(out, key=lambda x: x[4])


def priority_areas(a, flags):
    """Order improvement areas by how far below the reference they are,
    weighted by how much the area matters and how changeable it is."""
    change = {"high": 1.0, "medium": 0.6, "low": 0.3}
    scores = {}
    for c, v in a["components"].items():
        area = c
        gap = max(0.0, 35 - v["pct"]) / 35
        w = abs(a["overall"]["coef"].get(c, 0.05)) + 0.05
        scores[area] = gap * w * change[H.AREA_ACTIONS[area]["changeable"]]
    for _, _, area, r, fpct in flags:
        gap = (50 - fpct) / 50
        s = gap * abs(r) * change[H.AREA_ACTIONS[area]["changeable"]]
        scores[area] = max(scores.get(area, 0), s)
    return [k for k, v in sorted(scores.items(), key=lambda kv: -kv[1]) if v > 0]


def annotate(img, pts, path):
    out = img.copy()
    s = max(1, int(round(max(img.shape[:2]) / 400)))
    lines = [((ZYG_R, ZYG_L), (0, 200, 255)), ((GON_R, GON_L), (0, 140, 255)),
             ((R_EYE_IN, R_EYE_OUT), (255, 200, 0)), ((L_EYE_IN, L_EYE_OUT), (255, 200, 0)),
             ((R_BROW_MID, R_LID_TOP), (200, 255, 0)), ((L_BROW_MID, L_LID_TOP), (200, 255, 0)),
             ((NASION, SUBNASALE), (180, 120, 255)), ((SUBNASALE, CHIN), (255, 120, 180)),
             ((ALAR_R, ALAR_L), (120, 255, 180)), ((R_EYE_IN, L_EYE_IN), (255, 255, 255))]
    for (a, b), col in lines:
        cv2.line(out, tuple(map(int, pts[a])), tuple(map(int, pts[b])), col, s, cv2.LINE_AA)
    for p in pts[:468:3]:
        cv2.circle(out, tuple(map(int, p)), max(1, s // 2), (230, 230, 230), -1, cv2.LINE_AA)
    cv2.imwrite(str(path), out)


def render(a, sex, image_name=None, annotated_name=None):
    L = []
    add = L.append
    m = a["metrics"]
    flags = flagged_metrics(a)
    areas = priority_areas(a, flags)
    grp = {"M": "men", "F": "women", "AM": "Asian men", "CM": "Caucasian men",
           "AF": "Asian women", "CF": "Caucasian women"}[a["key"]]

    add(f"# Face assessment report")
    add(f"_{date.today().isoformat()} · photo: {image_name or '-'} · compared with "
        f"{a['n_reference']:,} rated {grp} (SCUT-FBP5500)_\n")
    if annotated_name:
        add(f"![landmarks]({annotated_name})\n")

    # ---- summary
    add("## Summary\n")
    o = a["overall"]
    add(f"**Structure index:** {ordinal(o['pct'])} percentile ({_band(o['pct'])}). "
        f"This combines the five components with weights learned from the ratings. "
        f"It explains only ~{max(o['cv_r2'], 0) * 100:.0f}% of rating differences on its own, because "
        f"hair, eyes, grooming, lighting and expression matter a lot and are not measured, so treat it "
        f"as a rough guide and not a looks rating.\n")
    if areas:
        add("**Top priorities** (biggest gap × importance × how changeable):\n")
        for i, ar in enumerate(areas[:3], 1):
            info = H.AREA_ACTIONS[ar]
            add(f"{i}. **{info['title']}** (changeability: {info['changeable']})")
        add("")
    else:
        add("No area is clearly below the reference group. Focus on presentation and the core habits.\n")

    # ---- photo check
    add("## Photo check\n")
    warns = photo_warnings(m)
    add(f"Head pose: yaw {m['yaw']:+.0f}°, pitch {m['pitch']:+.0f}°, roll {m['roll']:+.0f}°. "
        f"Pose effects are removed statistically before comparison.\n")
    if warns:
        add("⚠️ The results are less reliable for this photo:\n")
        for w in warns:
            add(f"- {w}")
        add("\nFor best results, use a straight-on, level, neutral-expression photo in even light, "
            "taken from 1.5 m or more.\n")
    else:
        add("✅ Photo is usable.\n")

    # ---- components
    add("## Component scores\n")
    add("Percentile among the reference group (50 = typical). Higher is better.\n")
    add("| Component | Percentile | | Weight in ratings* |")
    add("|---|---|---|---|")
    for c, v in a["components"].items():
        add(f"| {COMP_LABEL[c]} | {v['pct']:.0f} | `{_bar(v['pct'])}` | {o['coef'][c]:+.2f} |")
    add("\n\\* Regression weight learned from the reference ratings after removing pose effects. "
        "A weight near zero means this component barely predicted ratings in this group.\n")

    # ---- measurements
    add("## Measurements\n")
    add("| Measurement | You | Typical range (25-75%) | Your percentile | Link to ratings (r) |")
    add("|---|---|---|---|---|")
    for name, (label, _, expl) in METRICS.items():
        r = a["rating_corr_adj"][name]
        lo, hi = a["iqr"][name]
        link = f"{r:+.2f}" + (" ✱" if abs(r) >= R_MIN else "")
        add(f"| {label}<br><sub>{expl}</sub> | {a['adjusted'][name]:.3f} | {lo:.3f}-{hi:.3f} | "
            f"{a['metric_pct'][name]:.0f} | {link} |")
    add("\n✱ = meaningfully linked to ratings (|r| ≥ 0.10) in your reference group after controlling "
        "for pose; + means higher values went with higher ratings. Unmarked measurements are shown for "
        "information only: in the data they barely mattered, whatever the community says.\n")

    if flags:
        add("**Measurements where you sit on the less-favourable side:**\n")
        for name, label, area, r, fpct in flags:
            add(f"- {label}: you are at the {ordinal(fpct)} percentile in the favourable direction "
                f"(r = {r:+.2f}) → see *{H.AREA_ACTIONS[area]['title']}*")
        add("")

    # ---- actions
    add("## What to do\n")
    add("Evidence: ●●● strong · ●●○ moderate · ●○○ weak · ○○○ none\n")
    shown = areas[:4] if areas else []
    for ar in shown:
        info = H.AREA_ACTIONS[ar]
        add(f"### {info['title']}\n")
        add(f"_{info['why']}_\n")
        add("| Action | Evidence | Risk | Timeframe |")
        add("|---|---|---|---|")
        for act, ev, risk, tf in info["actions"]:
            add(f"| {act} | {_grade(ev)} | {risk} | {tf} |")
        add("")

    add("### Presentation (affects every photo)\n")
    for act, ev, risk in H.PRESENTATION:
        add(f"- {_grade(ev)} {act}")
    add("")

    # ---- habits
    add("## Habits\n")
    add("### Core habits\n")
    for name, ev, risk, note in H.CORE_HABITS:
        add(f"- {_grade(ev)} **{name}**" + (f". {note}" if note else ""))
    add("\n### Lesser-known habits\n")
    for name, ev, risk, note in H.LESSER_KNOWN:
        add(f"- {_grade(ev)} **{name}** (risk: {risk}). {note}")
    add("\n### Popular but overrated\n")
    for name, ev, risk, note in H.OVERRATED:
        add(f"- {_grade(ev)} **{name}**. {note}")
    add("\n### Avoid\n")
    for name, why in H.AVOID:
        add(f"- ⛔ **{name}**: {why}")
    add(f"\n> {H.SURGICAL_NOTE}\n")

    # ---- method
    add("## How this works and its limits\n")
    add("- 478 facial landmarks (MediaPipe) are measured on your photo and compared with the same "
        "measurements on 5,500 faces rated by 60 people each (SCUT-FBP5500).")
    add("- Head pose, expression and sharpness are removed statistically, because in the data head "
        f"angle alone predicted ratings (r ≈ {a['pose_rating_corr']['pitch']:+.2f}) more strongly "
        "than any facial measure.")
    add("- A frontal photo cannot measure profile features (maxilla projection, chin projection, "
        "gonial angle) or hair, height, body, voice or style.")
    add("- Most reference raters were young Chinese adults; preferences differ across cultures and "
        "individuals.")
    add("- This is a self-improvement guide, not a medical assessment or a fixed verdict on anyone's worth.")
    return "\n".join(L)
