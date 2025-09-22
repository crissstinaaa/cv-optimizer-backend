from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import pdfplumber
import docx
import textstat
import spacy

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

main = Blueprint('main', __name__)

# -------------------------
# Helper Functions
# -------------------------
def extract_text_from_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_docx(path):
    doc = docx.Document(path)
    return "\n".join(para.text for para in doc.paragraphs).strip()

def check_ats_issues_from_pdf(path):
    issues = {
        "tables": 0,
        "images": 0,
        "multi_column_lines": 0,
        "fancy_fonts": 0
    }
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            if page.find_tables():
                issues["tables"] += 1
            issues["images"] += len(page.images)
            text = page.extract_text() or ""
            for line in text.split('\n'):
                if line.count("  ") > 3 or "\t" in line:
                    issues["multi_column_lines"] += 1
            for obj in page.chars:
                font = obj.get("fontname", "").lower()
                if not any(f in font for f in ["arial", "times", "calibri", "helvetica"]):
                    issues["fancy_fonts"] += 1
                    break
    return issues

def extract_keywords(text):
    doc = nlp(text)
    return set(
        token.lemma_.lower()
        for token in doc
        if token.is_alpha and not token.is_stop and token.pos_ in {"NOUN", "PROPN", "VERB", "ADJ"}
    )

# -------------------------
# /analyze Endpoint
# -------------------------
@main.route("/analyze", methods=["POST"])
def full_resume_analysis():
    if 'file' not in request.files or 'job_description' not in request.form:
        return jsonify({"error": "file and job_description are required"}), 400

    file = request.files['file']
    job_description = request.form.get("job_description", "")
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext != 'pdf':
        return jsonify({"error": "Only PDF resumes are supported for full analysis"}), 400

    filename = secure_filename(file.filename)
    upload_dir = os.path.join(os.getcwd(), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    resume_text = extract_text_from_pdf(filepath)

    readability = {
        "flesch_reading_ease": textstat.flesch_reading_ease(resume_text),
        "flesch_kincaid_grade": textstat.flesch_kincaid_grade(resume_text),
        "smog_index": textstat.smog_index(resume_text),
        "coleman_liau_index": textstat.coleman_liau_index(resume_text),
        "automated_readability_index": textstat.automated_readability_index(resume_text),
        "dale_chall_score": textstat.dale_chall_readability_score(resume_text),
        "difficult_words": textstat.difficult_words(resume_text),
        "reading_time_minutes": round(textstat.reading_time(resume_text), 2),
        "summary": textstat.text_standard(resume_text)
    }

    ats_issues = check_ats_issues_from_pdf(filepath)
    deductions = 0
    if ats_issues["tables"]: deductions += 20
    if ats_issues["images"]: deductions += 20
    if ats_issues["multi_column_lines"] > 3: deductions += 20
    if ats_issues["fancy_fonts"]: deductions += 10
    ats_score = max(100 - deductions, 0)
    ats_summary = "High ATS compatibility" if ats_score >= 80 else "May have ATS issues"

    resume_keywords = extract_keywords(resume_text)
    jd_keywords = extract_keywords(job_description)
    matched = sorted(list(resume_keywords & jd_keywords))
    missing = sorted(list(jd_keywords - resume_keywords))
    match_percent = round((len(matched) / max(len(jd_keywords), 1)) * 100, 2)

    return jsonify({
        "match_percent": match_percent,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "readability": readability,
        "ats_check": {
            "ats_friendly_score": f"{ats_score}%",
            "issues_found": ats_issues,
            "summary": ats_summary
        }
    }), 200

# Register Blueprint

def register_routes(app):
    app.register_blueprint(main)
