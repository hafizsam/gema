# Lexicon Schema

The lexicon is the heart of the game. Every typeable word and every possible answer
lives in `lexicon/entries.json` as a single flat list of entries.

## Entry format

```json
{
  "id": "nasi_lemak",
  "term": "nasi lemak",
  "aliases": ["nasilemak", "nasi-lemak"],
  "lang": "ms",
  "category": "food",
  "region": null,
  "tags": ["rice", "coconut", "sambal", "breakfast", "malay", "staple"],
  "desc_en": "Fragrant coconut rice served with sambal, fried anchovies, ...",
  "desc_ms": "Nasi yang dimasak dengan santan, dihidang bersama sambal, ...",
  "is_answer": true,
  "difficulty": 1
}
```

## Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Unique, `snake_case`, ASCII. Stable forever — puzzle history references it. |
| `term` | string | yes | Canonical display form. Lowercase unless it is a proper noun. |
| `aliases` | string[] | yes | Alternate spellings players may type. May be empty. Must be unique across the whole lexicon. |
| `lang` | enum | yes | `ms` \| `en` \| `zh` \| `ta` \| `mixed` — origin of the term, used only for display/filtering. |
| `category` | enum | yes | One of the 10 categories below. Drives the `same_category` scoring bonus. |
| `region` | string\|null | yes | State or region if strongly associated (`kelantan`, `sabah`, `penang`), else `null`. |
| `tags` | string[] | yes | 4–10 `kebab-case` attribute tags. **This is the tuning surface** — see below. |
| `desc_en` | string | yes | 1–2 sentences. This is what gets embedded, so write it densely and factually. |
| `desc_ms` | string | yes | Malay equivalent. Also embedded (multilingual model). |
| `is_answer` | bool | yes | `true` = eligible to be a daily target. Reserve for well-known entries. |
| `difficulty` | int | yes | `1` common knowledge · `2` moderate · `3` niche. Used to pace the answer schedule. |

## Categories

`food` · `place` · `festival` · `clothing` · `arts` · `nature` · `object` ·
`institution` · `person` · `concept`

## Tag guidance

Tags are how we fix the "obviously related word ranked too far" complaint. The
embedding gives fuzzy topical similarity; tags give crisp, human-legible
relatedness that we control directly.

- Prefer **shared, reusable** tags over unique descriptors. A tag used by exactly
  one entry contributes nothing to similarity.
- Tag the **attributes a player would reason about**: ingredients, materials,
  occasions, ethnic association, form factor, sensory qualities.
- Do not restate the category as a tag (`food` on a `food` entry is dead weight).
- Aim for 4–10. Too many dilutes the Jaccard overlap signal.

Good: `["rice", "coconut", "sambal", "breakfast", "malay", "staple"]`
Bad: `["food", "delicious", "nasi-lemak", "eaten"]`

## Invariants (enforced by `pipeline/validate.py`)

1. `id` unique.
2. `term` and every alias, after normalization, unique across the whole lexicon —
   no two entries may be reachable by the same typed input.
3. `category` and `lang` within the allowed enums.
4. `tags` non-empty, kebab-case, no duplicates within an entry.
5. `desc_en` and `desc_ms` non-empty.
6. Every tag must be used by **at least 2 entries** (warning only — singleton tags
   are inert for scoring).
