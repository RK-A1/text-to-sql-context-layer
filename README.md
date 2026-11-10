# Text-to-SQL with and without a context layer

I wanted to know how much a context layer helps a text-to-SQL agent. A context layer is a file that a data team
writes once to explain what the tables mean, how they join and how metrics are computed. I gave one agent the 30
questions on BIRD Mini-Dev's `california_schools` database with four kinds of context, and graded every answer
twice: against the labels before and after Jin et al.'s [audit of BIRD](https://arxiv.org/abs/2601.08778), which
found errors in 52.8% of Mini-Dev. The model is DeepSeek V4.1 Flash, run three times per question.

## Results

RESULTS_PLACEHOLDER

## Setup

Every arm gets the table definitions and a `run_sql` tool for exploring the data. The `schema` arm gets nothing
else. The `dictionary` arm adds the data dictionary that BIRD ships with the database. The `hints` arm adds BIRD's
hint for each question, which no real user would supply. The `context` arm adds
[a context layer](context/california_schools.yaml) that I wrote by profiling the database. It is shorter than BIRD's
dictionary and corrects several things the dictionary gets wrong: it calls the `rtype` column that separates schools
from district totals "unuseful", it says K-12 enrollment starts at first grade, and its excellence-rate formula
truncates to zero under SQLite's integer division.

The original labels are the ones the audit started from. The corrected labels come from the audit's SQL-only
release, which changes the reference queries but not the questions, so the same answer can be graded against both.
On this database they give different answers to 9 of the 30 questions. Scoring is BIRD's execution accuracy with
floats rounded to 10 significant digits, because BIRD's strict version marks 0.904907975460123 wrong against
0.9049079754601227. Strict scores are in each run's `summary.md`.

## Limitations

Thirty questions on one database is a small sample, and each question is worth 3.3 points. The context layer isn't
blind: I wrote it after reading the paper and seeing some of these questions, although everything in it comes from
the data or the state's file documentation rather than from the questions. I changed it once before the main run,
to fix a false claim about the percentage columns. Some labels also depend on the hint. Question 11 defines total
enrollment as K-12 plus ages 5-17 enrollment, which counts most students twice, so an agent without the hint can't
match either label.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env    # add OPENROUTER_API_KEY
python -m bench.fetch_data
python -m bench.run --repeats 3 --label spike
python -m bench.report results/<run_dir>
```
