"""Create labelled vector and raster scientific figures from saved baseline data.

Run: python make_visuals.py
Needs Pillow for PNG rendering (SVG is also saved). Figures use the same drawing
primitives in both formats. Numerical model and verification use standard Python.
"""

import json
from html import escape
from math import hypot, sqrt
from PIL import Image, ImageDraw, ImageFont
from hydraulic_model import HydraulicModel
import visual_style as theme

from project_paths import ROOT, RESULTS, FIGURES
HERE = FIGURES
NAVY, BLUE, TEAL, ORANGE, PURPLE = theme.INK, theme.SLATE, theme.SAGE, theme.PLUM, theme.GOLD
GRAY, GRID, RED = theme.MUTED, theme.LINE, theme.RED


class Figure:
    def __init__(self, width, height):
        self.im = Image.new("RGB", (width, height), "white")
        self.d = ImageDraw.Draw(self.im)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>']

    def text(self, x, y, label, size=24, color=NAVY, bold=False, anchor="start"):
        font = ImageFont.truetype(str(theme.font_path("bold" if bold else "regular")), size)
        self.d.text((x, y), label, font=font, fill=color, anchor={"start": "lt", "middle": "mt", "end": "rt"}[anchor])
        self.svg.append(f'<text x="{x}" y="{y}" dominant-baseline="hanging" text-anchor="{anchor}" font-family="Calibri,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(label)}</text>')

    def line(self, points, color=NAVY, width=3, dashed=False):
        if dashed:
            distance_along_path = 0.0
            for (x1, y1), (x2, y2) in zip(points, points[1:]):
                length = hypot(x2-x1, y2-y1)
                if length == 0:
                    continue
                offset = 0.0
                while offset < length-1e-8:
                    phase = (distance_along_path+offset) % 16
                    on = phase < 9
                    end = min(length, offset + (9-phase if on else 16-phase))
                    if on:
                        self.d.line([(x1+(x2-x1)*offset/length, y1+(y2-y1)*offset/length),
                                     (x1+(x2-x1)*end/length, y1+(y2-y1)*end/length)], fill=color, width=width)
                    offset = end
                distance_along_path += length
        else:
            self.d.line(points, fill=color, width=width, joint="curve")
        dash = ' stroke-dasharray="9 7"' if dashed else ""
        coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        self.svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}"{dash}/>')

    def box(self, x, y, w, h, fill=theme.PALE, stroke=GRID):
        self.d.rectangle([x, y, x+w, y+h], fill=fill, outline=stroke, width=2)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')

    def dot(self, x, y, r=7, color=NAVY, fill=None):
        self.d.ellipse([x-r, y-r, x+r, y+r], fill=fill or color, outline=color, width=3)
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill or color}" stroke="{color}" stroke-width="3"/>')

    def arrow(self, x1, y1, x2, y2, color=NAVY, width=4):
        self.line([(x1, y1), (x2, y2)], color, width)
        dx, dy = x2-x1, y2-y1
        L = hypot(dx, dy)
        ux, uy = dx/L, dy/L
        pts = [(x2, y2), (x2-14*ux+6*uy, y2-14*uy-6*ux),
               (x2-14*ux-6*uy, y2-14*uy+6*ux), (x2, y2)]
        self.line(pts, color, width)

    def save(self, stem):
        self.im.save(HERE / f"{stem}.png")
        (HERE / f"{stem}.svg").write_text("\n".join(self.svg+["</svg>"]), encoding="utf-8")


def axes(fig, x0, y0, w, h):
    def xy(Q_m3_h, H_m):
        return x0+w*Q_m3_h/210, y0+h*(1-H_m/36)
    for x in range(0, 211, 30):
        xx, _ = xy(x, 0)
        fig.line([(xx, y0), (xx, y0+h)], GRID, 1)
        fig.text(xx, y0+h+12, str(x), 21, anchor="middle")
    for y in range(0, 37, 6):
        _, yy = xy(0, y)
        fig.line([(x0, yy), (x0+w, yy)], GRID, 1)
        fig.text(x0-15, yy-10, str(y), 21, anchor="end")
    fig.line([(x0, y0), (x0, y0+h), (x0+w, y0+h)], NAVY, 2)
    fig.text(x0, y0-38, "Head (m water)", 22)
    fig.text(x0+w/2, y0+h+53, "Total loop flow Q (m³/h)", 24, anchor="middle")
    return xy


def curve(fig, xy, fn, color, dashed=False):
    points = []
    for i in range(601):
        Q = i*210/600
        H = fn(Q)
        if 0 <= H <= 36:
            points.append(xy(Q, H))
        elif len(points) > 1:
            fig.line(points, color, 3, dashed)
            points = []
    if len(points) > 1:
        fig.line(points, color, 3, dashed)


