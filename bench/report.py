"""Summarise one or more runs: accuracy per arm under each label, and where the two labels disagree.

EX is execution accuracy with floats compared to 10 significant digits; "strict" is BIRD's own
comparison (exact floats). See bench/grade.py.

Usage:
    python -m bench.report results/<run_dir> [results/<another_run_dir> ...]
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ARMS


def pct(s):
    return s.mean().mul(100).round(1)


def summarise(df):
    g = df.groupby("arm", sort=False)
    answered = df["final_sql"].notna()
    # Of the answers that read satscores, how many drop its district and county rows (rtype).
    sat = df[df["final_sql"].str.contains("satscores", case=False, na=False)]
    filters_rtype = sat["final_sql"].str.contains("rtype", case=False).groupby(sat["arm"])
    table = pd.DataFrame({
        "answers": g.size(),
        "EX original label": pct(g["correct_original_tol"]),
        "EX corrected label": pct(g["correct_corrected_tol"]),
        "strict, original": pct(g["correct_original"]),
        "strict, corrected": pct(g["correct_corrected"]),
        "no answer": (~answered).groupby(df["arm"]).sum(),
        "answered on last call": (answered & df.get("last_call", False)).groupby(df["arm"]).sum(),
        "SAT answers filtering rtype (%)": pct(filters_rtype),
        "cost per answer ($)": g["cost_usd"].mean().round(5),
        "total cost ($)": g["cost_usd"].sum().round(4),
    })
    return table.reindex([a for a in ARMS if a in table.index])


def disagreements(df):
    """On questions whose two labels give different answers: which label each answer matched."""
    d = df[df["keys_disagree"]]
    if d.empty:
        return pd.DataFrame()
    o, c = d["correct_original_tol"], d["correct_corrected_tol"]
    out = pd.DataFrame({"arm": d["arm"], "answers": 1, "matched original only": o & ~c,
                        "matched corrected only": ~o & c, "matched neither": ~o & ~c})
    out = out.groupby("arm", sort=False).sum().astype(int)
    return out.reindex([a for a in ARMS if a in out.index])


def leads(df, n=10_000, seed=0):
    """Each arm's lead over schema only on the corrected label, in points, with a 95% bootstrap
    interval that resamples questions (each question's score is its mean over repeats)."""
    c = df.pivot_table(index="id", columns="arm", values="correct_corrected_tol", aggfunc="mean") * 100
    if "schema" not in c:
        return pd.DataFrame()
    idx = np.random.default_rng(seed).integers(0, len(c), (n, len(c)))
    rows = {}
    for a in [a for a in ARMS if a in c and a != "schema"]:
        d = (c[a] - c["schema"]).to_numpy()
        boot = d[idx].mean(axis=1)
        rows[a] = {"lead over schema": d.mean(), "95% low": np.percentile(boot, 2.5),
                   "95% high": np.percentile(boot, 97.5)}
    return pd.DataFrame(rows).T.round(1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dirs", type=Path, nargs="+")
    args = p.parse_args()
    df = pd.concat(pd.read_csv(d / "answers.csv", dtype={"id": str}) for d in args.run_dirs)
    text = "\n".join([
        f"# {', '.join(d.name for d in args.run_dirs)}\n",
        "## Execution accuracy by arm (%)\n", summarise(df).to_markdown(), "",
        f"## The {df.loc[df.keys_disagree, 'id'].nunique()} questions whose two labels give different answers\n",
        disagreements(df).to_markdown(), "",
        "## Lead over schema only on the corrected label (points)\n", leads(df).to_markdown(), "",
    ])
    (args.run_dirs[-1] / "summary.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
