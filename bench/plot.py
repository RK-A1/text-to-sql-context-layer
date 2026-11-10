"""Draw the README chart: accuracy per arm under the original and the corrected label.

A dumbbell per arm: the same answers, graded against each label. Writes a light and a dark SVG,
which the README switches between with <picture>.

Usage:
    python -m bench.plot results/<run_dir> [results/<another_run_dir> ...]
"""

import argparse
from html import escape
from pathlib import Path

import pandas as pd

from .config import ARMS, ROOT

OUT = ROOT / "docs"
NAMES = {"schema": "Schema only", "dictionary": "+ BIRD data dictionary",
         "hints": "+ BIRD hint per question", "context": "+ Context layer"}
THEMES = {  # chart surface, ink, gridline, connector, original label, corrected label
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9",
                  link="#c3c2b7", original="#86b6ef", corrected="#1c5cab"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a",
                 link="#383835", original="#256abf", corrected="#86b6ef"),
}
W, LEFT, RIGHT, TOP, ROW = 720, 200, 56, 128, 44


def title(scores):
    if "hints" in scores and round(scores["hints"][0] - scores["hints"][1]) > 0:
        return f"Correcting the labels costs BIRD's hints {scores['hints'][0] - scores['hints'][1]:.0f} points"
    return "Accuracy by context, graded against both labels"


def svg(scores, n_questions, n_runs, t):
    x = lambda v: LEFT + v / 100 * (W - LEFT - RIGHT)
    h = TOP + ROW * len(scores) + 44
    font = 'font-family="system-ui, -apple-system, Segoe UI, sans-serif"'
    desc = "; ".join(f"{NAMES[a]}: original {o:.0f}%, corrected {c:.0f}%" for a, (o, c) in scores.items())
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" {font}>',
           f"<title>Execution accuracy by context, original vs corrected label</title><desc>{escape(desc)}</desc>",
           f'<rect width="{W}" height="{h}" rx="8" fill="{t["surface"]}"/>',
           f'<text x="24" y="36" font-size="17" font-weight="600" fill="{t["ink"]}">'
           f"{escape(title(scores))}</text>",
           f'<text x="24" y="58" font-size="13" fill="{t["ink2"]}">BIRD california_schools, {n_questions} '
           f"questions × {n_runs} runs, DeepSeek V4.1 Flash. Execution accuracy, %.</text>"]
    for i, (key, label) in enumerate([("original", "Original label"), ("corrected", "Corrected label")]):
        lx = 24 + i * 150
        out += [f'<circle cx="{lx + 6}" cy="84" r="6" fill="{t[key]}"/>',
                f'<text x="{lx + 18}" y="88.5" font-size="13" fill="{t["ink2"]}">{label}</text>']
    bottom = TOP + ROW * len(scores) - ROW / 2 + 12
    for v in (0, 25, 50, 75, 100):
        out += [f'<line x1="{x(v)}" y1="{TOP - 18}" x2="{x(v)}" y2="{bottom}" stroke="{t["grid"]}" stroke-width="1"/>',
                f'<text x="{x(v)}" y="{bottom + 18}" font-size="12" text-anchor="middle" fill="{t["muted"]}">{v}</text>']
    for r, (arm, (orig, corr)) in enumerate(scores.items()):
        y = TOP + r * ROW
        out += [f'<text x="{LEFT - 16}" y="{y + 4.5}" font-size="13" text-anchor="end" fill="{t["ink"]}">'
                f"{escape(NAMES[arm])}</text>",
                f'<line x1="{x(orig)}" y1="{y}" x2="{x(corr)}" y2="{y}" stroke="{t["link"]}" stroke-width="2"/>']
        for key, v in (("original", orig), ("corrected", corr)):
            out.append(f'<circle cx="{x(v):.1f}" cy="{y}" r="6" fill="{t[key]}" stroke="{t["surface"]}" stroke-width="2"/>')
        # Label each end on its outer side; dots too close for two labels share one.
        def label(v, right, text):
            out.append(f'<text x="{x(v) + (12 if right else -12):.1f}" y="{y + 4.5}" font-size="12" '
                       f'text-anchor="{"start" if right else "end"}" fill="{t["ink"]}">{text}</text>')
        if round(corr) == round(orig):
            label(max(orig, corr), True, f"{corr:.0f}%, both labels")
        elif abs(x(corr) - x(orig)) < 16:
            label(max(orig, corr), True, f"{orig:.0f}% → {corr:.0f}%")
        else:
            label(orig, orig > corr, f"{orig:.0f}%")
            label(corr, corr > orig, f"{corr:.0f}%")
    out.append("</svg>")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dirs", type=Path, nargs="+")
    args = p.parse_args()
    df = pd.concat(pd.read_csv(d / "answers.csv", dtype={"id": str}) for d in args.run_dirs)
    g = df.groupby("arm")
    means = g[["correct_original_tol", "correct_corrected_tol"]].mean().mul(100)
    scores = {a: tuple(means.loc[a]) for a in ARMS if a in means.index}
    OUT.mkdir(exist_ok=True)
    for theme, suffix in (("light", ""), ("dark", "-dark")):
        path = OUT / f"accuracy{suffix}.svg"
        path.write_text(svg(scores, df["id"].nunique(), df["repeat"].nunique(), THEMES[theme]))
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
