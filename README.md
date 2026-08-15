# CEC → GNU Info

**English** | [Français](README.fr.md)

[![CI](https://github.com/fmaillar/cec-info/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/fmaillar/cec-info/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/fmaillar/cec-info)](https://github.com/fmaillar/cec-info/releases/latest)
[![GPL-3.0-or-later license](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)

Converts the French or English edition of the **Catechism of the Catholic
Church** published by the Vatican (IntraText) to **GNU Texinfo / Info**, PDF,
and EPUB 3. The Info output can be read directly in Emacs.

## Dependencies (Debian)

```sh
sudo apt install python3-bs4 texinfo
```

`pandoc` is not required.

PDF generation also requires a TeX installation providing `texi2dvi` and a
DVI-to-PDF converter, such as `texlive` on Debian.

The project can also be installed in a Python virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
cec2info --help
```

## Usage

```sh
make
```

French is the default source language. Select the official English corpus with:

```sh
make LANGUAGE=en
# or
cec2info --language en --compile --pdf --epub
```

Supported language codes are `fr` and `en`. `--language` selects the official
Vatican URL, navigation labels, structural headings, generated metadata, and
default file names. `--index-url` can still override the selected source URL.

The script creates:

- `.cec-cache/`: local cache for downloaded HTML pages;
- `catechisme.*`: French Texinfo, Info, PDF, and EPUB outputs;
- `catechism.*`: corresponding English outputs;
- `generation-report.json`: machine-readable generation report.

To generate a single format:

```sh
make info
make pdf
make epub
```

Run the local test suite with `make test` or all quality checks with
`make check`.

Before compiling the final formats, the generator verifies that paragraphs 1
through 2865 are present exactly once. IntraText pages missing from the table
of contents are recovered automatically by following localized next-page
links. For a different corpus, adjust the limit with
`--expected-last-paragraph`, or pass `0` to disable this check.

A human-readable report is always printed at the end. To also write a JSON
report with the installed command:

```sh
cec2info --compile --pdf --epub --report-json generation-report.json
```

The JSON report contains the language, source URL, entry count, linked and
orphan pages, paragraph coverage, and the path and size of every generated
file.

## Architecture

`cec2info.py` preserves the public interface and orchestrates the command. The
internal responsibilities are split without changing how the tool is used:

- `cec2info_network.py`: downloads, retries, and atomic cache writes;
- `cec2info_language.py`: French and English source/output profiles;
- `cec2info_parser.py`: IntraText table-of-contents and HTML parsing;
- `cec2info_output.py`: Texinfo generation, validation, reports, and compilation;
- `cec2info_model.py`: document tree and shared normalization.

Functions historically importable from `cec2info` are still re-exported for
backward compatibility.

To force a fresh download:

```sh
make refresh
```

`make clean` removes generated output and compilation auxiliaries.
`make distclean` also removes the HTML and Python caches.

## Continuous integration

The `.github/workflows/ci.yml` workflow tests Python 3.10 and 3.13 on Ubuntu,
and Python 3.13 on macOS and Windows. It checks the code with Ruff and mypy,
tests the `cec2info` command, and builds a wheel without downloading the
Vatican corpus. Ubuntu additionally enforces at least 95% branch coverage and
actually compiles the Info, PDF, and EPUB outputs. The other platforms run the
Python tests and skip compilation tests when Texinfo/TeX tools are unavailable.
Locally, `make check` reproduces the Python quality checks.

Small French and English HTML corpora also exercise the deterministic
integration chain: table of contents, orphan page, paragraphs, localized
Texinfo, and JSON report. CI therefore does not depend on the network to detect
integration regressions.

Run progressive static type checking separately with `make typecheck`.

Third-party GitHub Actions are pinned to full commit hashes. Dependabot checks
these references weekly and proposes updates.

## Publishing

A `vX.Y.Z` tag matching the version in `pyproject.toml` triggers all quality
checks, builds the wheel and source distribution once, generates SHA-256
checksums, and publishes the same distributions in a GitHub Release.

PyPI publishing uses Trusted Publishing (OIDC), without a long-lived secret.
The PyPI publisher must target owner `fmaillar`, repository `cec-info`, workflow
`release.yml`, and GitHub environment `pypi`. The repository variable
`PYPI_PUBLISH` enables this step when set to `true`.

## Reading in Emacs

```elisp
(info "/path/to/catechisme.info")
```

## Installing in the user Info directory

```sh
mkdir -p ~/.local/share/info
cp catechisme.info ~/.local/share/info/
install-info ~/.local/share/info/catechisme.info ~/.local/share/info/dir
```

If Emacs does not already know this directory:

```elisp
(add-to-list 'Info-default-directory-list
             (expand-file-name "~/.local/share/info/"))
```

Then use `M-x info`, followed by `m Catéchisme` or `m Catechism`.

## Navigation

- `n`, `p`, `u`: next, previous, and parent node;
- `m`: select a menu entry;
- `i RET 2270 RET`: open the index entry for paragraph 2270;
- `s RET eucharistie RET`: full-text search.

The script automatically uses the `__P*.HTM` pages from IntraText. These are
the reading variants without thousands of concordance links.

## License and text copyright

The converter is distributed under the GNU General Public License, version 3
or any later version. See [LICENSE](LICENSE).

This license does not cover the Catechism text. The project distributes only
the converter; the text is downloaded from the official Vatican website when
generating the output and remains subject to its publisher's rights.

Report vulnerabilities privately according to the
[security policy](SECURITY.md), rather than opening a public issue.
