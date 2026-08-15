PYTHON ?= python3

.PHONY: all refresh clean

all:
	$(PYTHON) cec2info.py --compile

refresh:
	$(PYTHON) cec2info.py --refresh --compile

clean:
	rm -f catechisme.texi catechisme.info
