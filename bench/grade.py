"""Execution accuracy (EX), two ways.

strict: exactly BIRD's evaluation script. An answer is correct when the set of row tuples it
        returns equals the set the reference query returns. Row order and duplicate rows don't
        count; column order and exact values do. Kept for comparability with BIRD's leaderboard.
tol:    the same, after rounding every float to 10 significant digits. Strict EX marks a stored
        0.904907975460123 wrong against a computed 0.9049079754601227; this variant does not.
"""

KEYS = ("original", "corrected")


def rounded(row):
    return tuple(float(f"{v:.10g}") if isinstance(v, float) else v for v in row)


def results_match(predicted_rows, reference_rows, tolerant=False):
    if tolerant:
        return {rounded(r) for r in predicted_rows} == {rounded(r) for r in reference_rows}
    return set(predicted_rows) == set(reference_rows)


class Grader:
    def __init__(self, db):
        self.db = db
        self.reference = {}  # (question id, key) -> rows

    def grade(self, item, sql):
        """Return ({'original': .., 'corrected': .., 'original_tol': .., 'corrected_tol': ..}, error).

        A query that fails or times out is wrong under every key.
        """
        try:
            _, rows, _ = self.db.query(sql)
        except Exception as e:
            return {k: False for k in GRADES}, f"final SQL failed: {str(e).strip().splitlines()[0][:200]}"
        out = {}
        for k in KEYS:
            if (item["id"], k) not in self.reference:
                self.reference[item["id"], k] = self.db.query(item[f"sql_{k}"])[1]
            out[k] = results_match(rows, self.reference[item["id"], k])
            out[f"{k}_tol"] = results_match(rows, self.reference[item["id"], k], tolerant=True)
        return out, None


GRADES = ("original", "corrected", "original_tol", "corrected_tol")
