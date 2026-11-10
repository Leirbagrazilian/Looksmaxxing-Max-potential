"""Small inline-SVG charts (no JavaScript chart library needed)."""

from datetime import date
from html import escape


def trend_svg(points, label, width=320, height=140):
    """Percentile (0-100) over time: faint dots for each day, a line for the
    7-check-in rolling average. points = [(date_str, value), ...]"""
    if not points:
        return '<p class="muted">No check-ins yet.</p>'
    pad_l, pad_r, pad_t, pad_b = 28, 10, 10, 22
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    days = [date.fromisoformat(d) for d, _ in points]
    d0, d1 = days[0], days[-1]
    span = max((d1 - d0).days, 1)

    def x(d):
        return pad_l + (w / 2 if d0 == d1 else (d - d0).days / span * w)

    def y(v):
        return pad_t + (1 - v / 100) * h

    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="{escape(label)} over time">']
    for g in (0, 50, 100):
        out.append(f'<line class="grid" x1="{pad_l}" x2="{pad_l + w}" y1="{y(g):.1f}" y2="{y(g):.1f}"/>'
                   f'<text class="axis" x="{pad_l - 6}" y="{y(g) + 3:.1f}" text-anchor="end">{g}</text>')
    out.append(f'<text class="axis" x="{pad_l}" y="{height - 6}">{d0:%b %d}</text>')
    if d1 != d0:
        out.append(f'<text class="axis" x="{pad_l + w}" y="{height - 6}" text-anchor="end">{d1:%b %d}</text>')

    vals = [v for _, v in points]
    roll = [sum(vals[max(0, i - 6):i + 1]) / len(vals[max(0, i - 6):i + 1]) for i in range(len(vals))]
    if len(points) > 1:
        path = " ".join(f"{'M' if i == 0 else 'L'}{x(d):.1f},{y(v):.1f}" for i, (d, v) in enumerate(zip(days, roll)))
        out.append(f'<path class="line" d="{path}"/>')
    for d, v, r in zip(days, vals, roll):
        out.append(f'<g class="pt"><circle class="hit" cx="{x(d):.1f}" cy="{y(v):.1f}" r="9"/>'
                   f'<circle class="dot" cx="{x(d):.1f}" cy="{y(v):.1f}" r="4"/>'
                   f'<title>{d:%a %b %d}: {v:.0f} (7-day avg {r:.0f})</title></g>')
    out.append("</svg>")
    return "".join(out)
