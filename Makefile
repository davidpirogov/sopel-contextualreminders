.PHONY: qa quality test coverages coverage_report coverage_html pylint pyroma

quality:
	isort contextualreminders
	pylint --max-line-length=120 --disable=locally-disabled contextualreminders
	isort tests
	pylint --max-line-length=120 --disable=locally-disabled tests/*
	mypy contextualreminders

test:
	coverage run -m py.test -v .

coverage_report:
	coverage report

coverage_html:
	coverage html

coverages: coverage_report coverage_html

pylint:
	pylint --max-line-length=120 --disable=locally-disabled contextualreminders

pyroma:
	pyroma .

qa: quality test coverages pylint pyroma

.PHONY: develop build

develop:
	pip install -r requirements.txt
	python setup.py develop

build:
	rm -rf build/ dist/
	python setup.py sdist bdist_wheel
