"""Shared lexicon loading, normalization and validation helpers."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES_PATH = ROOT / "lexicon" / "entries.json"
BUILD_DIR = ROOT / "data" / "build"

CATEGORIES = {
    "food", "place", "festival", "clothing", "arts",
    "nature", "object", "institution", "person", "concept",
}
LANGS = {"ms", "en", "zh", "ta", "mixed"}

_PUNCT = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Fold a typed guess to a lookup key.

    Case, accents, hyphens, apostrophes and spacing are all collapsed so that
    "Char Koay Teow", "char-kuey-teow" and "charkueyteow" hit the same entry.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return _PUNCT.sub("", text.lower())


def load_entries(path: Path = ENTRIES_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        entries = json.load(fh)
    entries.sort(key=lambda e: e["id"])
    return entries


def build_lookup(entries: list[dict]) -> dict[str, str]:
    """Map every normalized term and alias to its entry id."""
    lookup: dict[str, str] = {}
    for entry in entries:
        for surface in [entry["term"], *entry["aliases"]]:
            lookup[normalize(surface)] = entry["id"]
    return lookup


def validate(entries: list[dict]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors must be fixed before the build runs."""
    errors: list[str] = []
    warnings: list[str] = []

    seen_ids: set[str] = set()
    seen_surfaces: dict[str, str] = {}
    tag_counts: dict[str, int] = {}
    required = {
        "id", "term", "aliases", "lang", "category",
        "region", "tags", "desc_en", "desc_ms", "is_answer", "difficulty",
    }

    for entry in entries:
        eid = entry.get("id", "<missing id>")

        missing = required - entry.keys()
        if missing:
            errors.append(f"{eid}: missing field(s) {sorted(missing)}")
            continue

        if not re.fullmatch(r"[a-z0-9_]+", entry["id"]):
            errors.append(f"{eid}: id must be lowercase snake_case ascii")
        if entry["id"] in seen_ids:
            errors.append(f"{eid}: duplicate id")
        seen_ids.add(entry["id"])

        if entry["category"] not in CATEGORIES:
            errors.append(f"{eid}: unknown category {entry['category']!r}")
        if entry["lang"] not in LANGS:
            errors.append(f"{eid}: unknown lang {entry['lang']!r}")

        for surface in [entry["term"], *entry["aliases"]]:
            key = normalize(surface)
            if not key:
                errors.append(f"{eid}: surface form {surface!r} normalizes to empty")
            elif key in seen_surfaces and seen_surfaces[key] != entry["id"]:
                errors.append(
                    f"{eid}: surface {surface!r} collides with {seen_surfaces[key]}"
                )
            else:
                seen_surfaces[key] = entry["id"]

        if not entry["tags"]:
            errors.append(f"{eid}: needs at least one tag")
        if len(entry["tags"]) != len(set(entry["tags"])):
            errors.append(f"{eid}: duplicate tags")
        for tag in entry["tags"]:
            if not re.fullmatch(r"[a-z0-9-]+", tag):
                errors.append(f"{eid}: tag {tag!r} must be kebab-case")
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        if entry["category"] in entry["tags"]:
            warnings.append(f"{eid}: tag {entry['category']!r} restates the category")

        for field in ("desc_en", "desc_ms"):
            if not entry[field].strip():
                errors.append(f"{eid}: {field} is empty")

        if entry["difficulty"] not in (1, 2, 3):
            errors.append(f"{eid}: difficulty must be 1, 2 or 3")
        if not isinstance(entry["is_answer"], bool):
            errors.append(f"{eid}: is_answer must be a boolean")

    singletons = sorted(t for t, n in tag_counts.items() if n < 2)
    if singletons:
        warnings.append(
            f"{len(singletons)} tag(s) used by only one entry, inert for scoring: "
            + ", ".join(singletons)
        )

    return errors, warnings
