# Makefile
#
# WHY: A Makefile standardises every developer action into one-word commands.
# Recruiters and collaborators can `make install && make test` without reading
# any docs. On Windows, use `nmake` (ships with Visual Studio Build Tools) or
# use the make.bat fallback instead.
#
# Run `nmake <target>` in CMD, or `make <target>` in Git Bash / WSL.

.PHONY: install test lint serve run-demo clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

lint:
	ruff check gauntlet/

serve:
	gauntlet serve

# A quick smoke-test eval so anyone can see Gauntlet work without writing code.
# Uses the built-in demo agent (HTTP echo) so no custom agent is needed.
run-demo:
	gauntlet run \
		--goal "Summarise a news article in three bullet points" \
		--agent-description "An LLM agent that summarises text" \
		--mode standard \
		--scenarios 2

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f gauntlet.db
