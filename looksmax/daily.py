"""Daily plan: which habits to do today and the tip of the day.

The checklist is built from a fixed set of evidence-graded habits. Habits tied
to an improvement area only appear when the latest assessment flagged that
area, and some habits only appear on certain weekdays.
"""

from datetime import date

from . import habits as H

ALL_DAYS = range(7)
MWF, TTS, SUN = (0, 2, 4), (1, 3, 5), (6,)

# id, label, category, evidence, weekdays, areas (None = always), sex (None = both), note
HABITS = [
    ("photo", "Daily check-in photo (same place, light and distance)", "tracking", "-", ALL_DAYS, None, None,
     "Ticked automatically when you upload today's photo."),
    ("sunscreen", "Morning: SPF 30+ sunscreen on face and neck", "skin", "strong", ALL_DAYS, None, None,
     "Reapply if you are outside for hours."),
    ("sleep", "Slept 7-9 hours last night", "recovery", "moderate", ALL_DAYS, None, None,
     "Short sleep makes faces look puffier and less healthy."),
    ("steps", "8,000+ steps", "body", "strong", ALL_DAYS, None, None, ""),
    ("protein", "Hit protein target (1.6-2.2 g per kg body weight)", "nutrition", "strong", ALL_DAYS, None, None, ""),
    ("veg", "2+ servings of colourful vegetables or fruit", "nutrition", "moderate", ALL_DAYS, None, None,
     "Carotenoids (carrots, sweet potato, tomato, peppers, greens) give skin a healthy golden tone in 6-8 weeks."),
    ("training", "Resistance training session", "body", "strong", MWF, None, None,
     "Compound lifts; shoulders and upper back build the V-shape."),
    ("cardio", "20-30 min cardio or a long walk", "body", "strong", TTS, None, None, ""),
    ("deficit", "Stayed within your calorie target (~300-500 kcal deficit)", "nutrition", "strong", ALL_DAYS,
     ("leanness",), None, "Facial leanness is your biggest lever. Slow and steady keeps the face from looking gaunt."),
    ("no_alcohol", "No alcohol today", "nutrition", "moderate", ALL_DAYS, ("leanness", "skin", "eyes"), None,
     "Alcohol causes facial puffiness and redness the next day."),
    ("sodium", "Kept salt moderate, ate potassium-rich foods", "nutrition", "weak", ALL_DAYS, ("leanness", "eyes"), None,
     "Salt spikes cause next-day water retention around the face and eyes."),
    ("cleanse", "Evening: gentle cleanse + moisturiser", "skin", "moderate", ALL_DAYS, None, None, ""),
    ("retinoid", "Evening: retinoid (adapalene or prescribed tretinoin)", "skin", "strong", MWF, ("skin",), None,
     "Start 2-3x/week. Not during pregnancy. Ask a dermatologist if irritated."),
    ("back_sleep", "Sleep on your back, head slightly raised", "recovery", "weak", ALL_DAYS, ("eyes", "symmetry"), None,
     "Less morning puffiness and fewer one-sided creases."),
    ("chew_both", "Chew on both sides", "habit", "weak", ALL_DAYS, ("symmetry",), None, ""),
    ("posture", "Posture check: head stacked over shoulders (3 reminders)", "habit", "weak", ALL_DAYS, None, None, ""),
    ("cold", "Morning cold water or cold compress on face", "skin", "weak", ALL_DAYS, ("eyes", "leanness"), None,
     "Temporary depuffing for a few hours."),
    ("beard", "Trim beard and clean neckline below the jaw", "grooming", "moderate", SUN, None, "M",
     "Keep it longer at the chin if your lower third is short."),
    ("brows", "Tidy brow strays only (keep them full)", "grooming", "weak", SUN, None, None, ""),
    ("progress_review", "Weekly review: compare this week's photos and numbers", "tracking", "-", SUN, None, None, ""),
]

HABIT_IDS = [h[0] for h in HABITS]


def plan_for(day: date, priorities, sex):
    """Habits for a given day, given the latest priority areas."""
    out = []
    for hid, label, cat, ev, days, areas, hsex, note in HABITS:
        if day.weekday() not in days:
            continue
        if hsex and hsex != sex:
            continue
        if areas and not set(areas) & set(priorities or []):
            continue
        out.append(dict(id=hid, label=label, category=cat, evidence=ev, note=note,
                        targeted=bool(areas)))
    return out


def tip_for(day: date, priorities):
    """One action to focus on today, rotating through your priority areas,
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
