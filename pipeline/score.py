"""Turn embeddings + curated tags into the hybrid similarity matrix and ranks.

Score for a pair of entries:

    final = w_emb * csls(embeddings)     fuzzy topical similarity
          + w_tag * jaccard(tags)        crisp, human-authored relatedness
          + w_cat * same_category
          + w_reg * same_region

CSLS is applied to the embedding term to correct hubness: without it, a handful
of generic entries sit near everything and score suspiciously well against every
target, which is exactly the "why is that ranked so high?" complaint.

    python pipeline/score.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from lexicon import BUILD_DIR, load_entries

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def csls(cos: np.ndarray, k: int) -> np.ndarray:
    """Cross-domain similarity local scaling.

    Penalise entries that are close to everything by subtracting each side's
    mean similarity to its own k nearest neighbours.
    """
    n = cos.shape[0]
    k = max(1, min(k, n - 1))
    off = cos.copy()
    np.fill_diagonal(off, -np.inf)
    topk = np.sort(off, axis=1)[:, -k:]
    r = topk.mean(axis=1)
    return 2.0 * cos - r[:, None] - r[None, :]


def minmax(mat: np.ndarray) -> np.ndarray:
    """Scale to [0, 1] using off-diagonal values only."""
    n = mat.shape[0]
    mask = ~np.eye(n, dtype=bool)
    lo, hi = mat[mask].min(), mat[mask].max()
    return np.clip((mat - lo) / max(hi - lo, 1e-9), 0.0, 1.0)


def jaccard_matrix(tag_sets: list[set[str]]) -> np.ndarray:
    """IDF-weighted Jaccard overlap of the curated tags.

    Plain Jaccard treats every shared tag alike, which lets a tag carried by a
    third of the lexicon (`malay`) dominate the score and pull unrelated entries
    together. Weighting each tag by its inverse document frequency means sharing
    `banana-leaf` counts for far more than sharing `malay`, which is how a
    player intuitively reasons about it.
    """
    n = len(tag_sets)
    vocab = sorted({t for s in tag_sets for t in s})
    index = {t: i for i, t in enumerate(vocab)}

    present = np.zeros((n, len(vocab)), dtype=np.float32)
    for i, s in enumerate(tag_sets):
        for t in s:
            present[i, index[t]] = 1.0

    df = present.sum(axis=0)
    idf = np.log(1.0 + n / np.maximum(df, 1.0)).astype(np.float32)

    weighted = present * idf
    inter = weighted @ present.T          # sum of idf over shared tags
    totals = weighted.sum(axis=1)
    union = totals[:, None] + totals[None, :] - inter
    return (inter / np.maximum(union, 1e-9)).astype(np.float32)


def equality_matrix(values: list, ignore=(None,)) -> np.ndarray:
    n = len(values)
    m = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        if values[i] in ignore:
            continue
        for j in range(n):
            if values[i] == values[j]:
                m[i, j] = 1.0
    return m


def build_scores(entries: list[dict], vecs: np.ndarray, cfg: dict) -> np.ndarray:
    w = cfg["weights"]
    cos = vecs @ vecs.T
    emb = minmax(csls(cos, cfg["csls_k"]))
    tags = jaccard_matrix([set(e["tags"]) for e in entries])
    cat = equality_matrix([e["category"] for e in entries])
    reg = equality_matrix([e["region"] for e in entries])

    total = w["embedding"] + w["tags"] + w["category"] + w["region"]
    final = (
        w["embedding"] * emb
        + w["tags"] * tags
        + w["category"] * cat
        + w["region"] * reg
    ) / total
    np.fill_diagonal(final, 1.0)
    return final.astype(np.float32)


def rank_lists(scores: np.ndarray) -> np.ndarray:
    """ranks[a, b] = rank of entry b as a guess against answer a (answer = 0)."""
    n = scores.shape[0]
    order = np.argsort(-scores, axis=1, kind="stable")
    ranks = np.empty((n, n), dtype=np.int32)
    rows = np.arange(n)[:, None]
    ranks[rows, order] = np.arange(n)[None, :]
    return ranks


def main() -> None:
    cfg = load_config()
    entries = load_entries()
    vecs = np.load(BUILD_DIR / "vectors.npy")
    with open(BUILD_DIR / "vectors.meta.json", encoding="utf-8") as fh:
        meta = json.load(fh)

    ids = [e["id"] for e in entries]
    if meta["ids"] != ids:
        raise SystemExit("vectors are stale, rerun build_embeddings.py")

    scores = build_scores(entries, vecs, cfg)
    ranks = rank_lists(scores)

    np.save(BUILD_DIR / "scores.npy", scores)
    np.save(BUILD_DIR / "ranks.npy", ranks)

    off = scores[~np.eye(len(ids), dtype=bool)]
    print(f"scored {len(ids)} x {len(ids)} entries")
    print(
        f"pairwise score  min={off.min():.3f}  p50={np.median(off):.3f}  "
        f"p99={np.quantile(off, 0.99):.3f}  max={off.max():.3f}"
    )
    print(f"wrote {BUILD_DIR / 'scores.npy'} and {BUILD_DIR / 'ranks.npy'}")


if __name__ == "__main__":
    main()
