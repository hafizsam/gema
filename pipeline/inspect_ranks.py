"""Eyeball the rankings. This is the Phase 0 acceptance test.

    python pipeline/inspect_ranks.py "nasi lemak"        # neighbours of one entry
    python pipeline/inspect_ranks.py --all               # top 5 for every entry
    python pipeline/inspect_ranks.py "durian" --bottom   # farthest entries too
"""
from __future__ import annotations

import argparse

import numpy as np

from lexicon import BUILD_DIR, build_lookup, load_entries, normalize
from score import build_scores, csls, equality_matrix, jaccard_matrix, load_config, minmax


def components(entries, vecs, cfg):
    cos = vecs @ vecs.T
    return {
        "emb": minmax(csls(cos, cfg["csls_k"])),
        "tag": jaccard_matrix([set(e["tags"]) for e in entries]),
        "cat": equality_matrix([e["category"] for e in entries]),
    }


def heat(rank: int, n: int, cfg: dict) -> str:
    pct = rank / max(n - 1, 1)
    for tier in cfg["heat_tiers"]:
        if pct <= tier["max_rank_pct"]:
            return tier["name"]
    return cfg["heat_tiers"][-1]["name"]


def show(entries, scores, comps, cfg, i, top, bottom):
    n = len(entries)
    order = np.argsort(-scores[i])
    order = order[order != i]  # an entry is never its own guess
    target = entries[i]

    print(f"\n=== {target['term']}  [{target['category']}]")
    print(f"    tags: {', '.join(target['tags'])}")
    print(f"    {'#':>3}  {'term':<26} {'score':>6} {'heat':>8} "
          f"{'emb':>6} {'tag':>6} {'cat':>4}  shared tags")
    picks = list(order[:top])
    if bottom:
        picks += [None] + list(order[-3:])
    for pos, j in enumerate(picks):
        if j is None:
            print(f"    {'...':>3}")
            continue
        rank = int(np.where(order == j)[0][0]) + 1
        shared = sorted(set(target["tags"]) & set(entries[j]["tags"]))
        print(
            f"    {rank:>3}  {entries[j]['term'][:26]:<26} "
            f"{scores[i, j]:>6.3f} {heat(rank, n, cfg):>8} "
            f"{comps['emb'][i, j]:>6.3f} {comps['tag'][i, j]:>6.3f} "
            f"{int(comps['cat'][i, j]):>4}  {', '.join(shared)}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("term", nargs="?", help="term or alias to inspect")
    ap.add_argument("--all", action="store_true", help="summarise every entry")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--bottom", action="store_true", help="also show farthest entries")
    args = ap.parse_args()

    cfg = load_config()
    entries = load_entries()
    vecs = np.load(BUILD_DIR / "vectors.npy")
    scores = build_scores(entries, vecs, cfg)
    comps = components(entries, vecs, cfg)

    if args.all:
        for i in range(len(entries)):
            show(entries, scores, comps, cfg, i, 5, False)
        return

    if not args.term:
        ap.error("give a term, or pass --all")

    lookup = build_lookup(entries)
    key = normalize(args.term)
    if key not in lookup:
        raise SystemExit(f"{args.term!r} is not in the lexicon")
    i = [e["id"] for e in entries].index(lookup[key])
    show(entries, scores, comps, cfg, i, args.top, args.bottom)


if __name__ == "__main__":
    main()
