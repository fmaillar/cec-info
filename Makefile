PYTHON ?= python3

.PHONY: all refresh info pdf epub test clean distclean

all:
	$(PYTHON) cec2info.py --compile --pdf --epub

refresh:
	$(PYTHON) cec2info.py --refresh --compile --pdf --epub

info:
	$(PYTHON) cec2info.py --compile

pdf:
	$(PYTHON) cec2info.py --pdf

epub:
	$(PYTHON) cec2info.py --epub

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -f catechisme.texi catechisme.info catechisme.pdf catechisme.epub
	rm -f catechisme.aux catechisme.cp catechisme.cps catechisme.dvi
	rm -f catechisme.log catechisme.tex catechisme.toc cp.idx
	rm -rf catechisme_epub_package

distclean: clean
	rm -rf .cec-cache __pycache__ tests/__pycache__
