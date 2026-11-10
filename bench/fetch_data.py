"""Download the database and both answer keys, check them, and write data/questions.json.

Sources (each pinned by SHA-256):
- BIRD Mini-Dev (June 2024 release, minidev.zip). Only the california_schools files are fetched,
  with HTTP range requests, so the 800 MB zip is never downloaded in full.
- The SQL-only corrected labels from Jin et al., "Pervasive Annotation Errors Break Text-to-SQL
  Benchmarks and Leaderboards" (VLDB 2026), pinned to a commit of their repo.

Each question gets two reference queries:
- sql_original:  the label before the paper's audit (BIRD Mini-Dev with Arcwise's community fixes,
                 the version the authors started from)
- sql_corrected: the label after the audit

Usage:
    python -m bench.fetch_data
"""

import hashlib
import io
import json
import sqlite3
import urllib.request
import zipfile

from .config import DATA_DIR, DB_ID, DB_PATH, DICTIONARY_DIR, QUESTIONS

BIRD_ZIP = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
ZIP_DIR = "minidev/MINIDEV/"
BIRD_FILES = {  # path inside the zip -> (local path, sha256)
    f"dev_databases/{DB_ID}/{DB_ID}.sqlite":
        (DB_PATH, "c0903eec662e63068fd1d14403d3d6c1d473287fc10c4356333ea58f878db983"),
    f"dev_databases/{DB_ID}/database_description/frpm.csv":
        (DICTIONARY_DIR / "frpm.csv", "f2c3fa53a02c5d711866a192f580c6a545389192a096441767f40d72ffa41334"),
    f"dev_databases/{DB_ID}/database_description/satscores.csv":
        (DICTIONARY_DIR / "satscores.csv", "a44145158100894387d05a96987c487e3c83742892b13127b486de309bb8f138"),
    f"dev_databases/{DB_ID}/database_description/schools.csv":
        (DICTIONARY_DIR / "schools.csv", "f18d96abf47892e4bd8094dd47d6978ea6bbc11821eccdf91f3f54dd1685979f"),
    "mini_dev_sqlite.json":
        (DATA_DIR / "raw" / "bird_mini_dev_sqlite_2024.json",
         "4ba5fa8de55856222f484d380d2ba872b380bf79d825de70478e2120cb0fc43b"),
}
PAPER_COMMIT = "fe766045c55b6875a43b30e9ac7683df5582f8cf"
PAPER_LABELS = (
    f"https://raw.githubusercontent.com/uiuc-kang-lab/text_to_sql_benchmarks/{PAPER_COMMIT}"
    "/data/arcwise_plat_sql_only_with_diff.json",
    DATA_DIR / "raw" / "arcwise_plat_sql_only_with_diff.json",
    "e7bf76408f99266506ea558d84982c69422e5db3dfecab5f08a3a8d3900e8395",
)


class HTTPRangeFile(io.RawIOBase):
    """A read-only, seekable file over HTTP range requests, enough for zipfile."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        head = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60)
        self.size = int(head.headers["Content-Length"])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, buf):
        if self.pos >= self.size or not len(buf):
            return 0
        end = min(self.pos + len(buf), self.size) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        data = urllib.request.urlopen(req, timeout=600).read()
        buf[:len(data)] = data
        self.pos += len(data)
        return len(data)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_bird():
    todo = {name: (path, digest) for name, (path, digest) in BIRD_FILES.items()
            if not (path.exists() and sha256(path) == digest)}
    if not todo:
        return
    with zipfile.ZipFile(io.BufferedReader(HTTPRangeFile(BIRD_ZIP), buffer_size=1 << 20)) as z:
        for name, (path, digest) in todo.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(ZIP_DIR + name) as src, path.open("wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            if sha256(path) != digest:
                raise SystemExit(f"checksum mismatch for {name}")
            print(f"fetched {name}")


def fetch_paper_labels():
    url, path, digest = PAPER_LABELS
    if not (path.exists() and sha256(path) == digest):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(url, timeout=120).read())
        if sha256(path) != digest:
            raise SystemExit("checksum mismatch for the paper's labels")
        print("fetched the paper's labels")
    return json.loads(path.read_text())


def build_questions(labels):
    bird = {str(e["question_id"]): e for e in json.loads(BIRD_FILES["mini_dev_sqlite.json"][0].read_text())}
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    result = lambda sql: set(con.execute(sql).fetchall())  # BIRD's comparison: a set of row tuples

    questions = []
    for e in labels:
        if e["db_id"] != DB_ID:
            continue
        q = {"id": e["question_id"], "difficulty": bird[e["question_id"]]["difficulty"],
             "question": e["question"], "evidence": e["evidence"],
             "sql_original": e.get("original_SQL", e["SQL"]), "sql_corrected": e["SQL"]}
        original, corrected = result(q["sql_original"]), result(q["sql_corrected"])
        if not original or not corrected:
            raise SystemExit(f"question {q['id']}: a reference query returns no rows")
        q["sql_changed"] = "original_SQL" in e
        q["keys_disagree"] = original != corrected  # the two labels give different answers
        q["original_matches_bird_2024"] = original == result(bird[q["id"]]["SQL"])
        questions.append(q)
    return questions


def main():
    fetch_bird()
    questions = build_questions(fetch_paper_labels())
    QUESTIONS.write_text(json.dumps(questions, indent=1))
    n = len(questions)
    print(f"{n} {DB_ID} questions -> {QUESTIONS.relative_to(DATA_DIR.parent)}")
    print(f"  corrected SQL differs from the original on {sum(q['sql_changed'] for q in questions)}")
    print(f"  ... and returns a different result on {sum(q['keys_disagree'] for q in questions)}")
    print(f"  original label returns a different result from BIRD's 2024 release on "
          f"{sum(not q['original_matches_bird_2024'] for q in questions)}")


if __name__ == "__main__":
    main()
