import pathlib
p = pathlib.Path("README.md")
text = p.read_text()
fence = chr(96) * 3

fixes = [
    ("## Architecture\ngenerate_data.py",
     "## Architecture\n" + fence + "\ngenerate_data.py"),
    ("sellers | brands | listings | reviews | signals | alerts\n\nRule engine",
     "sellers | brands | listings | reviews | signals | alerts\n" + fence + "\n\nRule engine"),
    ("## Setup\n\ngit clone",
     "## Setup\n\n" + fence + "\ngit clone"),
    ("pip install -r requirements.txt\n\n## Running it",
     "pip install -r requirements.txt\n" + fence + "\n\n## Running it"),
    ("## Running it\n\npython3 src/run_pipeline.py",
     "## Running it\n\n" + fence + "\npython3 src/run_pipeline.py"),
    ("streamlit run dashboard/app.py # investigator dashboard\n\nOr run each stage",
     "streamlit run dashboard/app.py # investigator dashboard\n" + fence + "\n\nOr run each stage"),
    ("single detector:\n\npython3 src/generate_data.py",
     "single detector:\n\n" + fence + "\npython3 src/generate_data.py"),
    ("python3 src/network_analysis.py # seller network clusters\n\nThe dashboard bootstraps",
     "python3 src/network_analysis.py # seller network clusters\n" + fence + "\n\nThe dashboard bootstraps"),
    ("## Tests\n\npip install pytest",
     "## Tests\n\n" + fence + "\npip install pytest"),
    ("python3 -m pytest tests/ -v\n\nSix tests:",
     "python3 -m pytest tests/ -v\n" + fence + "\n\nSix tests:"),
    ("## Repository layout\n\nsrc/ pipeline code",
     "## Repository layout\n\n" + fence + "\nsrc/ pipeline code"),
    ("tests/ automated tests, unit and integration\n\n## Findings so far",
     "tests/ automated tests, unit and integration\n" + fence + "\n\n## Findings so far"),
]

missing = 0
for old, new in fixes:
    if old in text:
        text = text.replace(old, new, 1)
    else:
        print("NOT FOUND, skipped:", old[:60].replace(chr(10), " / "))
        missing += 1

p.write_text(text)
print("done, " + str(len(fixes) - missing) + " of " + str(len(fixes)) + " fixes applied")
