# HOMS - Hybrid Offline Marking System

Minimal local scaffold of the HOMS project for quick setup and smoke tests.

Quick start

1. Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run a basic import smoke test:

```powershell
python -c "from homs.utils.report_generator import ReportGenerator; print('reportgen ok')"
```

Files created:
- `homs/` package with core agents and utils
- `main.py` CLI entrypoint
- `config.json` default configuration
- `requirements.txt`
# HOMS (scaffold)

This workspace contains a scaffold of the Hybrid Offline Marking System (HOMS).

Quick start:

1. Create a Python virtual environment and activate it.

```bash
python -m venv venv
venv\Scripts\activate    # Windows
# or: source venv/bin/activate    # macOS/Linux
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run a quick import test:

```bash
python -c "import homs; print(homs.__version__)"
```

4. Create an eFundi session (one-time login, saves cookies):

```bash
python scripts/efundi_session.py
```

5. (Optional) eFundi packaging + upload workflow

Update `config.json`:

```json
"efundi": {
  "package": true,
  "download_zip": "C:/Users/User/Downloads/Assignment 1 - ...zip",
  "output_zip": "./output/efundi_upload.zip",
  "feedback_dir": "./output/efundi_feedback",
  "comments_json": "./output/comments.json",
  "student_id_map": {}
}
```

Then run the normal workflow; it will repackage the zip for Upload All.

5. Parse rubrics (docx) and run assessments:

```bash
# rubrics will be parsed automatically based on config.json
python main.py run ./submissions reference_name --output ./output
```
