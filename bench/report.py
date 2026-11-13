"""Summarise a run: accuracy per arm, overall and per database, and the context layer's lead.

The headline comparison, fixed before the main run: the context arm minus the schema arm, graded
against the corrected answer key, over every question, with a 95% bootstrap interval that resamples
questions. Everything else here is secondary.

EX is execution accuracy with floats compared to 10 significant digits; "strict" is BIRD's own
comparison (exact floats). See bench/grade.py.

Usage:
    python -m bench.report results/<run_dir>
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ARMS

COMPARISONS = [("context", "schema"), ("context", "dictionary"), ("dictionary", "schema")]


def pct(s):
    return s.mean().mul(100).round(1)


def ordered(table):
    return table.reindex([a for a in ARMS if a in table.index])


def summarise(df):
    g = df.groupby("arm")
    return ordered(pd.DataFrame({
        "answers": g.size(),
        "EX corrected key": pct(g["correct_corrected_tol"]),
        "EX original key": pct(g["correct_original_tol"]),
        "strict, corrected": pct(g["correct_corrected"]),
        "no answer": df["final_sql"].isna().groupby(df["arm"]).sum(),
        "answered on last call": (df["final_sql"].notna() & df["last_call"]).groupby(df["arm"]).sum(),
        "cost per answer ($)": g["cost_usd"].mean().round(5),
        "total cost ($)": g["cost_usd"].sum().round(3),
    }))


def per_question(df):
    """Rows: (db, question). Columns: arm. Values: share of repeats correct on the corrected key, in %."""
    return df.pivot_table(index=["db", "id"], columns="arm", values="correct_corrected_tol", aggfunc="mean") * 100


def leads(q, n=10_000, seed=0):
    """Paired differences between arms, in points, with 95% intervals from resampling questions."""
    idx = np.random.default_rng(seed).integers(0, len(q), (n, len(q)))
    rows = {}
    for a, b in COMPARISONS:
        if a in q and b in q:
            d = (q[a] - q[b]).to_numpy()
            boot = d[idx].mean(axis=1)
            rows[f"{a} - {b}"] = {"lead": d.mean(), "95% low": np.percentile(boot, 2.5),
                                  "95% high": np.percentile(boot, 97.5),
                                  "questions won": int((d > 0).sum()), "questions lost": int((d < 0).sum())}
    return pd.DataFrame(rows).T.round(1)


def by_database(q):
    """Accuracy per arm per database, and the headline lead per database with its interval."""
    out = q.groupby(level="db").mean().round(1)[[a for a in ARMS if a in q]]
    out.insert(0, "questions", q.groupby(level="db").size())
    if {"context", "schema"} <= set(q):
        ci = {db: leads(sub[["context", "schema"]], n=5_000).iloc[0] for db, sub in q.groupby(level="db")}
        ci = pd.DataFrame(ci).T
        out["context - schema"] = ci["lead"]
        out["95% low"], out["95% high"] = ci["95% low"], ci["95% high"]
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", type=Path)
    args = p.parse_args()
    df = pd.read_csv(args.run_dir / "answers.csv", dtype={"id": str})
    q = per_question(df)
    text = "\n".join([
        f"# {args.run_dir.name}\n",
        "## Execution accuracy by arm (%)\n", summarise(df).to_markdown(), "",
        f"## Leads on the corrected key, {len(q)} questions (points)\n", leads(q).to_markdown(), "",
        "## By database, corrected key (%)\n", by_database(q).to_markdown(), "",
    ])
    (args.run_dir / "summary.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
