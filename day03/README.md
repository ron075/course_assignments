# Day 03 – Protein Analysis Studio

## Overview

Protein Analysis Studio is a desktop application for analyzing protein and antibody sequences.

It uses computational biology methods to calculate and visualize various protein properties, including:

- Molecular weight and amino acid composition.
- Hydrophobicity.
- Net charge and isoelectric point across different pH values.
- Potential cleavage sites and sequence features.
- Estimated protein half-life and atomic composition.

The application also supports fetching protein structures from the Protein Data Bank (PDB), selecting chains, and analyzing antibody regions.

## Technologies

- **Python** – Scientific calculations and application logic.
- **PySide6** – Desktop application.
- **HTML, CSS, JavaScript** – User interface and visualizations.
- **PDB** – Source of protein structure data.

All calculated biological values are computational estimates, not experimental measurements.

## How to Run

Requires Python 3.10 or newer.

**Windows:**
```powershell
py run_app.py
```

Alternatively, use `python run_app.py`.

**macOS / Linux:**
```bash
python3 run_app.py
```

The launcher automatically checks and installs missing Python dependencies from `requirements.txt`.

## AI-Assisted Development

Visual Studio Code Co-Pilot agent was used to generate the app

Main prompts and tasks included:

- Design a protein analysis application with scientific calculations and visualizations (references to the relevant calculation location and papers was supplied before hand).
- Implement functions for calculating protein properties from amino acid sequences.
- Integrate PDB fetching and protein chain selection.
- Add antibody analysis with separate Fc and Fab regions.
- Develop the desktop interface and help debug and improve the application.

## Git

Git integration in Visual Studio Code was used to manage the project and track changes as part of the assignment.