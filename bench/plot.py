"""Draw the README chart: why BIRD's dictionary beat the context layer.

Reads docs/context_vs_dictionary.csv, my reading of every question that exactly one of the two arms
answered right, checks that it covers exactly those questions in the run, and draws one row per
reason: the dictionary's wins to the left, the context layer's to the right. Writes a light and a
dark SVG, which the README switches between with <picture>.

Usage:
    python -m bench.plot results/<run_dir>
"""

import argparse
from html import escape
from pathlib import Path

import pandas as pd

from .config import ROOT

OUT = ROOT / "docs"
CLASSIFICATION = OUT / "context_vs_dictionary.csv"
REASONS = {  # reason in the CSV -> row label
    "key uses a definition only BIRD's dictionary gives": "The answer key uses a definition only BIRD's dictionary gives",
    "key reads the question more narrowly than the layer advises": "The answer key reads the question more narrowly than my layer advises",
    "layer adds a fact the key uses": "My layer supplies a fact the answer key relies on",
    "agent slip": "Agent slip: an extra column, rounding, a cut-off answer, wrong logic",
}
THEMES = {  # categorical slots 1 and 2 of the dataviz reference palette
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", axis="#c3c2b7",
                  dictionary="#2a78d6", context="#eb6834"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", axis="#52514e",
                 dictionary="#3987e5", context="#d95926"),
}
W, TOP, ROW, BAR = 720, 116, 58, 18


def load(run_dir):
    a = pd.read_csv(run_dir / "answers.csv", dtype={"id": str})
    p = a.pivot_table(index="id", columns="arm", values="correct_corrected_tol", aggfunc="first")
    disagree = p[p["dictionary"] != p["context"]]
    c = pd.read_csv(CLASSIFICATION, dtype={"question_id": str}).set_index("question_id")
    if set(c.index) != set(disagree.index) or any(c.loc[i, "right"] != ("dictionary" if disagree.loc[i, "dictionary"]
                                                                       else "context") for i in c.index):
        raise SystemExit(f"{CLASSIFICATION.name} does not match the run's disagreements")
    return c.groupby(["reason", "right"]).size().unstack(fill_value=0).reindex(REASONS, fill_value=0)


def svg(counts, t):
    mid, half = W / 2, W / 2 - 64
    scale = half / max(30, counts.to_numpy().max())
    h = TOP + ROW * len(counts) + 12
    n_dict, n_ctx = int(counts["dictionary"].sum()), int(counts["context"].sum())
    font = 'font-family="system-ui, -apple-system, Segoe UI, sans-serif"'
    desc = "; ".join(f"{label}: dictionary {int(r['dictionary'])}, context layer {int(r['context'])}"
                     for label, (_, r) in zip(REASONS.values(), counts.iterrows()))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" {font}>',
           f"<title>Why BIRD's dictionary beat my context layer</title><desc>{escape(desc)}</desc>",
           f'<rect width="{W}" height="{h}" rx="8" fill="{t["surface"]}"/>',
           f'<text x="24" y="36" font-size="17" font-weight="600" fill="{t["ink"]}">Why BIRD\'s dictionary beat my context layer</text>',
           f'<text x="24" y="58" font-size="13" fill="{t["ink2"]}">The {n_dict + n_ctx} questions that exactly one of '
           f'the two answered right, by reason.</text>',
           f'<rect x="{mid - 22}" y="80" width="12" height="12" rx="2" fill="{t["dictionary"]}"/>',
           f'<text x="{mid - 30}" y="90.5" font-size="13" text-anchor="end" fill="{t["ink2"]}">BIRD\'s dictionary right ({n_dict})</text>',
           f'<rect x="{mid + 10}" y="80" width="12" height="12" rx="2" fill="{t["context"]}"/>',
           f'<text x="{mid + 30}" y="90.5" font-size="13" fill="{t["ink2"]}">My context layer right ({n_ctx})</text>']
    for i, (label, (_, r)) in enumerate(zip(REASONS.values(), counts.iterrows())):
        y = TOP + i * ROW
        out.append(f'<text x="24" y="{y + 10}" font-size="13" fill="{t["ink"]}">{escape(label)}</text>')
        by = y + 20
        out.append(f'<line x1="{mid}" y1="{by - 4}" x2="{mid}" y2="{by + BAR + 4}" stroke="{t["axis"]}" stroke-width="1"/>')
        for arm, sign in (("dictionary", -1), ("context", 1)):
            n = int(r[arm])
            w = n * scale
            x0 = mid if sign > 0 else mid - w
            if n:
                out.append(f'<rect x="{x0:.1f}" y="{by}" width="{w:.1f}" height="{BAR}" rx="3" fill="{t[arm]}"/>')
            tx = mid + sign * (w + 8)
            out.append(f'<text x="{tx:.1f}" y="{by + 13}" font-size="12" text-anchor="{"start" if sign > 0 else "end"}" '
                       f'fill="{t["ink"] if n else t["muted"]}">{n}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", type=Path)
    args = p.parse_args()
    counts = load(args.run_dir)
    for theme, suffix in (("light", ""), ("dark", "-dark")):
        path = OUT / f"disagreements{suffix}.svg"
        path.write_text(svg(counts, THEMES[theme]))
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