def legend(fig, x, y, color, label, dashed=False):
    fig.line([(x, y+11), (x+45, y+11)], color, 4, dashed)
    fig.text(x+58, y, label, 21)


def plot(model, results):
    fig = Figure(1800, 1110)
    fig.text(55, 30, "Fixed-speed hydraulic baseline", 38, bold=True)
    fig.text(55, 82, "Illustrative pump curves and losses · 1 MW coil load · 5 K water rise · 1450 rpm", 24, GRAY)
    fig.text(105, 142, "Full load: gross pump head and net header head", 26, bold=True)
    fig.text(1000, 142, "Valve throttling and staging at partial load", 26, bold=True)
    left, right = axes(fig, 105, 235, 680, 470), axes(fig, 1000, 235, 680, 470)
    Qd_h = model.Q_design*3600
    u = lambda Q: Q/Qd_h
    curve(fig, left, lambda Q: 32-8*u(Q)**2, GRAY, True)
    curve(fig, left, lambda Q: 32-10*u(Q)**2, BLUE)
    curve(fig, left, lambda Q: 20*u(Q)**2, TEAL, True)
    curve(fig, left, lambda Q: 22*u(Q)**2, ORANGE)
    full = next(r for r in results["normal_fixed_speed"] if r["load_fraction"] == 1)
    fig.dot(*left(Qd_h, 22), r=8, color=ORANGE)
    fig.dot(*left(Qd_h, 24), r=7, color=GRAY)
    q_open = results["diagnostics_not_all_admissible"]["two_pumps_valves_fully_open"]
    fig.dot(*left(q_open["achieved_flow_m3_h"], q_open["header_head_m"]), r=7, color=TEAL, fill="white")
    curve(fig, right, lambda Q: 32-40*u(Q)**2, GRAY, True)
    curve(fig, right, lambda Q: 32-10*u(Q)**2, BLUE)
    for row, color in zip(results["normal_fixed_speed"], [PURPLE, RED, TEAL, ORANGE]):
        R = model.R_passive + row["valve_R_s2_m5"]
        curve(fig, right, lambda Q, R=R: R*(Q/3600)**2, color)
        fig.dot(*right(row["achieved_flow_m3_h"], row["header_head_m"]), r=7, color=color)
        x, y = right(row["achieved_flow_m3_h"], row["header_head_m"])
        fig.text(x+12, y-31, f"{row['load_fraction']:.0%}", 22, color, True)
    legend(fig, 105, 810, GRAY, "2 pumps: gross H at q = Q/2", True)
    legend(fig, 105, 850, BLUE, "2 pumps: net H after branch loss")
    legend(fig, 105, 890, TEAL, "Shared system: valves fully open", True)
    legend(fig, 105, 930, ORANGE, "Shared system: full-load valve setting")
    legend(fig, 1000, 810, GRAY, "1 pump: net H (diagnostic continuation)", True)
    legend(fig, 1000, 850, BLUE, "2 pumps: net H")
    legend(fig, 1000, 890, PURPLE, "25%: 1 pump; valve dissipates 28.375 m")
    legend(fig, 1000, 930, RED, "50%: 1 pump; valve dissipates 17.500 m")
    legend(fig, 1000, 970, TEAL, "75%: 2 pumps; valve dissipates 16.250 m")
    fig.text(105, 978, f"Controlled: {Qd_h:.2f} m³/h · 24 m gross · 22 m header", 21, ORANGE, True)
    fig.text(105, 1014, f"Two pumps, valves fully open: {q_open['achieved_flow_m3_h']:.2f} m³/h", 21, TEAL)
    fig.text(55, 1066, "Dots mark controlled operating points. Permitted flow per pump: 0.45–1.20 × speed-scaled BEP; some curve extensions lie outside this range.", 21, GRAY)
    fig.save("baseline_curves")


