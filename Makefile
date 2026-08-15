PYTHON ?= python3
REPORT ?= generation-report.json

.PHONY: all refresh info pdf epub test lint coverage check clean distclean

all:
	$(PYTHON) cec2info.py --compile --pdf --epub --report-json $(REPORT)

refresh:
	$(PYTHON) cec2info.py --refresh --compile --pdf --epub --report-json $(REPORT)

info:
	$(PYTHON) cec2info.py --compile

pdf:
	$(PYTHON) cec2info.py --pdf

epub:
	$(PYTHON) cec2info.py --epub

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m ruff check .

coverage:
	$(PYTHON) -m coverage run -m unittest discover -s tests
	$(PYTHON) -m coverage report

check: lint coverage

clean:
	rm -f catechisme.texi catechisme.info catechisme.pdf catechisme.epub
	rm -f $(REPORT)
	rm -f catechisme.aux catechisme.cp catechisme.cps catechisme.dvi
	rm -f catechisme.log catechisme.tex catechisme.toc cp.idx
	rm -rf catechisme_epub_package

distclean: clean
	rm -rf .cec-cache __pycache__ tests/__pycache__
