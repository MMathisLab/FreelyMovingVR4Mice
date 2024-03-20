docs:
	PYTHONPATH=. jupyter-book build docs

dist:
	python -m build .

tests:
	PYTHONPATH=. python -m pytest -vvv tests

.PHONY: docs dist tests