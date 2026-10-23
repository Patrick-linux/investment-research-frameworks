"""Local research notebook. Python 3.10+, standard library only.

Quick start:
  python research.py --db demo.sqlite add "Example Company" --body "Research question" --tags demo,software
  python research.py --db demo.sqlite list --query Example
  python research.py --db demo.sqlite show 1
  python research.py --db demo.sqlite edit 1 --body "Updated hypothesis"
  python research.py --db demo.sqlite evidence 1 --claim "Example claim" --source https://example.com --date 2026-10-23 --kind inference --falsifier "Counterexample"
  python research.py --db demo.sqlite diff 1 1 2
  python research.py --db demo.sqlite scenario --cash-flow 100 --growth 0.03 --discount 0.1 --terminal-growth 0.02 --years 5
  python research.py --db demo.sqlite export notebook.json --format json
  python research.py --db imported.sqlite import notebook.json
  python research.py selftest

Release 0.2.0 (2026-10-23): SQLite storage, revisions, search/tags,
evidence tracking, scenario calculator, JSON/CSV/Markdown export, JSON import.
No network requests, credentials, accounts, market data or trading operations.
Generated databases and exported notes may contain private data: keep them local.
MIT License; copyright (c) 2026 Patrick-linux. See repository README for license.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import io
import json
import math
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

VERSION = "0.2.0"
SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 tags TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisions (
 note_id INTEGER NOT NULL REFERENCES notes(id), version INTEGER NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, tags TEXT NOT NULL, created TEXT NOT NULL,
 PRIMARY KEY(note_id, version));
CREATE TABLE IF NOT EXISTS evidence (
 id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES notes(id),
 claim TEXT NOT NULL, source TEXT NOT NULL, published TEXT NOT NULL,
 kind TEXT NOT NULL, falsifier TEXT NOT NULL);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def required(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value.strip()


def tags_list(value):
    values = value.split(",") if isinstance(value, str) else value
    if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
        raise ValueError("tags must be comma-separated text or a list of strings")
    return sorted({x.strip().casefold() for x in values if x.strip()})


def checked_evidence(item):
    if not isinstance(item, dict):
        raise ValueError("evidence must be an object")
    claim = required(item.get("claim"), "claim")
    source = required(item.get("source"), "source")
    parts = urlsplit(source)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("source must be an HTTP(S) URL without embedded credentials")
    published = required(item.get("published"), "published date")
    if date.fromisoformat(published).isoformat() != published:
        raise ValueError("published date must be YYYY-MM-DD")
    kind = item.get("kind")
    if kind not in ("fact", "inference", "unknown"):
        raise ValueError("kind must be fact, inference, or unknown")
    falsifier = item.get("falsifier", "")
    if not isinstance(falsifier, str):
        raise ValueError("falsifier must be text")
    return dict(claim=claim, source=source, published=published, kind=kind, falsifier=falsifier)


class Notebook:
    def __init__(self, path):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def get(self, note_id):
        row = self.conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if row is None:
            raise ValueError(f"note {note_id} does not exist")
        item = dict(row)
        item["tags"] = json.loads(item["tags"])
        item["evidence"] = [dict(r) for r in self.conn.execute(
            "SELECT claim,source,published,kind,falsifier FROM evidence WHERE note_id=? ORDER BY id", (note_id,))]
        return item

    def _add(self, title, body, tags):
        title = required(title, "title")
        if not isinstance(body, str):
            raise ValueError("body must be text")
        encoded = json.dumps(tags_list(tags), ensure_ascii=False)
        stamp = now()
        cursor = self.conn.execute("INSERT INTO notes(title,body,tags,created,updated) VALUES(?,?,?,?,?)",
                                   (title, body, encoded, stamp, stamp))
        note_id = cursor.lastrowid
        self.conn.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?)", (note_id, 1, title, body, encoded, stamp))
        return note_id

    def add(self, title, body="", tags=""):
        with self.conn:
            return self._add(title, body, tags)

    def edit(self, note_id, title=None, body=None, tags=None):
        # Read and update inside a write transaction so concurrent edits cannot reuse a revision number.
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            old = self.get(note_id)
            title = old["title"] if title is None else required(title, "title")
            body = old["body"] if body is None else body
            if not isinstance(body, str):
                raise ValueError("body must be text")
            tag_values = old["tags"] if tags is None else tags_list(tags)
            if (title, body, tag_values) == (old["title"], old["body"], old["tags"]):
                self.conn.rollback()
                return False
            stamp, encoded = now(), json.dumps(tag_values, ensure_ascii=False)
            version = self.conn.execute("SELECT MAX(version)+1 FROM revisions WHERE note_id=?", (note_id,)).fetchone()[0]
            self.conn.execute("UPDATE notes SET title=?,body=?,tags=?,updated=? WHERE id=?", (title, body, encoded, stamp, note_id))
            self.conn.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?)", (note_id, version, title, body, encoded, stamp))
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def evidence(self, note_id, item):
        item = checked_evidence(item)
        with self.conn:
            self.get(note_id)
            self.conn.execute("INSERT INTO evidence(note_id,claim,source,published,kind,falsifier) VALUES(?,?,?,?,?,?)",
                              (note_id, *(item[k] for k in ("claim", "source", "published", "kind", "falsifier"))))
            self.conn.execute("UPDATE notes SET updated=? WHERE id=?", (now(), note_id))

    def search(self, query="", tag=None):
        # Literal substring search: SQL wildcard characters do not change semantics.
        result = []
        for row in self.conn.execute("SELECT id,title,body,tags,updated FROM notes ORDER BY id"):
            item = dict(row)
            item["tags"] = json.loads(item["tags"])
            if query.casefold() not in (item["title"] + "\n" + item["body"]).casefold():
                continue
            if tag and tag.strip().casefold() not in item["tags"]:
                continue
            result.append(item)
        return result

    def history(self, note_id):
        self.get(note_id)
        return [dict(row) for row in self.conn.execute("SELECT * FROM revisions WHERE note_id=? ORDER BY version", (note_id,))]

    def diff(self, note_id, before, after):
        versions = {r["version"]: r for r in self.history(note_id)}
        if before not in versions or after not in versions:
            raise ValueError("requested revision does not exist")
        def lines(v):
            r = versions[v]
            return (r["title"] + "\nTags: " + r["tags"] + "\n\n" + r["body"]).splitlines(keepends=True)
        return "".join(difflib.unified_diff(lines(before), lines(after), fromfile=f"v{before}", tofile=f"v{after}"))

    def snapshot(self):
        return {"format": "research-notebook", "version": 1,
                "notes": [self.get(row["id"]) for row in self.conn.execute("SELECT id FROM notes ORDER BY id")]}

    def import_json(self, payload):
        if not isinstance(payload, dict) or payload.get("format") != "research-notebook" or payload.get("version") != 1:
            raise ValueError("unsupported import format/version")
        notes = payload.get("notes")
        if not isinstance(notes, list):
            raise ValueError("notes must be a list")
        ids = []
        with self.conn:
            for item in notes:
                if not isinstance(item, dict) or not isinstance(item.get("evidence", []), list):
                    raise ValueError("invalid note or evidence list")
                checked = [checked_evidence(e) for e in item.get("evidence", [])]
                note_id = self._add(item.get("title"), item.get("body", ""), item.get("tags", []))
                for evidence in checked:
                    self.conn.execute("INSERT INTO evidence(note_id,claim,source,published,kind,falsifier) VALUES(?,?,?,?,?,?)",
                                      (note_id, *(evidence[k] for k in ("claim", "source", "published", "kind", "falsifier"))))
                ids.append(note_id)
        return ids


def scenario(cash_flow, growth, discount, terminal_growth, years):
    values = (cash_flow, growth, discount, terminal_growth)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("all scenario inputs must be finite")
    if cash_flow < 0 or growth <= -1 or discount <= -1 or terminal_growth <= -1:
        raise ValueError("cash flow must be nonnegative and rates greater than -1")
    if not isinstance(years, int) or not 1 <= years <= 100:
        raise ValueError("years must be an integer between 1 and 100")
    if discount <= terminal_growth:
        raise ValueError("discount rate must exceed terminal growth")
    flows, pv = [], 0.0
    for year in range(1, years + 1):
        flow = cash_flow * (1 + growth) ** year
        discounted = flow / (1 + discount) ** year
        pv += discounted
        flows.append({"year": year, "cash_flow": flow, "present_value": discounted})
    terminal = flows[-1]["cash_flow"] * (1 + terminal_growth) / (discount - terminal_growth)
    terminal_pv = terminal / (1 + discount) ** years
    total = pv + terminal_pv
    if not all(math.isfinite(v) for v in (pv, terminal_pv, total)):
        raise ValueError("scenario inputs overflowed; use smaller values")
    return {"cash_flow_unit": "same as input; not a per-share price", "years": flows,
            "explicit_present_value": pv, "terminal_present_value": terminal_pv, "total_present_value": total,
            "terminal_share": terminal_pv / total if total else 0,
            "assumptions": {"growth": growth, "discount": discount, "terminal_growth": terminal_growth},
            "limitations": "Constant growth illustration; no debt, dilution, taxes or probability weighting."}


def csv_cell(value):
    # Avoid formula execution when text exports are opened in spreadsheet software.
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r")) else value


def export_text(book, fmt):
    payload = book.snapshot()
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if fmt == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["id", "title", "body", "tags", "evidence_count"])
        for note in payload["notes"]:
            writer.writerow([note["id"], csv_cell(note["title"]), csv_cell(note["body"]), csv_cell(",".join(note["tags"])), len(note["evidence"])])
        return stream.getvalue()
    lines = ["# Research notebook export", ""]
    for note in payload["notes"]:
        lines += [f"## {note['title']}", "", "Tags: " + ", ".join(note["tags"]), "", note["body"], "", "### Evidence", ""]
        for e in note["evidence"]:
            lines += [f"- [{e['kind']}] {e['claim']}", f"  Source: {e['source']} ({e['published']})", f"  Falsifier: {e['falsifier']}"]
        lines.append("")
    return "\n".join(lines)


def selftest():
    class Tests(unittest.TestCase):
        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.book = Notebook(Path(self.temp.name) / "test.sqlite")
        def tearDown(self):
            self.book.close()
            self.temp.cleanup()
        def test_unicode_search_tags_and_literal_wildcard(self):
            self.book.add("虚构企业 100%", "a hypothesis", "Demo, demo,Research")
            self.assertEqual(len(self.book.search("100%", "DEMO")), 1)
            self.assertEqual(len(self.book.search("100_")), 0)
            self.assertEqual(self.book.get(1)["tags"], ["demo", "research"])
        def test_revisions_and_noop(self):
            self.book.add("Example", "old\n")
            self.assertFalse(self.book.edit(1, body="old\n"))
            self.book.edit(1, body="new\n")
            self.assertEqual(len(self.book.history(1)), 2)
            self.assertIn("+new", self.book.diff(1, 1, 2))
        def test_invalid_revision(self):
            self.book.add("Example")
            with self.assertRaises(ValueError): self.book.diff(1, 1, 9)
        def test_evidence_validation(self):
            self.book.add("Example")
            e = dict(claim="Claim", source="https://example.com/report", published="2026-10-23", kind="inference", falsifier="Counterevidence")
            self.book.evidence(1, e)
            self.assertEqual(len(self.book.get(1)["evidence"]), 1)
            for bad in ({"source": "file:///private"}, {"source": "https://user:pass@example.com"}, {"published": "wrong"}, {"kind": "certainty"}):
                with self.assertRaises(ValueError): self.book.evidence(1, {**e, **bad})
        def test_import_roundtrip_and_remapped_ids(self):
            self.book.add("Example", "body", "demo")
            self.assertEqual(self.book.import_json(self.book.snapshot()), [2])
            self.assertEqual(self.book.get(2)["body"], "body")
        def test_import_is_atomic(self):
            payload = {"format": "research-notebook", "version": 1, "notes": [{"title": "valid"}, {"title": ""}]}
            with self.assertRaises(ValueError): self.book.import_json(payload)
            self.assertEqual(self.book.search(), [])
        def test_missing_note(self):
            with self.assertRaises(ValueError): self.book.edit(999, body="x")
        def test_scenario_known_result(self):
            # Constant 100 perpetuity discounted at 10% must equal 1000.
            result = scenario(100, 0, .1, 0, 5)
            self.assertAlmostEqual(result["total_present_value"], 1000)
            self.assertEqual(scenario(0, 0, .1, 0, 5)["total_present_value"], 0)
        def test_scenario_rejects_invalid_assumptions(self):
            for args in [(100, 0, .02, .03, 5), (100, 0, .1, 0, 0), (-1, 0, .1, 0, 5), (100, float("nan"), .1, 0, 5)]:
                with self.assertRaises(ValueError): scenario(*args)
        def test_csv_formula_escaping(self):
            self.book.add("=1+1", " @SUM(A1)", "demo")
            rows = list(csv.reader(io.StringIO(export_text(self.book, "csv"))))
            self.assertEqual(rows[1][1], "'=1+1")
            self.assertTrue(rows[1][2].startswith("'"))
        def test_exports_include_evidence(self):
            self.book.add("Example", "Body", "demo")
            self.book.evidence(1, dict(claim="Claim", source="https://example.com", published="2026-10-23", kind="unknown"))
            self.assertIn("Claim", export_text(self.book, "md"))
            self.assertEqual(json.loads(export_text(self.book, "json"))["notes"][0]["evidence"][0]["kind"], "unknown")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    return 0 if result.wasSuccessful() else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--db", default="research.sqlite", help="Local SQLite file (never commit real notes)")
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("add"); p.add_argument("title"); p.add_argument("--body", default=""); p.add_argument("--tags", default="")
    p = subs.add_parser("edit"); p.add_argument("id", type=int); p.add_argument("--title"); p.add_argument("--body"); p.add_argument("--tags")
    p = subs.add_parser("list"); p.add_argument("--query", default=""); p.add_argument("--tag")
    for command in ("show", "history"):
        p = subs.add_parser(command); p.add_argument("id", type=int)
    p = subs.add_parser("diff"); p.add_argument("id", type=int); p.add_argument("before", type=int); p.add_argument("after", type=int)
    p = subs.add_parser("evidence"); p.add_argument("id", type=int)
    for field in ("claim", "source", "date"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--kind", choices=("fact", "inference", "unknown"), required=True); p.add_argument("--falsifier", default="")
    p = subs.add_parser("export"); p.add_argument("path"); p.add_argument("--format", choices=("json", "csv", "md"), default="json")
    p = subs.add_parser("import"); p.add_argument("path")
    p = subs.add_parser("scenario")
    for field in ("cash-flow", "growth", "discount", "terminal-growth"):
        p.add_argument("--" + field, type=float, required=True)
    p.add_argument("--years", type=int, default=5)
    subs.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "selftest": return selftest()
    book = None
    try:
        if args.command == "scenario":
            result = scenario(args.cash_flow, args.growth, args.discount, args.terminal_growth, args.years)
        else:
            book = Notebook(args.db)
            if args.command == "add": result = {"id": book.add(args.title, args.body, args.tags)}
            elif args.command == "edit": result = {"changed": book.edit(args.id, args.title, args.body, args.tags)}
            elif args.command == "list": result = book.search(args.query, args.tag)
            elif args.command == "show": result = book.get(args.id)
            elif args.command == "history": result = book.history(args.id)
            elif args.command == "diff":
                print(book.diff(args.id, args.before, args.after)); return 0
            elif args.command == "evidence":
                book.evidence(args.id, dict(claim=args.claim, source=args.source, published=args.date, kind=args.kind, falsifier=args.falsifier)); result = {"saved": True}
            elif args.command == "export":
                path = Path(args.path)
                if path.resolve() == Path(args.db).resolve(): raise ValueError("export cannot overwrite the database")
                # Never overwrite an existing export; an explicit new path is required.
                with path.open("x", encoding="utf-8", newline="") as stream: stream.write(export_text(book, args.format))
                result = {"exported": str(path)}
            elif args.command == "import":
                result = {"new_note_ids": book.import_json(json.loads(Path(args.path).read_text(encoding="utf-8-sig")))}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, sqlite3.Error, OverflowError) as exc:
        print(f"Error: {exc}", file=sys.stderr); return 2
    finally:
        if book is not None: book.close()


if __name__ == "__main__":
    raise SystemExit(main())
