"""Check the lexicon against the schema invariants.

    python pipeline/validate.py
"""
from __future__ import annotations

import sys
from collections import Counter

from lexicon import build_lookup, load_entries, validate


def main() -> None:
    entries = load_entries()
    errors, warnings = validate(entries)

    for warning in warnings:
        print(f"warn  {warning}")
    for error in errors:
        print(f"ERROR {error}")

    answers = [e for e in entries if e["is_answer"]]
    print()
    print(f"entries          {len(entries)}")
    print(f"answer-eligible  {len(answers)}")
    print(f"typeable forms   {len(build_lookup(entries))}")
    print(f"categories       {dict(Counter(e['category'] for e in entries).most_common())}")
    print(f"difficulty       {dict(sorted(Counter(e['difficulty'] for e in entries).items()))}")
    print(f"distinct tags    {len({t for e in entries for t in e['tags']})}")

    if errors:
        print(f"\n{len(errors)} error(s)")
        sys.exit(1)
    print("\nlexicon ok")


if __name__ == "__main__":
    main()
