PYTHON ?= python3
REPORT ?= generation-report.json
LANGUAGE ?= fr

.PHONY: all refresh info pdf epub test lint typecheck coverage check clean distclean

all:
	$(PYTHON) cec2info.py --language $(LANGUAGE) --compile --pdf --epub --report-json $(REPORT)

refresh:
	$(PYTHON) cec2info.py --language $(LANGUAGE) --refresh --compile --pdf --epub --report-json $(REPORT)

info:
	$(PYTHON) cec2info.py --language $(LANGUAGE) --compile

pdf:
	$(PYTHON) cec2info.py --language $(LANGUAGE) --pdf

epub:
	$(PYTHON) cec2info.py --language $(LANGUAGE) --epub

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy

coverage:
	$(PYTHON) -m coverage run -m unittest discover -s tests
	$(PYTHON) -m coverage report

check: lint typecheck coverage

clean:
	rm -f catechisme.texi catechisme.info catechisme.pdf catechisme.epub
	rm -f catechism.texi catechism.info catechism.pdf catechism.epub
	rm -f katechismus.texi katechismus.info katechismus.pdf katechismus.epub
	rm -f catechismo.texi catechismo.info catechismo.pdf catechismo.epub
	rm -f catecismo-es.texi catecismo-es.info catecismo-es.pdf catecismo-es.epub
	rm -f catecismo-pt.texi catecismo-pt.info catecismo-pt.pdf catecismo-pt.epub
	rm -f catechismus-la.texi catechismus-la.info catechismus-la.pdf catechismus-la.epub
	rm -f $(REPORT)
	rm -f catechisme.aux catechisme.cp catechisme.cps catechisme.dvi
	rm -f catechisme.log catechisme.tex catechisme.toc cp.idx
	rm -rf catechisme_epub_package

distclean: clean
	rm -rf .cec-cache __pycache__ tests/__pycache__
