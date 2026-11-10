"""Daily plan ("quests"), tip of the day, XP/ranks and coach messages.

The checklist is built from a fixed set of evidence-graded habits. Habits tied
to an improvement area only appear when the latest assessment flagged that
area, and some habits only appear on certain weekdays.

XP and ranks reward consistency (habits done), never looks.
"""

from datetime import date

from . import habits as H

ALL_DAYS = tuple(range(7))
MWF, TTS, SUN = (0, 2, 4), (1, 3, 5), (6,)
SLOTS = [("morning", "Morning"), ("day", "Day"), ("evening", "Evening")]
XP_BY_EVIDENCE = {"strong": 15, "moderate": 10, "weak": 5, "-": 20}


def _h(id, label, slot, evidence, days=ALL_DAYS, areas=None, sex=None, note=""):
    return dict(id=id, label=label, slot=slot, evidence=evidence, days=days,
                areas=areas, sex=sex, note=note, xp=XP_BY_EVIDENCE[evidence])


HABITS = [
    _h("photo", "Daily scan", "morning", "-",
       note="Same place, light and distance. Ticks itself when you upload."),
    _h("sunscreen", "SPF 30+ on face and neck", "morning", "strong",
       note="Every morning, all year. Reapply after hours outside."),
    _h("sleep", "Slept 7-9 hours", "morning", "moderate",
       note="Short sleep makes faces look puffier and less healthy."),
    _h("cold", "Cold water on face", "morning", "weak", areas=("eyes", "leanness"),
       note="Temporary depuffing for a few hours."),
    _h("steps", "8,000+ steps", "day", "strong"),
    _h("protein", "Hit protein target", "day", "strong",
       note="1.6-2.2 g per kg of body weight."),
    _h("veg", "2+ servings of colourful veg or fruit", "day", "moderate",
       note="Carotenoids give skin a healthy golden tone in 6-8 weeks."),
    _h("training", "Lift weights", "day", "strong", days=MWF,
       note="Compound lifts; shoulders and upper back build the V-shape."),
    _h("cardio", "20-30 min cardio or long walk", "day", "strong", days=TTS),
    _h("deficit", "Stay in calorie target", "day", "strong", areas=("leanness",),
       note="~300-500 kcal deficit. Facial leanness is your biggest lever."),
    _h("no_alcohol", "No alcohol", "day", "moderate", areas=("leanness", "skin", "eyes"),
       note="Alcohol causes facial puffiness and redness the next day."),
    _h("sodium", "Moderate salt, potassium-rich food", "day", "weak", areas=("leanness", "eyes"),
       note="Salt spikes cause next-day water retention in the face."),
    _h("chew_both", "Chew on both sides", "day", "weak", areas=("symmetry",)),
    _h("posture", "3 posture checks", "day", "weak",
       note="Head stacked over shoulders."),
    _h("cleanse", "Gentle cleanse + moisturiser", "evening", "moderate"),
    _h("retinoid", "Retinoid", "evening", "strong", days=MWF, areas=("skin",),
       note="Adapalene or prescribed tretinoin. Not during pregnancy."),
    _h("beard", "Trim beard + clean neckline", "evening", "moderate", days=SUN, sex="M",
       note="Keep it longer at the chin if your lower third is short."),
    _h("brows", "Tidy brow strays (keep them full)", "evening", "weak", days=SUN),
    _h("back_sleep", "Sleep on your back", "evening", "weak", areas=("eyes", "symmetry"),
       note="Head slightly raised: less morning puffiness."),
    _h("review", "Weekly review", "evening", "-", days=SUN,
       note="Compare this week's scans and habit rates on Progress."),
]
HABIT_BY_ID = {h["id"]: h for h in HABITS}
HABIT_IDS = list(HABIT_BY_ID)

RANKS = [(0, "Initiate"), (300, "Apprentice"), (900, "Adept"), (2000, "Vanguard"),
         (4000, "Ascendant"), (7000, "Paragon"), (11000, "Apex")]


def plan_for(day: date, priorities, sex):
    out = []
    for h in HABITS:
        if day.weekday() not in h["days"] or (h["sex"] and h["sex"] != sex):
            continue
        if h["areas"] and not set(h["areas"]) & set(priorities or []):
            continue
        out.append({**h, "targeted": bool(h["areas"])})
    return out


def tip_for(day: date, priorities):
    """One action to focus on today, rotating through priority areas,
    lesser-known habits and photo tips."""
    pool = []
    for area in (priorities or [])[:3]:
        info = H.AREA_ACTIONS[area]
        for act, ev, risk, tf in info["actions"]:
            pool.append(dict(title=info["title"], text=act, evidence=ev, risk=risk))
    for name, ev, risk, note in H.LESSER_KNOWN:
        pool.append(dict(title="Lesser-known habit", text=f"{name}. {note}", evidence=ev, risk=risk))
    for act, ev, risk in H.PRESENTATION:
        pool.append(dict(title="Presentation", text=act, evidence=ev, risk=risk))
    return pool[day.toordinal() % len(pool)]


def rank_for(xp):
    idx = max(i for i, (floor, _) in enumerate(RANKS) if xp >= floor)
    floor, name = RANKS[idx]
    nxt = RANKS[idx + 1] if idx + 1 < len(RANKS) else None
    return dict(name=name, tier=idx + 1, xp=xp, floor=floor,
                next_name=nxt[1] if nxt else None, next_at=nxt[0] if nxt else None,
                progress=(xp - floor) / (nxt[0] - floor) if nxt else 1.0)


def coach_line(plan, done, has_scan, is_today):
    """One short, direct sentence about what to do next."""
    left = [h for h in plan if h["id"] not in done]
    if not plan:
        return "Rest day. Nothing scheduled."
    if not left:
        return f"All {len(plan)} quests cleared. +{sum(h['xp'] for h in plan)} XP banked."
    if is_today and not has_scan:
        return "Start with today's scan. It takes 10 seconds and tunes your quests."
    if len(left) == len(plan):
        return f"New day. Start with: {left[0]['label'].lower()}."
    return f"{len(plan) - len(left)} done, {len(left)} to go. Next: {left[0]['label'].lower()}."
