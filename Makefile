PYTHON ?= python3
NPM ?= npm

.PHONY: demo test security frontend-test frontend-build docker-build reproducibility institutional-demo clean

# Public, local-data-free commands. Generated files are ignored by .gitignore.
demo:
	PYTHONPATH=src $(PYTHON) tools/nwrsa_demo.py
	PYTHONPATH=src $(PYTHON) tools/scientific_benchmark_demo.py

institutional-demo:
	PYTHONPATH=src:. $(PYTHON) tools/institutional_onboarding_demo.py

test:
	PYTHONPATH=src:. $(PYTHON) -m pytest -q

security:
	$(PYTHON) tools/security_release_checks.py --summary
	PYTHONPATH=src $(PYTHON) -m unittest tests/test_release_hygiene.py

frontend-test:
	cd apps/web && $(NPM) test && $(NPM) run typecheck

frontend-build:
	cd apps/web && $(NPM) run build

docker-build:
	docker build -f infra/docker/Dockerfile.api -t xroad-api .
	docker build -f infra/docker/Dockerfile.web -t xroad-web .

reproducibility:
	$(PYTHON) tools/reproducibility_check.py

clean:
	find data -type f ! -name '.gitkeep' ! -name 'README.md' -delete
	find data -type d -empty -delete
