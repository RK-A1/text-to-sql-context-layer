"""The text-to-SQL agent: one loop and one set of tools for every arm. Only the context differs.

The agent explores with run_sql and ends by calling submit_answer with the one query whose
result answers the question. The grader re-runs that query, so prose answers are never parsed.
"""

import csv
import json
import re

from .config import CONTEXT_LAYER, DICTIONARY_DIR, MAX_STEPS

SYSTEM = """You answer questions about a SQLite database by writing SQL.

Use run_sql to explore the data and test your query. Then call submit_answer with one SQLite query. \
Its result is your answer, and it is compared row by row with a reference answer, so:
- Return only the columns the question asks for, in the order it asks for them. No extra columns.
- Don't round unless the question asks you to.

# Database schema

{schema}"""

DICTIONARY = """

# Data dictionary (shipped with the database)

{dictionary}"""

CONTEXT = """

# Context layer (written by the data team for this database)

{context}"""

NUDGE = "Please call submit_answer with the SQL query that answers the question."


def fn(name, description):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "required": ["sql"],
                       "properties": {"sql": {"type": "string", "description": "One read-only SQLite query."}}}}}


TOOLS = [
    fn("run_sql", "Run a read-only SQLite query and see up to 30 rows of its result."),
    fn("submit_answer", "Submit the final SQLite query. Its full result is your answer. Call this once, last."),
]


def dictionary_text():
    """BIRD's database_description CSVs as plain text, content unchanged apart from whitespace."""
    parts = []
    for path in sorted(DICTIONARY_DIR.glob("*.csv")):
        lines = [f"## {path.stem}"]
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                clean = {k.strip(): " ".join((v or "").split()) for k, v in row.items() if k}
                line = f"- {clean['original_column_name']}"
                if clean["column_name"]:
                    line += f" ({clean['column_name']})"
                line += f": {clean['column_description'] or '(no description)'} [{clean['data_format']}]"
                if clean["value_description"]:
                    line += f" Values: {clean['value_description']}"
                lines.append(line)
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def system_prompt(arm, schema):
    text = SYSTEM.format(schema=schema)
    if arm == "dictionary":
        text += DICTIONARY.format(dictionary=dictionary_text())
    elif arm == "context":
        text += CONTEXT.format(context=CONTEXT_LAYER.read_text().strip())
    return text


def user_prompt(arm, item):
    if arm == "hints" and item["evidence"].strip():
        return f"{item['question']}\n\nHint: {item['evidence']}"
    return item["question"]


def sql_from_text(text):
    """Fallback when a model answers in prose: take its last ```sql block."""
    blocks = re.findall(r"```(?:sql)?\s*(.*?)```", text or "", flags=re.DOTALL | re.IGNORECASE)
    return blocks[-1].strip() if blocks else None


def answer(call, db, system, question, on_call, budget_ok):
    """Run the tool loop for one question. Returns (summary, messages)."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    s = {"final_sql": None, "answer_source": None, "end": None, "steps": 0, "n_sql": 0, "n_failed_sql": 0,
         "nudged": False, "cost_usd": 0.0, "latency_s": 0.0, "prompt_tokens": 0, "completion_tokens": 0}

    for step in range(1, MAX_STEPS + 1):
        if not budget_ok():
            s["end"] = "spend_cap"
            break
        try:
            assistant, meta = call(messages)
        except Exception as e:
            on_call(step, {"error": f"{e.__class__.__name__}: {str(e)[:500]}"})
            s["end"], s["error"] = "api_error", f"{e.__class__.__name__}: {str(e)[:300]}"
            break
        s["steps"] = step
        for k in ("cost_usd", "latency_s", "prompt_tokens", "completion_tokens"):
            s[k] += meta.get(k) or 0
        on_call(step, meta)
        messages.append(assistant)

        calls = assistant.get("tool_calls") or []
        if not calls:
            if meta.get("finish_reason") == "length":
                s["end"] = "truncated"
                break
            if not s["nudged"]:
                s["nudged"] = True  # one reminder, reported as a failure mode
                messages.append({"role": "user", "content": NUDGE})
                continue
            if sql := sql_from_text(assistant.get("content")):
                s["final_sql"], s["answer_source"] = sql, "text"
            s["end"] = "text_answer" if sql else "no_answer"
            break

        for tc in calls:
            name = tc["function"]["name"]
            try:
                sql = str(json.loads(tc["function"]["arguments"] or "{}").get("sql", ""))
            except json.JSONDecodeError:
                result = "ERROR: arguments were not valid JSON."
            else:
                if name == "run_sql":
                    r = db.run_sql(sql)
                    s["n_sql"] += 1
                    s["n_failed_sql"] += not r["ok"]
                    result = r["text"]
                elif name == "submit_answer":
                    s["final_sql"], s["answer_source"] = sql, "submit"
                    result = "Submitted."
                else:
                    result = f"ERROR: unknown tool {name!r}."
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
        if s["answer_source"] == "submit":
            s["end"] = "submitted"
            break
    else:
        s["end"] = "max_steps"

    for k in ("cost_usd", "latency_s"):
        s[k] = round(s[k], 6)
    return s, messages
