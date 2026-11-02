# Hi, I'm Ron Shaked

This is my main course repository, where i would upload my different assigments!

# Day 01 – Assignment

## Website Setup

I used **Jekyll** to create and test my website locally on my laptop.

After finishing the initial setup, I pushed the website to GitHub using the `master` branch and configured GitHub Pages to use the `master` branch with `/docs` as the publishing folder.

My `docs` folder contains all the files from my local website directory, since I pushed the entire folder to GitHub.

In my particular case, I think I could have published the website using only these three files:

- `_config.yml` – Contains the text and other variables displayed on the website.
- `index.markdown` – Contains the actual webpage structure, styling, and references to the variables defined in `_config.yml`.
- `404.html` – Handles requests to nonexistent URLs.

However, I wanted to keep a backup of all the files, so I uploaded the entire directory. I also haven't tested whether the website works with only those three files.

## Git and `.gitignore`

From my current understanding, if I wanted to push only specific files, I could add the names of the files and folders I wanted to exclude to `.gitignore`.

These files would then be ignored by Git when using commands such as `git add`.

## Ruby Dependencies

Regarding `Gemfile` and `Gemfile.lock`, these are Ruby dependency files used by Jekyll.

They help manage the dependencies required to build the website and maintain consistent dependency versions.

They were created during the initial setup:

1. `bundle init` – Created the `Gemfile`.
2. `bundle install` – Installed the dependencies listed in the `Gemfile` and generated `Gemfile.lock`.

## Website Design and ChatGPT Assistance

I wrote most of `_config.yml` myself (although Jekyll generated an initial template).

The styling in `index.markdown` was also mostly done by me through trial and error.

I used ChatGPT for assistance with two specific parts of the design:

- The animated linear-gradient background.
- The custom scrollbar.

ChatGPT provided the initial code, which I then modified and refined through online research and testing. For example, I adjusted the gradient colors and animation speed and fixed the seamless-repeat issue.

### Prompts used with ChatGPT

**Gradient background:**

> In code form. Animate background as gradient, white on left side, changing colors on right side.

**Custom scrollbar:**

> In code form. I want to style the scroll bar, so it is transparent and the handle is just a floating circle going up and down.

# Day 02 – Assignment

## Python

Installed Python and configured Visual Studio Code to run Python programs.

Created a Python file called `main.py` containing:

```python
print("Hello world")
```

Ran the program successfully and verified that it prints `Hello world` to the screen.

## GitHub

- Created a new GitHub repository for the course assignments.
- Cloned the repository to my local computer.
- Created a `README.md` file describing the repository.
- Created a `day02` folder and added the Python program.
- Pushed the changes to GitHub.

## Issues

Practiced opening and closing of issue on other students repositories.

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