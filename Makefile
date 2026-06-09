.PHONY: validate test stats search suggest recommend compose check \
        embed index quality export clean install help

comma := ,
PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PIP := $(if $(wildcard .venv/bin/pip),.venv/bin/pip,pip)

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

validate:       ## Validate all 269 skills
	$(PYTHON) taskmaster.py validate

test:           ## Run full test suite
	$(PYTHON) -m pytest tests/ -v

stats:          ## Show category and risk distributions
	$(PYTHON) taskmaster.py stats

search:         ## Search skills by keyword (usage: make search q="postgres")
	$(PYTHON) taskmaster.py search "$(q)"

suggest:        ## Suggest skills for a task (usage: make suggest t="debug api")
	$(PYTHON) taskmaster.py suggest "$(t)"

recommend:      ## Recommend with semantic+keyword scoring (usage: make recommend t="security audit")
	$(PYTHON) taskmaster.py recommend "$(t)"

compose:        ## Compose a dependency plan (usage: make compose s="bug-hunter,error-detective")
	$(PYTHON) taskmaster.py compose $(subst $(comma), ,$(s))

check:          ## Deep-check a skill (usage: make check s=bug-hunter)
	$(PYTHON) taskmaster.py check $(s)

embed:          ## Build or rebuild the embedding index
	$(PYTHON) taskmaster.py embed

index:          ## Regenerate INDEX.md
	$(PYTHON) taskmaster.py generate-index

quality:        ## Score all skills by quality
	$(PYTHON) taskmaster.py quality

export:         ## Export all skills as JSON
	$(PYTHON) taskmaster.py export --json

install:        ## Install with all extras
	$(PYTHON) -m pip install -e ".[all]"

clean:          ## Remove caches and build artifacts
	rm -rf .taskmaster_cache/ .pytest_cache/ .ruff_cache/
	rm -rf __pycache__/ */__pycache__/ */*/__pycache__/
	rm -rf build/ dist/ *.egg-info/
	find . -name '*.pyc' -delete
