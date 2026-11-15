"""Voice rule (Nov. 15, 2026): I am the author, so the repo speaks in first person. No page refers to me in
the third person, and none shows scratch paths or tool names. A byline with my full name is fine."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".md", ".py", ".html", ".json", ".yaml", ".yml", ".toml", ".cff", ".txt"}
SKIP_DIRS = {".git", ".venv", "data", "__pycache__", ".pytest_cache", "node_modules"}
FIRST = "Dy" + "lan"
BAD = [
    (re.compile(FIRST + r"(?: Fanelli)?['’]s\b"), "possessive of my own name: write 'my'"),
    (re.compile(r"\b" + FIRST + r" (?![A-Z])"), "my first name as the subject: write 'I'"),
    (re.compile(r"(?<!Fanelli, )\b" + FIRST + r"[.,;:)]"), "my first name alone: write 'I' or 'me'"),
    (re.compile(r"/home/" + "claude|/tmp/" + "claude|/home/" + "user/"), "a scratch path from another machine"),
    (re.compile(r"\b(?:" + "Clau" + "de|Anth" + "ropic|sub" + "agent|Web" + "Fetch|Web" + "Search)\b"), "a tool name"),
    (re.compile("Co-Authored" + "-By"), "an attribution trailer"),
]


def _files():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in SUFFIXES and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS):
            yield p


def test_first_person_and_no_tooling():
    hits = []
    for p in _files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        for rx, why in BAD:
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{p.relative_to(ROOT)}:{line}: {why}: {text[max(0, m.start() - 30):m.end() + 30]!r}")
    assert not hits, "\n".join(hits[:40])


def test_the_rule_catches_what_it_should():
    bad = [FIRST + "'s decision", FIRST + " asked for this", "at the request of " + FIRST + ".", "/home/" + "claude/x"]
    good = ["Written 2026-11-15; " + FIRST + " Fanelli; Data", "Fanelli, " + FIRST + "</div>", FIRST + " Cease, RHP", "Chart: " + FIRST + " Fanelli"]
    assert all(any(rx.search(s) for rx, _ in BAD) for s in bad)
    assert not any(rx.search(s) for rx, _ in BAD for s in good)
