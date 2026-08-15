# Contributing to cec2info

Thank you for contributing to `cec2info`. Focused changes with tests and
compatibility with Python 3.10 or later are preferred.

## Preparing the environment

```sh
git clone https://github.com/fmaillar/cec-info.git
cd cec-info
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Texinfo and TeX tools are optional for Python-only tests, but required to
validate actual Info, PDF, and EPUB output.

## Proposing a change

1. Open an issue first for a significant feature.
2. Keep each commit focused on one coherent change.
3. Add or update tests for changed behavior.
4. Run the local checks:

   ```sh
   make check
   python -m build
   ```

5. Open a pull request describing the problem, solution, and validation.

Do not commit the Vatican cache, generated documents, or virtual environments.
By contributing, you agree that your contribution is distributed under the
GPL-3.0-or-later license.
