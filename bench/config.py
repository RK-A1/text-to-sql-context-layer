"""Paths, arms, model, limits and the budget. Everything a run depends on lives here."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the repo root
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"

# All eleven BIRD Mini-Dev databases.
DBS = ["california_schools", "card_games", "codebase_community", "debit_card_specializing", "european_football_2",
       "financial", "formula_1", "student_club", "superhero", "thrombosis_prediction", "toxicology"]
QUESTIONS = DATA_DIR / "questions.json"
CHECKSUMS = ROOT / "bench" / "checksums.json"  # sha256 of every file fetched from BIRD


def db_path(db):
    return DATA_DIR / db / f"{db}.sqlite"


def dictionary_dir(db):
    return DATA_DIR / db / "database_description"


def context_layer(db):
    return ROOT / "context" / f"{db}.yaml"


# One cheap model. BIRD's 2026 baseline puts it at 61% on Mini-Dev (SQLite), so there is room to improve.
MODEL = "openrouter/deepseek/deepseek-v4.1-flash"

# What the agent gets besides the question. Every arm also gets the table definitions and run_sql.
ARMS = {
    "schema": "table definitions only",
    "dictionary": "plus BIRD's data dictionary, as shipped with the database",
    "context": "plus the context layer in context/<db>.yaml",
}

# Agent limits.
MAX_STEPS = 8           # LLM calls per question, plus one last call to submit
MAX_TOKENS = 8000       # per LLM call, reasoning included
ROW_CAP = 30            # rows shown to the model per run_sql
CHAR_CAP = 4000         # characters shown to the model per tool result
SQL_TIMEOUT_S = 30      # per query; BIRD's evaluation script uses 30 s too

# Hard stop for the whole project, in USD: every calls.csv under results/ counts toward it.
SPEND_CAP = 10.0
