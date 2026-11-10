# Day 04 – Protein Analysis Studio

## Overview

The project continues the Day 03 assignment. The original desktop application was preserved, and a Flask-based web interface was added. Both interfaces use the same underlying Python business logic.

## How to Run

Requires Python 3.10 or newer.

### Desktop Mode

**Windows:**

```powershell
py run_app.py
```

Alternatively:

```powershell
python run_app.py
```

On Windows, the launcher closes its console after starting the desktop application.

**macOS / Linux:**

```bash
python3 run_app.py
```

The launcher automatically checks for and installs missing Python dependencies from `requirements.txt`.

### Web Mode

Start the Flask web application from the `day04` folder.

**Windows:**

```powershell
py -m pip install -r requirements.txt
py run_web.py
```

The launcher opens `http://127.0.0.1:5000` in the default browser.

The desktop application remains available through `run_app.py`.

### AI-Assisted Development

Github copilot was given these following prompts:

**Adding web mode:**

"look at day04 folder, in addition to the current desktop mode, add a web mode with flask"

**Adjusting web-specific settings:**

"1) When using web mode, from the settings, remove the full screen and start minimized options.

2) When using Ab mode, should do 2 things:
A) Ask player for chain count instead of applying them automatically based on Ab class.
B) Should show the same tabs as for normal proteins: overview, composition, chemistry and charge, sequence features, cleavage."

## Git

Git integration in Visual Studio Code was used to manage the project and track changes throughout the assignment.

## Assignment

This project fulfills the Day 04 assignment by taking the previous implementation, preserving it, and adding a web application that reuses its existing business logic.

The original desktop application remains available, alongside the new Flask-based web interface.