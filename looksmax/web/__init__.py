"""Daily tracker web app: photo check-ins, daily plan, habit checklist, progress.

Run:  python -m looksmax.web            (http://127.0.0.1:8000)
      python -m looksmax.web --host 0.0.0.0   to open it from your phone on the same Wi-Fi
"""

import threading
from datetime import date, timedelta

import cv2
import markdown
import numpy as np
from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)

from .. import daily
from ..measure import FaceMeasurer
from ..reference import Reference
from ..report import (COMP_LABEL, annotate, flagged_metrics, photo_warnings,
                      priority_areas, render)
from ..habits import AREA_ACTIONS
from .charts import trend_svg
from .store import Store

MAX_UPLOAD_MB = 15


def create_app(store=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
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

    @app.before_request
    def need_settings():
        if request.endpoint not in ("settings", "static") and "sex" not in store.settings():
            return redirect(url_for("settings"))

    # ------------------------------------------------------------ pages
    @app.get("/")
    def today():
        day = parse_day(request.args.get("d"))
        ds = day.isoformat()
        sex = store.settings()["sex"]
        prios, source = priorities_for(ds)
        plan = daily.plan_for(day, prios, sex)
        done = store.habits_done(ds)
        checkin = store.checkin(ds)
        n_done = sum(h["id"] in done for h in plan)
        return render_template(
            "today.html", day=day, is_today=day == date.today(),
            prev=(day - timedelta(days=1)).isoformat(),
            next=(day + timedelta(days=1)).isoformat() if day < date.today() else None,
            plan=plan, done=done, n_done=n_done, checkin=checkin,
            priorities=[AREA_ACTIONS[p]["title"] for p in prios[:3]],
            priority_source=source["day"] if source else None,
            tip=daily.tip_for(day, prios), comp_label=COMP_LABEL)

    @app.post("/checkin")
    def checkin():
        day = parse_day(request.form.get("day"))
        f = request.files.get("photo")
        if not f or not f.filename:
            return redirect(url_for("today", d=day.isoformat()))
        img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            abort(400, "Could not read that image.")
        # downscale very large phone photos; landmarks don't need 12 MP
        scale = 1600 / max(img.shape[:2])
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        ds = day.isoformat()
        name = f"{ds}.jpg"
        cv2.imwrite(str(store.photos / name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])

        s = store.settings()
        with lock:
            res = get_measurer().measure(img)
        if res is None:
            store.save_checkin(ds, name, None, None, ["No face found. Use a clear, front-facing photo."])
        else:
            metrics, shape, pts = res
            eth = {"asian": "A", "caucasian": "C"}.get(s.get("ethnicity"))
            a = ref.assess(metrics, shape, s["sex"], eth)
            annotate(img, pts, store.photos / f"{ds}_landmarks.jpg")
            md = render(a, s["sex"], name, url_for("photo", name=f"{ds}_landmarks.jpg"))
            store.save_checkin(ds, name, a, md, photo_warnings(metrics))
        store.set_habit(ds, "photo", True)
        return redirect(url_for("today", d=ds))

    @app.get("/photo/<name>")
    def photo(name):
        return send_from_directory(store.photos, name)

    @app.get("/report/<day>")
    def report(day):
        c = store.checkin(parse_day(day).isoformat())
        if not c or not c["report"]:
            abort(404)
        html = markdown.markdown(c["report"], extensions=["tables"])
        return render_template("report.html", day=day, html=html)

    @app.get("/progress")
    def progress():
        today_ = date.today()
        since = (today_ - timedelta(days=89)).isoformat()
        sex = store.settings()["sex"]
        checkins = [c for c in store.checkins(since) if c["assessment"]]
        log = store.habit_log(since)

        # daily completion for the last 28 days
        done_by_day = {}
        for r in log:
            done_by_day.setdefault(r["day"], set()).add(r["habit"])
        grid, streak, counting = [], 0, True
        for i in range(27, -1, -1):
            d = today_ - timedelta(days=i)
            plan_day = daily.plan_for(d, priorities_for(d.isoformat())[0], sex)
            ids = {h["id"] for h in plan_day}
            got = len(ids & done_by_day.get(d.isoformat(), set()))
            grid.append(dict(day=d, pct=got / len(ids) if ids else 0, got=got, total=len(ids)))
        for g in reversed(grid):
            if g["day"] == today_ and g["pct"] < 0.7:
                continue                         # today still in progress
            if counting and g["pct"] >= 0.7:
                streak += 1
            else:
                counting = False

        # per-habit completion over the last 28 days
        stats = []
        for hid, label, *_ in daily.HABITS:
            sched = [g for g in grid if hid in {h["id"] for h in daily.plan_for(
                g["day"], priorities_for(g["day"].isoformat())[0], sex)}]
            if not sched:
                continue
            got = sum(hid in done_by_day.get(g["day"].isoformat(), set()) for g in sched)
            stats.append(dict(label=label, got=got, total=len(sched), pct=got / len(sched)))
        stats.sort(key=lambda s: s["pct"])

        charts = []
        for key, label in [("overall", "Structure index")] + list(COMP_LABEL.items()):
            pts = [(c["day"], (c["assessment"]["overall"] if key == "overall"
                               else c["assessment"]["components"][key])["pct"]) for c in checkins]
            charts.append(dict(label=label, svg=trend_svg(pts, label),
                               last=pts[-1][1] if pts else None))
        return render_template("progress.html", grid=grid, streak=streak, stats=stats,
                               charts=charts, photos=[c for c in checkins][-14:])

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "POST":
            sex = request.form.get("sex")
            if sex not in ("M", "F"):
                abort(400)
            store.save_settings(sex=sex, ethnicity=request.form.get("ethnicity") or "")
            return redirect(url_for("today"))
        return render_template("settings.html", s=store.settings())

    # ------------------------------------------------------------ API
    @app.post("/api/habit")
    def api_habit():
        j = request.get_json(force=True)
        if j.get("habit") not in daily.HABIT_IDS:
            abort(400)
        ds = parse_day(j.get("day")).isoformat()
        store.set_habit(ds, j["habit"], bool(j.get("done")))
        return jsonify(ok=True)

    return app


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="looksmax.web")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    print(f"Data folder: {Store().home}")
    create_app().run(host=a.host, port=a.port)
