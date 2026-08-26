# Gema

A Malaysian-culture guessing game in the style of Nounable / Semantle. Each day
has a secret entry from a curated Malaysian lexicon; players guess other entries
and are told how semantically close each guess is, by rank.

**Phase 0 (pipeline + seed lexicon) and a working front end are done. Phase 1
(scaling the lexicon) is in progress: 275 entries across 10 categories.**

## Why the scoring is hybrid

The standard complaint about Semantle-likes is that a word which obviously feels
related ranks worse than one that doesn't. Raw embedding cosine causes this:
it measures distributional co-occurrence, not human relatedness, and it suffers
from hubness (a few entries sit near everything) and anisotropy (all cosines
squashed into a narrow band).

So the score is not raw cosine. It is:

```
final = 0.60 * csls(embedding of the description)   fuzzy topical similarity
      + 0.28 * jaccard(hand-authored tags)          crisp, curated relatedness
      + 0.08 * same_category
      + 0.04 * same_region
```

with `all-but-the-top` applied to the embeddings first (strips the shared
component that causes anisotropy) and CSLS applied to the cosines (penalises
hub entries).

The tag term is the important one. Because the lexicon is curated and closed, we
can encode the attributes a player actually reasons about — ingredients, ethnic
association, occasion, material — and make `nasi lemak` ↔ `nasi kerabu`
reliably close instead of hoping the model figures it out. Weights live in
[pipeline/config.json](pipeline/config.json) and are meant to be tuned by
eyeballing `inspect_ranks.py`.

## Layout

```
lexicon/entries.json     the lexicon — the actual work of this project
lexicon/SCHEMA.md        entry format and authoring rules
pipeline/                offline build: validate, embed, score, emit
data/build/              intermediate matrices (gitignored)
public/data/             what the web app fetches (gitignored, generated)
```

## Usage

```bash
make setup                        # venv + numpy + scikit-learn
make build                        # validate, embed, score
make inspect TERM="nasi lemak"    # eyeball the neighbours of one entry
make puzzles DAYS=30              # emit vocab.json + daily puzzle files
```

The real embedding backend needs `pip install sentence-transformers`:

```bash
make embed BACKEND=st && make score
```

### Backends

| Backend | Cost | Use |
|---|---|---|
| `tfidf` | none, ships with scikit-learn | pipeline smoke test only — see the caveat below |
| `st` | ~2 GB of torch + model | the real one |

**The `tfidf` backend is not good enough to ship.** At this lexicon size a single
shared token dominates a sparse vector, so every entry whose description contains
"Malay" clusters together regardless of meaning. It exists to prove the pipeline
end to end without a model download. Judge ranking quality on `st` only.

## Data files

`docs/data/vocab.json` — every entry with its display text and aliases. Drives
autocomplete and the end-of-game reveal.

`docs/data/puzzles/YYYY-MM-DD.json` — rank and score for every entry against
that day's answer, keyed by `sha256(salt:date:id)[:12]`. About 15 KB at 584
entries, extrapolating to roughly 110 KB (40 KB gzipped) at the target 4,000.

`data/build/vectors.npy` + `vectors.meta.json` are committed (small, ~1.8 MB)
so CI can rerun `score.py` and `make_puzzle.py` — both pure numpy — without
redownloading the sentence-transformers model. `scores.npy`/`ranks.npy` are
regenerated on every run and gitignored.

The hashing stops the answer being readable in devtools, but the salt ships to
the client, so a determined player can script their way to it. If that matters,
move scoring behind a Cloudflare Worker; the front end does not change.

## Front end

`docs/` is a plain HTML/CSS/JS site — no build step, no framework, no Node
dependency. It fetches `docs/data/*.json` directly and does all scoring lookups
(guess normalization, salted-hash lookup, heat tiers, win detection) in the
browser; the heavy computation already happened offline in the pipeline.

```bash
make serve   # http://localhost:8000, serves docs/ so fetch() finds docs/data
```

Progress, streak and language preference persist in `localStorage`, scoped per
puzzle date so switching days doesn't leak guesses across puzzles.

### Deploying

Because the site needs no build step, GitHub Pages serves it directly:
push this repo, then in **Settings → Pages** set source to
**Deploy from a branch → `main` → `/docs`**.

`.github/workflows/daily-puzzle.yml` runs `score.py` + `make_puzzle.py` daily
(00:00 MYT) and commits any new `docs/data/puzzles/*.json` — pure numpy, no
model download, since `vectors.npy` is committed. Run it manually
(`workflow_dispatch`) after editing `lexicon/entries.json` or
`pipeline/config.json` to pick up the change immediately instead of waiting
for the next scheduled run.

## Growing the lexicon

`pipeline/merge_batches.py` merges one or more `lexicon/batches/*.json` files
(same entry schema as `entries.json`) into the canonical lexicon. It drops
duplicate ids, drops entries whose term/alias collides with something already
in the lexicon (case/spacing/hyphen-insensitive), and normalizes any `region`
value outside the state/territory enum to `null` — logging every drop and fix
instead of silently applying them. Run it, review the report, then re-run
`make build && make puzzles` since growing the lexicon reshuffles which entry
lands on which date (the answer schedule is a deterministic function of the
full answer-eligible set).

## Next

Continue Phase 1 toward the 3,000–5,000 entry target — that's authoring work,
not code. Also worth doing: a feedback control ("this ranking seems off") on
each guess row per the design doc, and moving scoring behind a small serverless
endpoint if answer-scripting becomes a real problem once the game has players.
