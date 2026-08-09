# HOMS V3.0 - Hybrid Offline Marking System

Installer behaviour
- Creates homs_production next to the installer file.
- Creates venv and installs dependencies immediately.

Compile reference
venv\Scripts\python scripts\compile_reference.py --notebook reference.ipynb --out data\references\reference.pkl

Run workflow
venv\Scripts\python main.py run <DROP_FOLDER> reference_name --reference-path data/references/reference.pkl --output output

eFundi packaging (Upload All)
1) Edit config.json -> efundi section
2) Run workflow, it will repackage the downloaded zip:
   venv\Scripts\python main.py run <DROP_FOLDER> reference_name --output output

eFundi session (Playwright)
venv\Scripts\python scripts\efundi_session.py
