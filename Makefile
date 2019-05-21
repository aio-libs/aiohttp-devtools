.DEFAULT_GOAL := all

.PHONY: install
install:
	pip install -U setuptools pip
	pip install -e .
	pip install -r tests/requirements.txt
	grablib

.PHONY: isort
isort:
	isort -rc -w 120 aiohttp_devtools
	isort -rc -w 120 tests

.PHONY: lint
lint:
	python setup.py check -rms
	flake8 aiohttp_devtools/ tests/
	isort -rc -w 120 --check-only aiohttp_devtools
	isort -rc -w 120 --check-only tests

.PHONY: test
test:
	pytest --cov=aiohttp_devtools --boxed --duration 5 && (coverage combine || test 0)

.PHONY: testcov
testfast:
	pytest --cov=aiohttp_devtools --boxed --fast -n 4 && (echo "building coverage html"; coverage combine; coverage html)

.PHONY: testcov
testcov:
	pytest --cov=aiohttp_devtools --boxed && (echo "building coverage html"; coverage combine; coverage html)

.PHONY: all
all: testcov lint

.PHONY: clean
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -rf .cache
	rm -rf htmlcov
	rm -rf *.egg-info
	rm -f .coverage
	rm -f .coverage.*
	rm -rf build
	python setup.py clean
