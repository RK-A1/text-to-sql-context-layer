"""Run the questions through each arm and grade every answer against both answer keys.

Writes to results/<timestamp>_<label>/:
    run.json              settings, plus checksums of the questions and the context layers used
    calls.csv             one row per LLM call (rewritten after every call)
    answers.csv           one row per graded answer (arm, database, question, repeat)
    transcripts.jsonl.gz  full message history per answer, for reading failures

Spend is a project-wide ledger: every calls.csv under results/ counts toward SPEND_CAP.

Usage:
    python -m bench.run --scripted --label smoke             # offline pipeline test: submits the corrected SQL
    python -m bench.run --limit 2 --label smoke              # two questions per database and arm, live
    python -m bench.run --label main                         # every question, every arm, once
    python -m bench.run --dbs superhero --arms schema,context
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
from .agent import TOOLS, answer, system_prompt
from .config import ARMS, DBS, MODEL, QUESTIONS, RESULTS_DIR, ROOT, SPEND_CAP, context_layer
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
    """Shared state across worker threads: rows, files and the spend ledger."""

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
                f.write(json.dumps({k: row[k] for k in ("arm", "db", "id", "repeat")} | {"messages": messages}) + "\n")


def run_task(arm, db_id, items, repeats, run, scripted):
    """One arm on one database: every question, every repeat, in order."""
    db = DB(db_id)  # one connection per thread
    grader = Grader(db)
    system = system_prompt(arm, db_id, db.schema())
    for rep in range(1, repeats + 1):
        for item in items:
            if not run.budget_ok():
                console.print(f"[red]{arm}/{db_id}: spend cap ${run.cap} reached, stopping[/red]")
                return
            base = {"arm": arm, "db": db_id, "id": item["id"], "repeat": rep}
            call = scripted_call(item) if scripted else (lambda m: providers.call(MODEL, m, TOOLS))
            on_call = lambda step, meta: run.log_call(
                {**base, "step": step, "ts": datetime.now().isoformat(timespec="seconds"), **meta})

            s, messages = answer(call, db, system, item["question"], on_call, run.budget_ok)
            correct, error = ({g: False for g in GRADES}, s.get("error") or s["end"])
            if s["final_sql"]:
                correct, error = grader.grade(item, s["final_sql"])
            run.log_answer({**base, "difficulty": item["difficulty"], "keys_disagree": item["keys_disagree"],
                            **{f"correct_{g}": correct[g] for g in GRADES}, "error": error, **s}, messages)
            mark = "[green]ok[/green]" if correct["corrected_tol"] else "[red]x[/red]"
            console.print(f"{arm:<10} {db_id[:18]:<18} r{rep} q{item['id']:<5} {mark}  {s['end']:<10} "
                          f"steps={s['steps']} ${s['cost_usd']:.4f}  (project ${run.spent:.3f})")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arms", default=",".join(ARMS), help=f"comma-separated, default all: {', '.join(ARMS)}")
    p.add_argument("--dbs", default=",".join(DBS), help="comma-separated databases, default all eleven")
    p.add_argument("--ids", help="comma-separated question ids (default: all)")
    p.add_argument("--limit", type=int, help="only the first N questions of each database")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--workers", type=int, default=12, help="arm-database pairs run in parallel")
    p.add_argument("--label", default="run")
    p.add_argument("--scripted", action="store_true", help="offline: submit the corrected SQL, no API calls")
    args = p.parse_args()

    arms, dbs = args.arms.split(","), args.dbs.split(",")
    if unknown := [a for a in arms if a not in ARMS] + [d for d in dbs if d not in DBS]:
        raise SystemExit(f"unknown arm(s) or database(s): {unknown}")
    if not QUESTIONS.exists():
        raise SystemExit("no questions yet: run python -m bench.fetch_data")
    if "context" in arms and (missing := [d for d in dbs if not context_layer(d).exists()]):
        raise SystemExit(f"no context layer for: {missing}")
    load_dotenv(ROOT / ".env")
    if not args.scripted and not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("set OPENROUTER_API_KEY in .env")

    items = json.loads(QUESTIONS.read_text())
    if args.ids:
        items = [q for q in items if q["id"] in args.ids.split(",")]
    by_db = {d: [q for q in items if q["db"] == d] for d in dbs}
    by_db = {d: (qs[:args.limit] if args.limit else qs) for d, qs in by_db.items() if qs}

    out = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{args.label}"
    out.mkdir(parents=True)
    (out / "run.json").write_text(json.dumps({
        "model": "scripted" if args.scripted else MODEL, "arms": arms, "repeats": args.repeats,
        "question_ids": {d: [q["id"] for q in qs] for d, qs in by_db.items()},
        "started": datetime.now().isoformat(timespec="seconds"), "questions_sha256": sha256(QUESTIONS),
        "context_layer_sha256": {d: sha256(context_layer(d)) for d in by_db if context_layer(d).exists()}},
        indent=1))
    run = Run(out, SPEND_CAP)
    n = sum(len(qs) for qs in by_db.values())
    console.print(f"{len(arms)} arm(s) x {n} question(s) in {len(by_db)} database(s) x {args.repeats}; "
                  f"project spend so far ${run.spent:.3f} of ${SPEND_CAP} -> {out.relative_to(ROOT)}")
    with ThreadPoolExecutor(args.workers) as pool:
        tasks = [pool.submit(run_task, a, d, qs, args.repeats, run, args.scripted)
                 for d, qs in by_db.items() for a in arms]
        for f in tasks:
            f.result()
    console.print(f"\nDone. Project spend ${run.spent:.3f} of ${SPEND_CAP}. "
                  f"Report: python -m bench.report {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
