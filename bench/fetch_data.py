"""Download the databases and both answer keys, check them, and write data/questions.json.

Sources (each file pinned by SHA-256):
- BIRD Mini-Dev (June 2024 release, minidev.zip): the eleven SQLite databases and their
  database_description CSVs, read with HTTP range requests so the zip is never downloaded whole.
  Checksums are in bench/checksums.json.
- The SQL-only corrected answer key from Jin et al., "Pervasive Annotation Errors Break Text-to-SQL
  Benchmarks and Leaderboards" (VLDB 2026), pinned to a commit of their repo.

Each question gets two reference queries:
- sql_original:  the answer before the paper's audit (BIRD Mini-Dev with Arcwise's community fixes,
                 the version the authors started from)
- sql_corrected: the answer after the audit

Usage:
    python -m bench.fetch_data
"""

import hashlib
import io
import json
import urllib.request
import zipfile

from .config import CHECKSUMS, DATA_DIR, DBS, QUESTIONS
from .db import DB

BIRD_ZIP = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
ZIP_DIR = "minidev/MINIDEV/"
BIRD_QUESTIONS = ("mini_dev_sqlite.json", DATA_DIR / "raw" / "bird_mini_dev_sqlite_2024.json",
                  "4ba5fa8de55856222f484d380d2ba872b380bf79d825de70478e2120cb0fc43b")


def bird_files():
    """Path inside the zip -> (local path, sha256)."""
    files = {name: (DATA_DIR / name.removeprefix("dev_databases/"), digest)
             for name, digest in json.loads(CHECKSUMS.read_text()).items()}
    name, path, digest = BIRD_QUESTIONS
    return files | {name: (path, digest)}


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
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


def fetch_bird():
    todo = {name: (path, digest) for name, (path, digest) in bird_files().items()
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
    """Keep a question only if both reference queries run under the grader's own rules (read-only,
    SQL_TIMEOUT_S) and the corrected one returns rows: an empty answer would match any empty result."""
    bird = {str(e["question_id"]): e for e in json.loads(BIRD_QUESTIONS[1].read_text())}
    dbs = {db: DB(db) for db in DBS}
    questions, dropped = [], []
    for e in labels:
        q = {"id": e["question_id"], "db": e["db_id"], "difficulty": bird[e["question_id"]]["difficulty"],
             "question": e["question"], "evidence": e["evidence"],
             "sql_original": e.get("original_SQL", e["SQL"]), "sql_corrected": e["SQL"]}
        try:
            original, corrected = (set(dbs[q["db"]].query(q[f"sql_{k}"])[1]) for k in ("original", "corrected"))
        except Exception as ex:
            dropped.append(f"{q['db']} {q['id']} ({str(ex).strip() or type(ex).__name__})")
            continue
        if not corrected:
            dropped.append(f"{q['db']} {q['id']} (empty answer)")
            continue
        q["sql_changed"] = "original_SQL" in e
        q["keys_disagree"] = original != corrected  # the two keys give different answers
        questions.append(q)
    return questions, dropped


def main():
    fetch_bird()
    questions, dropped = build_questions(fetch_paper_labels())
    QUESTIONS.write_text(json.dumps(questions, indent=1))
    print(f"{len(questions)} questions in {len({q['db'] for q in questions})} databases "
          f"-> {QUESTIONS.relative_to(DATA_DIR.parent)}")
    print(f"  dropped {len(dropped)}: {'; '.join(dropped) or 'none'}")
    print(f"  corrected SQL differs from the original on {sum(q['sql_changed'] for q in questions)}")
    print(f"  ... and returns a different result on {sum(q['keys_disagree'] for q in questions)}")


if __name__ == "__main__":
    main()
