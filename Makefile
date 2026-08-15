PYTHON ?= python3

.PHONY: all refresh info pdf epub test clean

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
