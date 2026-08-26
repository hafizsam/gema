"""Embed every lexicon entry and write a normalized vector matrix.

Two backends:

  tfidf  no model download, character+word TF-IDF over the descriptions.
         Good enough to validate the pipeline and eyeball rankings.
  st     sentence-transformers, multilingual. The real backend.

    python pipeline/build_embeddings.py --backend tfidf
    python pipeline/build_embeddings.py --backend st --model intfloat/multilingual-e5-large
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from lexicon import BUILD_DIR, load_entries
from stopwords import STOPWORDS


def entry_text(entry: dict) -> str:
    """The string we actually embed.

    Descriptions carry the semantics; tags and category are appended so that
    curated attributes leak into the embedding as well as into the tag score.
    """
    tags = " ".join(t.replace("-", " ") for t in entry["tags"])
    region = entry["region"] or ""
    return (
        f"{entry['term']}. {entry['desc_en']} {entry['desc_ms']} "
        f"{entry['category']} {region} {tags}"
    ).strip()


def embed_tfidf(texts: list[str]) -> np.ndarray:
    """Word-level TF-IDF over content words only.

    Deliberately no character n-grams: Malay is agglutinative, so char n-grams
    match shared affixes (meng-, -kan, -nya) and rank unrelated entries as
    similar purely on morphology.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    matrix = TfidfVectorizer(
        sublinear_tf=True,
        min_df=1,
        max_df=0.5,
        ngram_range=(1, 2),
        strip_accents="unicode",
        stop_words=STOPWORDS,
    ).fit_transform(texts)
    return np.asarray(matrix.todense(), dtype=np.float32)


def embed_st(texts: list[str], model_name: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    prefix = "passage: " if "e5" in model_name.lower() else ""
    return model.encode(
        [prefix + t for t in texts],
        batch_size=16,
        convert_to_numpy=True,
        show_progress_bar=True,
    ).astype(np.float32)


def l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return mat / np.maximum(norms, 1e-9)


def all_but_the_top(mat: np.ndarray, d: int = 2) -> np.ndarray:
    """Mean-center and strip the top d principal components.

    Embedding spaces are anisotropic: every vector shares a large common
    component, which squashes all cosines into a narrow band and makes the
    differences between them feel arbitrary to players. Removing it spreads
    the similarity distribution back out.
    """
    if d <= 0 or mat.shape[0] <= d:
        return mat
    centered = mat - mat.mean(axis=0, keepdims=True)
    d = min(d, min(centered.shape) - 1)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    top = vt[:d]
    return centered - (centered @ top.T) @ top


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["tfidf", "st"], default="tfidf")
    ap.add_argument("--model", default="intfloat/multilingual-e5-large")
    ap.add_argument("--abtt", type=int, default=2, help="principal components to remove")
    args = ap.parse_args()

    entries = load_entries()
    texts = [entry_text(e) for e in entries]
    print(f"embedding {len(entries)} entries with backend={args.backend}")

    raw = embed_tfidf(texts) if args.backend == "tfidf" else embed_st(texts, args.model)
    vecs = l2_normalize(all_but_the_top(l2_normalize(raw), args.abtt))

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    np.save(BUILD_DIR / "vectors.npy", vecs)
    meta = {
        "backend": args.backend,
        "model": args.model if args.backend == "st" else None,
        "abtt": args.abtt,
        "dims": int(vecs.shape[1]),
        "ids": [e["id"] for e in entries],
    }
    with open(BUILD_DIR / "vectors.meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"wrote {vecs.shape[0]} x {vecs.shape[1]} -> {BUILD_DIR / 'vectors.npy'}")


if __name__ == "__main__":
    main()
