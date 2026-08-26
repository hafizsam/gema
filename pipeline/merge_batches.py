"""One-shot merge of lexicon/batches/*.json into lexicon/entries.json.

Agent-authored batches can collide with each other or with the existing
lexicon (same dish under a different id, a region value outside our enum,
etc). This applies fixes deterministically and logs every change instead of
silently accepting or dropping data.

    python pipeline/merge_batches.py            # dry run, prints a report
    python pipeline/merge_batches.py --write     # writes lexicon/entries.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lexicon import ENTRIES_PATH, ROOT, load_entries, normalize, validate

BATCHES_DIR = ROOT / "lexicon" / "batches"

VALID_REGIONS = {
    "kedah", "penang", "perak", "selangor", "kuala-lumpur", "negeri-sembilan",
    "melaka", "johor", "pahang", "terengganu", "kelantan", "perlis",
    "sabah", "sarawak", "labuan", "putrajaya",
}
# Batches occasionally used a broader/looser region than our per-state enum.
REGION_FIXUP = {
    "borneo": None, "peninsular": None, "east-coast": None,
}


def load_batches() -> list[dict]:
    entries = []
    for path in sorted(BATCHES_DIR.glob("*.json")):
        entries.extend(json.loads(path.read_text(encoding="utf-8")))
    return entries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    existing = load_entries()
    candidates = load_batches()

    seen_ids = {e["id"] for e in existing}
    seen_surfaces: dict[str, str] = {}
    for e in existing:
        for surface in [e["term"], *e["aliases"]]:
            seen_surfaces[normalize(surface)] = e["id"]

    merged = list(existing)
    dropped_dupe_id, dropped_dupe_surface, fixed_region = [], [], []

    for cand in candidates:
        if cand["id"] in seen_ids:
            dropped_dupe_id.append(cand["id"])
            continue

        surfaces = [cand["term"], *cand["aliases"]]
        keys = [normalize(s) for s in surfaces]
        collision = next((k for k in keys if k in seen_surfaces), None)
        if collision:
            dropped_dupe_surface.append(f"{cand['id']} (clashes with {seen_surfaces[collision]})")
            continue

        if cand.get("region") in REGION_FIXUP:
            fixed_region.append(f"{cand['id']}: {cand['region']!r} -> null")
            cand["region"] = REGION_FIXUP[cand["region"]]
        elif cand.get("region") is not None and cand["region"] not in VALID_REGIONS:
            fixed_region.append(f"{cand['id']}: {cand['region']!r} -> null (unknown region)")
            cand["region"] = None

        seen_ids.add(cand["id"])
        for k in keys:
            seen_surfaces[k] = cand["id"]
        merged.append(cand)

    merged.sort(key=lambda e: e["id"])
    errors, warnings = validate(merged)

    print(f"existing entries       {len(existing)}")
    print(f"candidate entries      {len(candidates)}")
    print(f"dropped (dup id)       {len(dropped_dupe_id)}  {dropped_dupe_id}")
    print(f"dropped (dup surface)  {len(dropped_dupe_surface)}  {dropped_dupe_surface}")
    print(f"region fixups          {len(fixed_region)}")
    for line in fixed_region:
        print(f"  {line}")
    print(f"merged total           {len(merged)}")
    print(f"validation errors      {len(errors)}")
    for e in errors:
        print(f"  ERROR {e}")
    print(f"validation warnings    {len(warnings)}")

    if errors:
        raise SystemExit("fix errors before writing")

    if args.write:
        with open(ENTRIES_PATH, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"\nwrote {ENTRIES_PATH.relative_to(ROOT)}")
    else:
        print("\ndry run — pass --write to commit")


if __name__ == "__main__":
    main()