def schematic():
    fig = Figure(1800, 970)
    fig.text(55, 30, "Closed chilled-water distribution loop", 38, bold=True)
    fig.text(55, 82, "System boundary: secondary water loop and pumps; primary plant and CRAH air side excluded", 24, GRAY)
    fig.box(75, 175, 1650, 620, fill="white", stroke=GRID)
    # Pump manifold: identical individual branches share the same S and D nodes.
    fig.line([(160, 280), (160, 660)], BLUE, 5)
    fig.line([(650, 280), (650, 490)], BLUE, 5)
    for i, y in enumerate([280, 385, 490]):
        color = BLUE if i < 2 else GRAY
        fig.line([(160, y), (650, y)], color, 4, dashed=i == 2)
        for x, label, width in [(205, "IV", 65), (315, f"P{i+1}", 95), (450, "CV →", 95), (570, "IV", 65)]:
            fig.box(x, y-24, width, 48, fill="white", stroke=color)
            fig.text(x+width/2, y-13, label, 23, color, True, anchor="middle")
        fig.text(315, y+35, "duty" if i < 2 else "standby", 21, color)
    fig.dot(160, 385, 9, BLUE)
    fig.dot(650, 385, 9, BLUE)
    fig.text(124, 350, "S", 25, BLUE, True)
    fig.text(672, 350, "D", 25, BLUE, True)
    fig.text(190, 208, "Three identical pump branches in parallel", 25, bold=True)
    fig.text(190, 566, "Each running branch: 2 m loss at 86.03 m³/h", 22)
    fig.text(190, 602, "IV: isolation valve; CV: discharge check valve", 22, GRAY)
    # Shared loop; plant HX is downstream of pumps, before coil inlet.
    fig.line([(650, 385), (720, 385), (720, 270), (790, 270)], BLUE, 5)
    fig.arrow(735, 270, 785, 270, BLUE)
    fig.box(790, 220, 230, 100, fill=theme.PALE, stroke=BLUE)
    fig.text(905, 238, "Plant HX", 28, BLUE, True, anchor="middle")
    fig.text(905, 280, "secondary loss: 4 m", 20, BLUE, anchor="middle")
    fig.arrow(1020, 270, 1120, 270, BLUE)
    fig.text(1040, 224, "12.5°C", 22, BLUE)
    fig.box(1120, 220, 260, 100, fill=theme.PAPER, stroke=TEAL)
    fig.text(1250, 238, "CRAH coil bank", 25, TEAL, True, anchor="middle")
    fig.text(1250, 280, "coil loss: 8 m", 22, TEAL, anchor="middle")
    fig.line([(1380, 270), (1510, 270), (1510, 385)], ORANGE, 5)
    fig.arrow(1510, 320, 1510, 382, ORANGE)
    fig.text(1540, 315, "17.5°C", 24, ORANGE)
    fig.box(1380, 385, 260, 100, fill=theme.PALE, stroke=ORANGE)
    fig.text(1510, 402, "Equivalent two-way", 25, ORANGE, True, anchor="middle")
    fig.text(1510, 438, "control valve", 25, ORANGE, True, anchor="middle")
    fig.line([(1510, 485), (1510, 660), (160, 660)], ORANGE, 5)
    fig.arrow(1170, 660, 1080, 660, ORANGE)
    fig.arrow(230, 660, 165, 660, ORANGE)
    fig.arrow(160, 625, 160, 550, ORANGE)
    fig.text(1020, 535, "Valve: 2 m fully open; 4 m at full-load setting", 22)
    fig.text(735, 604, "Shared supply/return pipes, fittings and headers: 6 m total", 23)
    fig.text(760, 712, "All head budgets are illustrative at design flow; losses scale with flow².", 22, GRAY)
    fig.text(1100, 137, "External plant: adequate heat rejection; supply maintained", 23, BLUE, anchor="middle")
    fig.line([(905, 165), (905, 220)], BLUE, 3, True)
    fig.text(1245, 346, "+1 MW from hall at full load", 22, TEAL, anchor="middle")
    # Expansion connection is a closed dead leg at pump suction, not an open reservoir.
    fig.line([(160, 660), (160, 730), (280, 730)], GRAY, 3)
    fig.box(280, 697, 260, 65, fill=theme.PALE, stroke=GRAY)
    fig.text(410, 710, "Closed expansion / fill", 22, GRAY, anchor="middle")
    fig.text(80, 830, "Full-load references: Q = 172.05 m³/h; qP1 = qP2 = 86.03 m³/h; HP = 24 m; HD−HS = 22 m.", 25, bold=True)
    fig.text(80, 875, "Failed branch isolated; standby replaces its duty position. Standby check valve prevents reverse flow when off.", 23)
    fig.text(80, 918, "Coil and valve blocks represent a balanced parallel terminal bank. The layout shows the hydraulic model's connections.", 23, GRAY)
    fig.save("cooling_loop_schematic")


if __name__ == "__main__":
    assumptions = json.loads((ROOT/"assumptions.json").read_text(encoding="utf-8"))
    results = json.loads((RESULTS/"baseline_results.json").read_text(encoding="utf-8"))
    plot(HydraulicModel(assumptions), results)
    schematic()
    print("Saved baseline_curves and cooling_loop_schematic in PNG and SVG.")
