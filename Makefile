PY := .venv/bin/python
PIPELINE := cd pipeline && ../$(PY)

.PHONY: help setup validate embed score build inspect puzzles clean serve

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup:  ## create the venv and install the light dependencies
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q numpy scikit-learn

validate:  ## check the lexicon against the schema invariants
	$(PIPELINE) validate.py

embed:  ## build embeddings (BACKEND=tfidf|st)
	$(PIPELINE) build_embeddings.py --backend $(or $(BACKEND),tfidf)

score:  ## build the hybrid similarity matrix and rank tables
	$(PIPELINE) score.py

build: validate embed score  ## full data build

inspect:  ## neighbours for one entry, e.g. make inspect TERM="nasi lemak"
	$(PIPELINE) inspect_ranks.py "$(TERM)" --top $(or $(TOP),10)

puzzles:  ## emit vocab.json and DAYS daily puzzle files
	$(PIPELINE) make_puzzle.py --days $(or $(DAYS),7)

clean:
	rm -rf data/build docs/data

serve:  ## serve docs/ locally so fetch() of docs/data/*.json works
	cd docs && ../$(PY) -m http.server 8000
