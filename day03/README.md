# Day 03 – Protein Analysis Studio

## Overview

Protein Analysis Studio is a desktop application for analyzing protein and antibody sequences.

It uses computational biology methods to calculate and visualize various protein properties, including:

- Molecular weight and amino acid composition.
- Hydrophobicity.
- A per-residue charge profile with an interactive pH slider and labeled sequence-position and charge axes, plus theoretical isoelectric point.
- Potential cleavage sites and sequence features.
- Estimated protein half-life and atomic composition.

The application also supports fetching protein structures from the Protein Data Bank (PDB), downloading fetched PDB files, uploading local PDB or mmCIF files, selecting chains, and analyzing antibody regions.

On the main screen, use **Clear sequence** to reset sequence inputs or **Clear PDB/CIF** to unload a fetched or uploaded structure. The desktop input layout is compacted to fit the window without a vertical scrollbar; the mobile layout remains scrollable.

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

On Windows, the launcher closes its console after starting the desktop app.

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

##Process

The development process was iterative: I started using chat-GPT to organise the wanted app and its strucutre (final app structure, as given to copilot, is included in "App_Design.txt").
After strucutre was given, Co-Pilot suggested to base the app on python, with html web page, styling in CSS and JavaScript for seamless injection of data analyzed and processed in python into the web page.
Following that, app was built feature by feature (copilot was told to "Build features step by step, with approval between each"). Copilot also performed code/app testing without prompting, speeding the entire process even further.

After the app as designedin the "App_Design" file was built, further improvements and features were added. 
For example:
"Add an import button, place it in the side bar above export"
"Remove the native title bar, add a custom circle close button with X to the top right corner, with padding around it"
"Add the graph bar from composition tab into hydrophobicity tab, group the bars by hydrophobic/neutral/hydrophilic. On "Hydrophobicity by residue" graph hover should show a tooltip with residue number, chain, Abb/letter and value"
"Add a residue charge profile to the Chemistry & charge tab with a pH slider and labeled sequence-position and charge axes."

Prompting stopped and final result was uploaded when layout and function was deemed good and easy to use.										