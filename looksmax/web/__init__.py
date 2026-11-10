"""Ascend: daily tracker web app (scan, quests, progress).

Run:  python -m looksmax.web            (http://127.0.0.1:8000)
      python -m looksmax.web --host 0.0.0.0   to open it from your phone on the same Wi-Fi
"""

import io
import threading
from datetime import date, timedelta

import cv2
import numpy as np
from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)

from .. import daily
from .. import habits as H
from ..measure import FaceMeasurer
from ..reference import Reference
from ..report import (COMP_LABEL, METRICS, R_MIN, annotate, flagged_metrics,
                      ordinal, photo_warnings, priority_areas)
from .charts import trend_svg
from .store import Store

MAX_UPLOAD_MB = 25

try:                                   # iPhone HEIC photos
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass


def decode_image(data):
    """Bytes -> upright BGR image. Handles JPEG/PNG/WebP/HEIC and EXIF rotation."""
    try:
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)
    except Exception:
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def create_app(store=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    app.jinja_env.filters["ordinal"] = ordinal
    store = store or Store()
    ref = Reference()
    lock = threading.Lock()          # MediaPipe detector is not thread-safe
    measurer = {}

    def get_measurer():
        if "fm" not in measurer:
            measurer["fm"] = FaceMeasurer()
        return measurer["fm"]

    def parse_day(s):
        try:
            d = date.fromisoformat(s) if s else date.today()
        except ValueError:
            abort(400)
        return min(d, date.today())

    def priorities_for(day_str):
        c = store.latest_checkin(day_str)
        if not c:
            return [], None
        a = c["assessment"]
        return priority_areas(a, flagged_metrics(a)), c

    def total_xp():
        return sum(daily.HABIT_BY_ID[r["habit"]]["xp"] for r in store.habit_log("0000")
                   if r["habit"] in daily.HABIT_BY_ID)

    @app.context_processor
    def inject():
        return dict(rank=daily.rank_for(total_xp()), comp_label=COMP_LABEL)

    @app.before_request
    def need_settings():
        if request.endpoint not in ("profile", "static") and "sex" not in store.settings():
            return redirect(url_for("profile", setup=1))

    # ------------------------------------------------------------ pages
    @app.get("/")
    def today():
        day = parse_day(request.args.get("d"))
        ds = day.isoformat()
        prios, _ = priorities_for(ds)
        plan = daily.plan_for(day, prios, store.settings()["sex"])
        done = store.habits_done(ds)
        checkin = store.checkin(ds)
        groups = [(key, label, [h for h in plan if h["slot"] == key]) for key, label in daily.SLOTS]
        hour = __import__("datetime").datetime.now().hour
        default_slot = "morning" if hour < 11 else "day" if hour < 18 else "evening"
        return render_template(
            "today.html", day=day, is_today=day == date.today(),
            prev=(day - timedelta(days=1)).isoformat(),
            next=(day + timedelta(days=1)).isoformat() if day < date.today() else None,
            plan=plan, groups=groups, done=done,
            n_done=sum(h["id"] in done for h in plan),
            xp_today=sum(h["xp"] for h in plan if h["id"] in done),
            xp_possible=sum(h["xp"] for h in plan),
            coach=daily.coach_line(plan, done, bool(checkin), day == date.today()),
            default_slot=default_slot, tip=daily.tip_for(day, prios),
            focus_areas=[H.AREA_ACTIONS[p]["title"].split(" (")[0] for p in prios[:2]])

    @app.get("/scan")
    def scan():
        day = parse_day(request.args.get("d"))
        ds = day.isoformat()
        c = store.checkin(ds)
        summary = None
        if c and c["assessment"]:
            a = c["assessment"]
            prios = priority_areas(a, flagged_metrics(a))
            plan = daily.plan_for(day, prios, store.settings()["sex"])
            top = prios[0] if prios else None
            summary = dict(
                a=a, top=H.AREA_ACTIONS[top]["title"].split(" (")[0] if top else None,
                top_why=H.AREA_ACTIONS[top]["why"].split(". ")[0] + "." if top else None,
                n_targeted=sum(h["targeted"] for h in plan),
                prios=[H.AREA_ACTIONS[p]["title"].split(" (")[0] for p in prios[:3]])
        return render_template("scan.html", day=day, is_today=day == date.today(),
                               checkin=c, s=summary)

    @app.post("/scan")
    def scan_upload():
        day = parse_day(request.form.get("day"))
        f = request.files.get("photo")
        if not f or not f.filename:
            return redirect(url_for("scan", d=day.isoformat()))
        img = decode_image(f.read())
        if img is None:
            return render_template("scan.html", day=day, is_today=day == date.today(), checkin=None,
                                   s=None, error="That file is not an image I can read. Try a JPEG or PNG.")
        scale = 1600 / max(img.shape[:2])          # phones shoot 12+ MP; landmarks need far less
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        ds = day.isoformat()
        name = f"{ds}.jpg"
        cv2.imwrite(str(store.photos / name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        s = store.settings()
        with lock:
            res = get_measurer().measure(img)
        if res is None:
            store.save_checkin(ds, name, None, None,
                               ["No face found. Face the camera in good light, with your whole face in frame."])
        else:
            metrics, shape, pts, crop = res
            eth = {"asian": "A", "caucasian": "C"}.get(s.get("ethnicity"))
            a = ref.assess(metrics, shape, s["sex"], eth)
            annotate(crop, pts, store.photos / f"{ds}_landmarks.jpg")
            store.save_checkin(ds, name, a, None, photo_warnings(metrics))
        store.set_habit(ds, "photo", True)
        return redirect(url_for("scan", d=ds))

    @app.get("/photo/<name>")
    def photo(name):
        return send_from_directory(store.photos, name)

    @app.get("/report/<day>")
    def report(day):
        d = parse_day(day)
        c = store.checkin(d.isoformat())
        if not c or not c["assessment"]:
            abort(404)
        a = c["assessment"]
        flags = flagged_metrics(a)
        prios = priority_areas(a, flags)
        measures = []
        for name, (label, area, expl) in METRICS.items():
            r = a["rating_corr_adj"][name]
            lo, hi = a["iqr"][name]
            measures.append(dict(label=label, expl=expl, value=a["adjusted"][name], lo=lo, hi=hi,
                                 pct=a["metric_pct"][name], r=r, matters=abs(r) >= R_MIN))
        measures.sort(key=lambda m: (not m["matters"], -abs(m["r"])))
        return render_template(
            "report.html", day=d, c=c, a=a, measures=measures,
            areas=[dict(key=p, **H.AREA_ACTIONS[p]) for p in prios[:4]],
            flags=flags, area_title={k: v["title"] for k, v in H.AREA_ACTIONS.items()},
            H=H, landmarks=f"{d.isoformat()}_landmarks.jpg")

    @app.get("/progress")
    def progress():
        today_ = date.today()
        since = (today_ - timedelta(days=89)).isoformat()
        sex = store.settings()["sex"]
        checkins = [c for c in store.checkins(since) if c["assessment"]]
        done_by_day = {}
        for r in store.habit_log(since):
            done_by_day.setdefault(r["day"], set()).add(r["habit"])

        grid, plans = [], {}
        for i in range(27, -1, -1):
            d = today_ - timedelta(days=i)
            plans[d] = {h["id"] for h in daily.plan_for(d, priorities_for(d.isoformat())[0], sex)}
            got = len(plans[d] & done_by_day.get(d.isoformat(), set()))
            grid.append(dict(day=d, pct=got / len(plans[d]) if plans[d] else 0, got=got, total=len(plans[d])))
        streak = 0
        for g in reversed(grid):
            if g["day"] == today_ and g["pct"] < 0.7:
                continue                         # today is still in progress
            if g["pct"] < 0.7:
                break
            streak += 1

        week = grid[-7:]
        week_pct = sum(g["got"] for g in week) / max(1, sum(g["total"] for g in week))
        stats = []
        for h in daily.HABITS:
            sched = [g for g in grid if h["id"] in plans[g["day"]]]
            if sched:
                got = sum(h["id"] in done_by_day.get(g["day"].isoformat(), set()) for g in sched)
                stats.append(dict(label=h["label"], got=got, total=len(sched), pct=got / len(sched)))
        stats.sort(key=lambda s: s["pct"])

        charts = []
        for key, label in [("overall", "Structure index")] + list(COMP_LABEL.items()):
            pts = [(c["day"], (c["assessment"]["overall"] if key == "overall"
                               else c["assessment"]["components"][key])["pct"]) for c in checkins]
            charts.append(dict(label=label, svg=trend_svg(pts, label), last=pts[-1][1] if pts else None))

        if not checkins and not any(done_by_day.values()):
            headline = "Nothing logged yet. Your first scan starts the timeline."
        elif stats:
            worst, best = stats[0], stats[-1]
            headline = (f"{week_pct:.0%} of quests done this week. Strongest: {best['label'].lower()}. "
                        f"Weakest: {worst['label'].lower()}.")
        else:
            headline = ""
        return render_template("progress.html", grid=grid, streak=streak, stats=stats,
                               charts=charts, photos=checkins[-14:], headline=headline,
                               week_pct=week_pct, n_scans=len(checkins))

    @app.route("/profile", methods=["GET", "POST"])
    def profile():
        if request.method == "POST":
            sex = request.form.get("sex")
            if sex not in ("M", "F"):
                abort(400)
            store.save_settings(sex=sex, ethnicity=request.form.get("ethnicity") or "")
            return redirect(url_for("today"))
        return render_template("profile.html", s=store.settings(), ranks=daily.RANKS,
                               setup=request.args.get("setup"))

    # ------------------------------------------------------------ API
    @app.post("/api/habit")
    def api_habit():
        j = request.get_json(force=True)
        if j.get("habit") not in daily.HABIT_BY_ID:
            abort(400)
        ds = parse_day(j.get("day")).isoformat()
        store.set_habit(ds, j["habit"], bool(j.get("done")))
        r = daily.rank_for(total_xp())
        return jsonify(ok=True, rank=r)

    return app


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="looksmax.web")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    print(f"Data folder: {Store().home}")
    print(f"Open http://{'127.0.0.1' if a.host == '0.0.0.0' else a.host}:{a.port}")
    create_app().run(host=a.host, port=a.port)
