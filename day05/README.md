#Day 05 — Protein Analysis Studio

Protein Analysis Studio has a PySide6 desktop interface and a Flask web
interface. Both use the same Python analysis logic.

## What changed

This assignment adds a `pytest` suite and a **Testing** page in the app. The
page can run offline tests, online reference comparisons, or both. It shows
the latest status, counts, test details, logs, and—when a reference result is
available—a comparison with the app's result.

Offline tests cover sequence handling, calculations, structure parsing,
reporting, and app services. Online tests compare analyses with public
references such as RCSB, ScanProsite, ExPASy ProtParam, and PeptideCutter.
Calculations for molecular weight, pI, and protease cleavage were aligned with
the conventions used by their linked calculators.

## Install dependencies

All desktop, web, and testing dependencies are in one file:

```powershell
python -m pip install -r requirements.txt
```

## Start the app

From the `day05` folder, run either interface:

```powershell
python run_app.py
```

```powershell
python run_web.py
```

In the app, open **Testing** and choose the offline, online, or all-tests
action. Review and confirm the test inputs in the dialog before the run.

## Run tests from the command line

Run the offline suite (online checks are skipped by default):

```powershell
python -m pytest -v
```

Run offline and online checks:

```powershell
python -m pytest -v --run-online
```

Online checks require an internet connection and send the configured protein
sequence to external analysis services; RCSB checks query the PDB identifier.
Uploaded structure files are parsed locally. The saved 9NND inputs are
configured in `tests/online_validation.json`. A valid `service_email` is
needed for some EMBL-EBI checks. Leave online checks disabled if you do not
want to make external requests.

## Reading the results

- **Passed** means the expected behavior or reference comparison matched.
- **Failed** means an assertion failed or the app result differed from the
  reference.
- **Skipped** means an online check was not enabled, its required input or
  contact email was unavailable, or no equivalent reference was available.

Some online comparisons rely on linked web forms because those calculators
do not document a REST API. Their availability or output format may change.
