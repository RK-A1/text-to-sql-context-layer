"""Paths, arms, model, limits and the budget. Everything a run depends on lives here."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the repo root
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"

DB_ID = "california_schools"
DB_PATH = DATA_DIR / DB_ID / f"{DB_ID}.sqlite"
DICTIONARY_DIR = DATA_DIR / DB_ID / "database_description"
QUESTIONS = DATA_DIR / "questions.json"
CONTEXT_LAYER = ROOT / "context" / f"{DB_ID}.yaml"

# One cheap model. BIRD's 2026 baseline puts it at 61% on Mini-Dev (SQLite), so there is room to improve.
MODEL = "openrouter/deepseek/deepseek-v4.1-flash"

# What the agent gets besides the question. Every arm also gets the table definitions and run_sql.
ARMS = {
    "schema": "table definitions only",
    "dictionary": "plus BIRD's data dictionary, as shipped with the database",
    "hints": "plus BIRD's hint for this question (the 'evidence' field)",
    "context": "plus the context layer in context/california_schools.yaml",
}

# Agent limits.
MAX_STEPS = 8           # LLM calls per question, plus one last call to submit
MAX_TOKENS = 8000       # per LLM call, reasoning included
ROW_CAP = 30            # rows shown to the model per run_sql
CHAR_CAP = 4000         # characters shown to the model per tool result
SQL_TIMEOUT_S = 30      # per query; BIRD's evaluation script uses 30 s too

# Hard stop for the whole project, in USD: every calls.csv under results/ counts toward it.
SPEND_CAP = 5.0
