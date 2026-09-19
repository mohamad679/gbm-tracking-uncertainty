# Contributing

Thanks for contributing to the GBM tracking uncertainty audit.

## Development setup

Use a supported Python version (3.11, 3.12, or 3.13):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints.txt -e . coverage
```

On Windows PowerShell use `.venv\Scripts\Activate.ps1`.

## Before opening a pull request

Run the test suite and coverage gate:

```bash
coverage run --source=gbm_audit -m unittest discover -s tests -q
coverage report --show-missing --fail-under=65
```

Changes affecting packaging should also build and install a wheel successfully.

## Scientific-change requirements

Changes that can affect numerical benchmark outputs must:

1. include a regression test;
2. preserve artifact schema/provenance contracts or document a schema migration;
3. rerun the full U373 reproduction workflow;
4. update `docs/reproduced-results-2026-09-19.json` and the relevant report when results change;
5. clearly distinguish technical benchmark evidence from biological interpretation.

Do not commit raw datasets or generated `results/` artifacts unless the repository policy is intentionally changed.

## Pull requests

Keep changes focused. Describe:

- the problem being solved;
- implementation approach;
- tests added or updated;
- whether scientific outputs changed;
- reproduction run IDs when relevant.

A change should not be described as a biological validation unless a dedicated biological validation study and reference are added explicitly.
