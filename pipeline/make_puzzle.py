"""Emit the static files the web app fetches.

  docs/data/meta.json                 salt + heat-tier thresholds, read once by the front end
  docs/data/vocab.json                every typeable form -> entry (autocomplete + reveal)
  docs/data/puzzles/YYYY-MM-DD.json   rank + score for every entry against that day's answer

Output goes to docs/ so the site can be published straight from GitHub Pages'
built-in "Deploy from a branch: /docs" mode, no build step or Actions run
required for the static parts.

Puzzle files are keyed by a salted hash of the entry id so the answer is not
readable by opening the file in devtools. This is obfuscation, not security: the
salt has to ship to the client to be usable, so a determined player can script
their way to the answer. Move scoring to a serverless endpoint if that matters.

    python pipeline/make_puzzle.py --days 30
    python pipeline/make_puzzle.py --date 2026-08-12
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta

import numpy as np

from lexicon import BUILD_DIR, ROOT, load_entries
from score import build_scores, load_config, rank_lists

PUBLIC_DATA = ROOT / "docs" / "data"
EPOCH = date(2026, 1, 1)
SALT = "gema-v1"


def key_for(entry_id: str, day: str) -> str:
    raw = f"{SALT}:{day}:{entry_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:12]


def answer_schedule(entries: list[dict]) -> list[dict]:
    """Deterministic answer order: easy entries first, shuffled within a tier."""
    answers = [e for e in entries if e["is_answer"]]
    return sorted(
        answers,
        key=lambda e: (e["difficulty"], hashlib.sha256((SALT + e["id"]).encode()).hexdigest()),
    )


def write_meta(cfg: dict, schedule_len: int) -> None:
    payload = {
        "version": 1,
        "salt": SALT,
        "epoch": EPOCH.isoformat(),
        "cycleLength": schedule_len,
        "heatTiers": cfg["heat_tiers"],
    }
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    path = PUBLIC_DATA / "meta.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    print(f"meta    -> {path.relative_to(ROOT)}")


def write_vocab(entries: list[dict]) -> None:
    payload = {
        "version": 1,
        "entries": [
            {
                "id": e["id"],
                "term": e["term"],
                "aliases": e["aliases"],
                "category": e["category"],
                "region": e["region"],
                "desc_en": e["desc_en"],
                "desc_ms": e["desc_ms"],
            }
            for e in entries
        ],
    }
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    path = PUBLIC_DATA / "vocab.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"vocab   {len(entries):>4} entries -> {path.relative_to(ROOT)} "
          f"({path.stat().st_size / 1024:.0f} KB)")


def write_puzzle(entries, scores, ranks, schedule, day: date) -> None:
    seq = (day - EPOCH).days
    if seq < 0:
        raise SystemExit(f"{day} precedes the epoch {EPOCH}")
    answer = schedule[seq % len(schedule)]
    ids = [e["id"] for e in entries]
    a = ids.index(answer["id"])
    iso = day.isoformat()

    table = {
        key_for(ids[j], iso): [int(ranks[a, j]), round(float(scores[a, j]) * 100, 1)]
        for j in range(len(ids))
    }
    payload = {
        "date": iso,
        "seq": seq,
        "total": len(ids),
        "answer": key_for(answer["id"], iso),
        "ranks": table,
    }
    out_dir = PUBLIC_DATA / "puzzles"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{iso}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    print(f"puzzle  {iso}  #{seq}  {answer['term']:<24} "
          f"{path.stat().st_size / 1024:>5.0f} KB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="single date, YYYY-MM-DD")
    ap.add_argument("--start", help="first date, defaults to today")
    ap.add_argument("--days", type=int, default=1)
    args = ap.parse_args()

    cfg = load_config()
    entries = load_entries()
    vecs = np.load(BUILD_DIR / "vectors.npy")
    scores = build_scores(entries, vecs, cfg)
    ranks = rank_lists(scores)
    schedule = answer_schedule(entries)

    write_meta(cfg, len(schedule))
    write_vocab(entries)
    print(f"answers {len(schedule):>4} eligible, cycle length {len(schedule)} days")

    if args.date:
        days = [date.fromisoformat(args.date)]
    else:
        start = date.fromisoformat(args.start) if args.start else date.today()
        days = [start + timedelta(days=i) for i in range(args.days)]

    for day in days:
        write_puzzle(entries, scores, ranks, schedule, day)


if __name__ == "__main__":
    main()
