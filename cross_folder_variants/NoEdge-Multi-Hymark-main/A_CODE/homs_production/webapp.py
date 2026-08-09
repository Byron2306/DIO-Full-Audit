from flask import Flask, request, redirect, url_for, send_from_directory, jsonify, render_template, flash
from pathlib import Path
from homs.core.workflow_engine import WorkflowEngine
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-secret-in-production'

BASE = Path(__file__).resolve().parent
REF_DIR = BASE / 'references'
SUB_DIR = BASE / 'submissions'
OUT_DIR = BASE / 'output'
LOG_DIR = BASE / 'logs'
PROGRESS_FILE = OUT_DIR / 'progress.txt'

REF_DIR.mkdir(exist_ok=True)
SUB_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


def list_reports():
    return sorted([f.name for f in OUT_DIR.iterdir() if f.is_file()], reverse=True)


def tail_text(path: Path, max_lines: int = 200) -> str:
    if not path.exists():
        return ''
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception:
        return ''


@app.route('/')
def index():
    reports = list_reports()
    references = [p.name for p in REF_DIR.iterdir() if p.is_file()]
    submissions = [p.name for p in SUB_DIR.iterdir() if p.is_file()]
    return render_template('index.html', reports=reports, references=references, submissions=submissions)


@app.route('/status')
def status():
    # Live progress feed (polled by UI)
    progress = tail_text(PROGRESS_FILE, max_lines=200)
    return jsonify({"progress": progress})


@app.route('/upload_reference', methods=['GET', 'POST'])
def upload_reference():
    if request.method == 'POST':
        ref_file = request.files.get('reference')
        ref_name = request.form.get('ref_name') or None
        if not ref_file:
            flash('No reference file provided', 'danger')
            return redirect(url_for('upload_reference'))
        suffix = Path(ref_file.filename).suffix or ''
        target_name = f"{ref_name or Path(ref_file.filename).stem}{suffix}"
        target = REF_DIR / target_name
        ref_file.save(target)
        flash(f'Reference {target_name} uploaded', 'success')
        return redirect(url_for('index'))
    return render_template('upload_reference.html')


@app.route('/upload_submission', methods=['GET', 'POST'])
def upload_submission():
    if request.method == 'POST':
        submission = request.files.get('submission')
        student_id = request.form.get('student_id')
        if not submission or not student_id:
            flash('Student ID and submission file required', 'danger')
            return redirect(url_for('upload_submission'))
        sub_path = SUB_DIR / f"{student_id}{Path(submission.filename).suffix}"
        submission.save(sub_path)
        flash(f'Submission for {student_id} uploaded', 'success')
        return redirect(url_for('index'))
    return render_template('upload_submission.html')


@app.route('/assess_single', methods=['POST'])
def assess_single():
    student_id = request.form.get('student_id')
    reference_name = request.form.get('reference_name')
    if not student_id or not reference_name:
        flash('Student ID and reference name are required', 'danger')
        return redirect(url_for('index'))

    candidates = list(SUB_DIR.glob(f"{student_id}.*"))
    if not candidates:
        flash(f'No submission found for {student_id}', 'warning')
        return redirect(url_for('index'))
    submission_path = candidates[0]

    ref_matches = list(REF_DIR.glob(f"{reference_name}*"))
    if not ref_matches:
        flash(f'Reference {reference_name} not found', 'warning')
        return redirect(url_for('index'))

    engine = WorkflowEngine(Path('config.json'))
    engine.assessment_agent.load_reference(reference_name, ref_matches[0])

    if submission_path.suffix == '.py':
        result = engine.assessment_agent.assess_submission(submission_path, reference_name, student_id)
        out_path = OUT_DIR / f'assessment_{student_id}.json'
        out_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        return render_template('result.html', result=result)
    else:
        results = engine.run_assessment_only(SUB_DIR, reference_name)
        out_path = OUT_DIR / f'assessment_batch_{student_id}.json'
        out_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
        return render_template('results_batch.html', results=results)


@app.route('/reports')
def reports():
    files = list_reports()
    embedded_html = None
    summary_path = OUT_DIR / 'summary_report.html'
    if summary_path.exists():
        try:
            embedded_html = summary_path.read_text(encoding='utf-8')
        except Exception:
            embedded_html = None
    return render_template('reports.html', files=files, embedded_html=embedded_html)


@app.route('/reports/<path:filename>')
def get_report(filename):
    return send_from_directory(str(OUT_DIR), filename)


@app.route('/reports/preview/<path:filename>')
def preview_report(filename):
    target = OUT_DIR / filename
    if not target.exists() or not target.is_file():
        return f"Report {filename} not found", 404
    suffix = target.suffix.lower()
    try:
        text = target.read_text(encoding='utf-8')
    except Exception:
        return f"Unable to read {filename}", 500

    if suffix == '.html':
        return text
    if suffix == '.json':
        try:
            obj = json.loads(text)
            pretty = json.dumps(obj, indent=2)
        except Exception:
            pretty = text
        return render_template('preview.html', filename=filename, content=pretty, is_html=False)
    if suffix == '.csv':
        rows = [r.split(',') for r in text.strip().splitlines() if r.strip()]
        return render_template('preview.html', filename=filename, table=rows, is_csv=True)

    return render_template('preview.html', filename=filename, content=text, is_html=False)


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(str(BASE / 'static'), filename)


if __name__ == '__main__':
    app.run(port=5052, debug=True)
