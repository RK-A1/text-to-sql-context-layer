"""Run the questions through each arm and grade every answer against both reference labels.

Writes to results/<timestamp>_<label>/:
    run.json              settings, plus checksums of the questions and the context layer used
    calls.csv             one row per LLM call (rewritten after every call)
    answers.csv           one row per graded answer (arm, question, repeat)
    transcripts.jsonl.gz  full message history per answer, for reading failures

Spend is a project-wide ledger: every calls.csv under results/ counts toward SPEND_CAP.

Usage:
    python -m bench.run --scripted --label smoke     # offline pipeline test: submits the corrected SQL
    python -m bench.run --limit 3 --label smoke      # three questions per arm, live
    python -m bench.run --label spike                # all questions, every arm, once
    python -m bench.run --arms schema,context --repeats 3
"""

import argparse
import csv
import gzip
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from rich.console import Console

from . import providers
from .agent import TOOLS, answer, system_prompt, user_prompt
from .config import ARMS, CONTEXT_LAYER, MODEL, QUESTIONS, RESULTS_DIR, ROOT, SPEND_CAP
from .db import DB
from .grade import GRADES, Grader

console = Console()


def scripted_call(item):
    """Offline stand-in that runs, then submits, the corrected reference SQL."""
    def call(messages):
        n = sum(m["role"] == "assistant" for m in messages)
        name = ["run_sql", "submit_answer"][min(n, 1)]
        msg = {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"call_{n}", "type": "function",
             "function": {"name": name, "arguments": json.dumps({"sql": item["sql_corrected"]})}}]}
        return msg, {"served_model": "scripted", "finish_reason": "tool_calls", "cost_usd": 0.0}
    return call


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prior_spend():
    files = [f for f in RESULTS_DIR.glob("*/calls.csv") if f.stat().st_size]
    return sum(pd.read_csv(f)["cost_usd"].fillna(0).sum() for f in files)


class Run:
    """Shared state across arm threads: rows, files and the spend ledger."""

    def __init__(self, out_dir, cap):
        self.dir = out_dir
        self.calls, self.answers = [], []
        self.spent = prior_spend()
        self.cap = cap
        self.lock = threading.Lock()

    def budget_ok(self):
        return self.spent < self.cap

    def save(self, rows, name):
        fields = list(dict.fromkeys(k for r in rows for k in r))
        with (self.dir / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    def log_call(self, row):
        with self.lock:
            self.spent += row.get("cost_usd") or 0
            row["project_spend_usd"] = round(self.spent, 4)
            self.calls.append(row)
            self.save(self.calls, "calls.csv")

    def log_answer(self, row, messages):
        with self.lock:
            self.answers.append(row)
            self.save(self.answers, "answers.csv")
            with gzip.open(self.dir / "transcripts.jsonl.gz", "at") as f:
                f.write(json.dumps({k: row[k] for k in ("arm", "id", "repeat")} | {"messages": messages}) + "\n")


def run_arm(arm, items, repeats, run, scripted):
    db = DB()  # one connection per thread
    grader = Grader(db)
    system = system_prompt(arm, db.schema())
    for rep in range(1, repeats + 1):
        for item in items:
            if not run.budget_ok():
                console.print(f"[red]{arm}: spend cap ${run.cap} reached, stopping[/red]")
                return
            base = {"arm": arm, "id": item["id"], "repeat": rep}
            call = scripted_call(item) if scripted else (lambda m: providers.call(MODEL, m, TOOLS))
            on_call = lambda step, meta: run.log_call(
                {**base, "step": step, "ts": datetime.now().isoformat(timespec="seconds"), **meta})

            s, messages = answer(call, db, system, user_prompt(arm, item), on_call, run.budget_ok)
            correct, error = ({g: False for g in GRADES}, s.get("error") or s["end"])
            if s["final_sql"]:
                correct, error = grader.grade(item, s["final_sql"])
            run.log_answer({**base, "difficulty": item["difficulty"], "keys_disagree": item["keys_disagree"],
                            **{f"correct_{g}": correct[g] for g in GRADES}, "error": error, **s}, messages)
            marks = " ".join(f"{k[:4]}={'[green]ok[/green]' if correct[f'{k}_tol'] else '[red]x[/red]'}"
                             for k in ("original", "corrected"))
            console.print(f"{arm:<10} r{rep} q{item['id']:<4} {marks}  {s['end']:<10} steps={s['steps']} "
                          f"${s['cost_usd']:.4f}  (project ${run.spent:.3f})")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arms", default=",".join(ARMS), help=f"comma-separated, default all: {', '.join(ARMS)}")
    p.add_argument("--ids", help="comma-separated question ids (default: all)")
    p.add_argument("--limit", type=int, help="only the first N questions")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--label", default="run")
    p.add_argument("--scripted", action="store_true", help="offline: submit the corrected SQL, no API calls")
    args = p.parse_args()

    arms = args.arms.split(",")
    if unknown := [a for a in arms if a not in ARMS]:
        raise SystemExit(f"unknown arm(s): {unknown}")
    if not QUESTIONS.exists():
        raise SystemExit("no questions yet: run python -m bench.fetch_data")
    load_dotenv(ROOT / ".env")
    if not args.scripted and not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("set OPENROUTER_API_KEY in .env")

    items = json.loads(QUESTIONS.read_text())
    if args.ids:
        items = [q for q in items if q["id"] in args.ids.split(",")]
    items = items[:args.limit] if args.limit else items

    out = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{args.label}"
    out.mkdir(parents=True)
    (out / "run.json").write_text(json.dumps({
        "model": "scripted" if args.scripted else MODEL, "arms": arms, "repeats": args.repeats,
        "question_ids": [q["id"] for q in items], "started": datetime.now().isoformat(timespec="seconds"),
        "questions_sha256": sha256(QUESTIONS), "context_layer_sha256": sha256(CONTEXT_LAYER)}, indent=1))
    run = Run(out, SPEND_CAP)
    console.print(f"{len(arms)} arm(s) x {len(items)} question(s) x {args.repeats}; project spend so far "
                  f"${run.spent:.3f} of ${SPEND_CAP} -> {out.relative_to(ROOT)}")
    with ThreadPoolExecutor(len(arms)) as pool:
        for f in [pool.submit(run_arm, a, items, args.repeats, run, args.scripted) for a in arms]:
            f.result()
    console.print(f"\nDone. Project spend ${run.spent:.3f} of ${SPEND_CAP}. "
                  f"Report: python -m bench.report {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
