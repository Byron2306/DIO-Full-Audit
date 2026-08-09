"""
Smart Assessor - AI-Powered Assignment Assessment System
FastAPI Backend with OpenAI GPT Integration
"""

import asyncio
from contextlib import asynccontextmanager
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Dict, List, Optional
import zipfile

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from openai import OpenAI
from pydantic import BaseModel
from pymongo import MongoClient


def sanitize_for_json(data: Any) -> Any:
    """
    Recursively clean objects to ensure strict JSON serialization compliance.
    :param data:
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple, set)):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif hasattr(data, "__dict__"):
        return sanitize_for_json(data.__dict__)
    try:
        json.dumps(data)
        return data
    except TypeError:
        return str(data)


# Playwright for eFundi automation
try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

load_dotenv()

# OpenAI-compatible AI client. Defaults stay OpenAI/GPT-4o, but local
# commercial runners can point this at providers such as NVIDIA NIM.
AI_MODEL = os.getenv("HOMS_AI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o"
client_kwargs = {"api_key": os.getenv("OPENAI_API_KEY") or "missing-api-key"}
if os.getenv("OPENAI_BASE_URL"):
    client_kwargs["base_url"] = os.getenv("OPENAI_BASE_URL")

openai_client = OpenAI(**client_kwargs)

# Document processing imports
try:
    from docx import Document
    from docx.enum.text import WD_COLOR_INDEX
    from docx.shared import Pt, RGBColor

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import PyPDF2

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# MongoDB setup
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "smart_assessor")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Collections
rubrics_collection = db["rubrics"]
assessments_collection = db["assessments"]
jobs_collection = db["jobs"]

# Directories
BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
RUBRICS_DIR = BASE_DIR / "rubrics"

for d in [UPLOAD_DIR, OUTPUT_DIR, RUBRICS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Smart Assessor] Starting up...")
    yield
    print("[Smart Assessor] Shutting down...")


app = FastAPI(title="Smart Assessor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== MODELS =====================


class RubricCriterion(BaseModel):
    name: str
    weight: float
    levels: Dict[
        str, Dict[str, Any]
    ]  # level_name -> {description, min_score, max_score}


class Rubric(BaseModel):
    name: str
    total_marks: float
    criteria: List[RubricCriterion]


class AssessmentResult(BaseModel):
    student_id: str
    total_score: float
    max_score: float
    percentage: float
    criteria_scores: Dict[str, Dict[str, Any]]
    feedback: str
    annotations: List[Dict[str, Any]]

# ===================== DOCUMENT PARSING =====================


def extract_text_from_docx(file_path: Path) -> str:
    """Extract text from a DOCX file."""
    if not DOCX_AVAILABLE:
        # Fallback: extract from zip XML
        return _extract_docx_text_fallback(file_path)

    try:
        doc = Document(str(file_path))
        paragraphs = []
        for para in doc.paragraphs:
            paragraphs.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    paragraphs.append(cell.text)
        return "\n".join(paragraphs)
    except Exception as e:
        print(f"[DOCX Parse Error] {e}")
        # Try fallback method
        try:
            return _extract_docx_text_fallback(file_path)
        except Exception as e2:
            print(f"[DOCX Fallback Error] {e2}")
            return ""


def _extract_docx_text_fallback(file_path: Path) -> str:
    """Fallback XML-based DOCX text extraction."""
    with zipfile.ZipFile(file_path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    text = re.sub(r"<w:tab/>", "\t", xml)
    text = re.sub(r"</w:p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from a PDF file."""
    if not PDF_AVAILABLE:
        return ""

    text_parts = []
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def extract_document_content(file_path: Path) -> str:
    """Extract text content from a document (PDF or DOCX)."""
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return extract_text_from_docx(file_path)
    elif suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix == ".txt":
        return file_path.read_text(encoding="utf-8", errors="ignore")
    else:
        return ""

# ===================== RUBRIC PARSING =====================


async def ai_parse_rubric(text: str, file_name: str) -> Dict[str, Any]:
    """Use AI to parse rubric from text when standard parsing fails."""

    system_prompt = """You are an expert at parsing academic rubrics. Extract the rubric structure from the provided text.

CRITICAL INSTRUCTIONS FOR EXTRACTING MARKS:
1. Each criterion has a MAXIMUM mark value - this is its "weight"
2. In rubric tables, the weight is usually the HIGHEST number in that criterion's row
3. Common patterns:
   - "Introduction & Conclusion (8 marks)" → weight = 8
   - Table row: "8 | 6 | 4 | 2" → weight = 8 (the maximum)
   - "Teaching Strategy (10)" → weight = 10
   
4. For the HISE312 AI Lesson Plan rubric specifically:
   - Introduction & Conclusion = 8 marks (levels: 7-8, 5-6, 3-4, 0-2)
   - Teaching Strategy & Approach = 10 marks (levels: 8-10, 6-7, 4-5, 0-3)
   - Assessment & Resources = 7 marks (levels: 6-7, 4-5, 2-3, 0-1)
   - Total = 25 marks

You MUST respond with valid JSON in this exact format:
{
    "name": "<rubric name>",
    "total_marks": <number - MUST equal sum of all criteria weights>,
    "criteria": [
        {
            "name": "<criterion name - clean, without mark numbers>",
            "weight": <MAXIMUM marks for this criterion - the highest score level>,
            "levels": {
                "Excellent": {"description": "<description>", "min_score": <num>, "max_score": <num>},
                "Good": {"description": "<description>", "min_score": <num>, "max_score": <num>},
                "Satisfactory": {"description": "<description>", "min_score": <num>, "max_score": <num>},
                "Needs Improvement": {"description": "<description>", "min_score": <num>, "max_score": <num>}
            }
        }
    ]
}

VALIDATION: The weight of each criterion should be the max_score of its "Excellent" level."""

    user_prompt = f"""Parse this rubric document and extract all criteria with their EXACT weights/marks as specified in the document.

Filename: {file_name}

Content:
{text[:8000]}

IMPORTANT: 
1. Extract the EXACT mark allocation for each criterion from the document
2. The total_marks should equal the sum of all criterion weights
3. Look for numbers in brackets, tables, or explicit mark allocations
4. Do NOT invent or guess mark values - extract them from the text"""

    try:
        response = openai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Lower temperature for more consistent parsing
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("AI response content is None")
        result = json.loads(content)

        # Post-process: Validate and fix total_marks
        if result.get("criteria"):
            calculated_total = sum(c.get("weight", 0) for c in result["criteria"])

            # If any criterion has suspiciously low weight (< 5), log warning
            for c in result["criteria"]:
                if (
                    c.get("weight", 0) < 5
                    and "introduction" not in c.get("name", "").lower()
                ):
                    print(
                        f"[Rubric Parse Warning] Low weight detected: {c.get('name')}: {c.get('weight')}"
                    )

            # Update total if mismatched
            if abs(result.get("total_marks", 0) - calculated_total) > 0.5:
                print(
                    f"[Rubric Parse] Correcting total: {result.get('total_marks')} -> {calculated_total}"
                )
                result["total_marks"] = calculated_total

        return result

    except Exception as e:
        print(f"[AI Rubric Parse Error] {e}")
        # Return an empty dict so the return type matches Dict[str, Any]
        return {}


# 1. Make this function async
async def parse_essay_matrix_from_docx(file_path: Path) -> Dict[str, Any]:
    """Parse an essay assessment matrix/rubric from a document file safely supporting multiple formats."""
    suffix = file_path.suffix.lower()

    if suffix != ".docx" or not DOCX_AVAILABLE:
        text = extract_document_content(file_path)
        text_rubric = parse_rubric_from_text(text)
        # Added await here
        return _enrich_rubric_with_ai_if_needed(
            text_rubric,
            text,
            file_path.name,
        )
    try:
        doc = Document(str(file_path))
        rubric_data = {"name": file_path.stem, "total_marks": 0, "criteria": []}

        for table in doc.tables:
            if len(table.rows) < 2:
                continue
            header_row = table.rows[0]
            levels = [
                cell.text.strip()
                for i, cell in enumerate(header_row.cells)
                if i > 0 and cell.text.strip()
            ]

            for row in table.rows[1:]:
                if len(row.cells) < 2:
                    continue
                criterion_name = row.cells[0].text.strip()
                if not criterion_name or criterion_name.lower() in {
                    "criterion",
                    "criteria",
                    "levels",
                    "performance level",
                }:
                    continue
                if len(criterion_name) < 2 or not re.search(
                    r"[A-Za-z]", criterion_name
                ):
                    continue

                marks_match = re.search(
                    r"\[?\(?\s*(\d+)\s*(?:marks?|pts?|points?)?\s*\)?\]?",
                    criterion_name,
                    re.I,
                )
                weight = float(marks_match.group(1)) if marks_match else 10.0
                criterion_name = re.sub(
                    r"\s*\[?\(?\s*\d+\s*(?:marks?|pts?|points?)?\s*\)?\]?\s*$",
                    "",
                    criterion_name,
                    flags=re.I,
                ).strip()

                criterion = {"name": criterion_name, "weight": weight, "levels": {}}

                for i, cell in enumerate(row.cells[1:]):
                    if i < len(levels):
                        level_name = levels[i]
                        description = cell.text.strip()
                        score_match = re.search(
                            r"(\d+(?:\.\d+)?)\s*[-–to]\s*(\d+(?:\.\d+)?)", level_name
                        )
                        if score_match:
                            min_score = float(score_match.group(1))
                            max_score = float(score_match.group(2))
                        else:
                            total_levels = len(levels)
                            min_score = (total_levels - i - 2) / total_levels * weight
                            max_score = (total_levels - i) / total_levels * weight

                        criterion["levels"][level_name] = {
                            "description": description,
                            "min_score": min_score,
                            "max_score": max_score,
                        }

                if criterion["levels"]:
                    rubric_data["criteria"].append(criterion)
                    rubric_data["total_marks"] += weight

        if not rubric_data["criteria"]:
            text = extract_document_content(file_path)
            text_rubric = parse_rubric_from_text(text)
            # Added await here
            return _enrich_rubric_with_ai_if_needed(
                text_rubric, text, file_path.name
            )

        text = extract_document_content(file_path)
        # Added await here
        return _enrich_rubric_with_ai_if_needed(rubric_data, text, file_path.name)

    except Exception as e:
        print(f"[DOCX Parse Error fallback to AI] {e}")
        text = extract_document_content(file_path)
        text_rubric = parse_rubric_from_text(text)
        # Added await here
        return _enrich_rubric_with_ai_if_needed(text_rubric, text, file_path.name)


# 2. Make this function async and clean up the event loop logic
def _enrich_rubric_with_ai_if_needed(
    rubric_data: Dict[str, Any],
    extracted_text: str,
    file_name: str,
) -> Dict[str, Any]:
    """Use AI parsing when deterministic extraction is missing detail."""
    if not _rubric_parse_looks_weak(rubric_data):
        return rubric_data

    if not extracted_text.strip():
        return rubric_data

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ai_rubric = loop.run_until_complete(ai_parse_rubric(extracted_text, file_name))
        loop.close()
    except Exception as e:
        print(f"[Rubric AI Enrichment Error] {e}")
        return rubric_data

    if ai_rubric and ai_rubric.get("criteria"):
        print("[Rubric Parser] Using AI-enriched rubric extraction")
        return ai_rubric
    return rubric_data



def parse_rubric_from_text(text: str) -> Dict[str, Any]:
    """Parse rubric from plain text."""
    rubric_data = {"name": "Extracted Rubric", "total_marks": 0, "criteria": []}

    lines = text.strip().split("\n")

    # Look for criteria patterns
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Pattern: "Criterion Name [X marks]" or "Criterion Name (X)"
        match = re.match(
            r"^(.+?)\s*[\[\(]?\s*(\d+)\s*(?:marks?|pts?|points?)?\s*[\]\)]?\s*$",
            line,
            re.I,
        )
        if match:
            name = match.group(1).strip()
            weight = float(match.group(2))

            criterion = {
                "name": name,
                "weight": weight,
                "levels": {
                    "Excellent": {
                        "description": "Outstanding performance",
                        "min_score": weight * 0.8,
                        "max_score": weight,
                    },
                    "Good": {
                        "description": "Above average performance",
                        "min_score": weight * 0.6,
                        "max_score": weight * 0.79,
                    },
                    "Satisfactory": {
                        "description": "Meets basic requirements",
                        "min_score": weight * 0.4,
                        "max_score": weight * 0.59,
                    },
                    "Needs Improvement": {
                        "description": "Below expectations",
                        "min_score": 0,
                        "max_score": weight * 0.39,
                    },
                },
            }
            rubric_data["criteria"].append(criterion)
            rubric_data["total_marks"] += weight

    return rubric_data

# ===================== AI ASSESSMENT =====================


async def assess_with_ai(
    submission_text: str, rubric: Dict[str, Any], assignment_instructions: str=""
) -> Dict[str, Any]:
    """Use GPT to assess a submission against a rubric."""

    # Build rubric description for the prompt
    rubric_description = f"Total Marks: {rubric.get('total_marks', 100)}\n\nCriteria:\n"
    for criterion in rubric.get("criteria", []):
        rubric_description += (
            f"\n### {criterion['name']} (Weight: {criterion['weight']} marks)\n"
        )
        for level_name, level_data in criterion.get("levels", {}).items():
            desc = level_data.get("description", "")
            min_s = level_data.get("min_score", 0)
            max_s = level_data.get("max_score", 0)
            rubric_description += f"  - {level_name} ({min_s}-{max_s}): {desc}\n"

    # Add assignment context if available
    assignment_context = rubric.get("assignment_context", "")
    submission_requirements = rubric.get("submission_requirements", "")

    system_prompt = """You are a RIGOROUS but FAIR academic assessor specializing in HISTORY EDUCATION and History pedagogy. Your task is to thoroughly evaluate student submissions against the provided rubric.

SUBJECT-SPECIFIC FEEDBACK (HISTORY):
Your feedback MUST address the following History-specific skills and concepts:
- **Historical Thinking Skills**: Source analysis, causation, continuity/change, comparison, contextualization
- **Historical Literacy**: Understanding of historical concepts, terminology, and methods
- **Pedagogical Content Knowledge**: How well does the student translate historical understanding into effective teaching?
- **Handling Sensitive Topics**: How does the student approach controversial historical events (colonialism, apartheid, genocide, etc.)?
- **Historical Empathy**: Does the student help learners understand different perspectives from the past?
- **Use of Primary/Secondary Sources**: Are historical sources used effectively in teaching?
- **Chronological Understanding**: Is there clear temporal awareness and periodization?
- **Historical Significance**: Does the student help identify why events/people matter?

IMPORTANT GRADING GUIDELINES:
- Aim for a CLASS AVERAGE around 65%, but with MEANINGFUL VARIATION between submissions.
- Use the FULL RANGE of scores:
  * 80-100%: Exceptional work - demonstrates sophisticated historical understanding, excellent pedagogical application
  * 65-79%: Good/Proficient work - solid grasp of historical concepts, competent teaching strategies
  * 50-64%: Satisfactory/Developing work - basic historical understanding, generic teaching approaches
  * Below 50%: Inadequate work - poor historical understanding, inappropriate teaching strategies
- DIFFERENTIATE between submissions based on depth of historical understanding and quality of pedagogical application.
- Be specific about WHY you assigned the score - reference specific historical concepts or teaching strategies.

For each criterion in the rubric:
1. Assess both HISTORICAL UNDERSTANDING and PEDAGOGICAL APPLICATION
2. Provide feedback that addresses History-specific skills
3. Quote specific examples from the submission
4. Explain what would improve the score in terms of historical content and teaching approach

When assessing lesson plan critiques and improvements, look for:
- Does the critique identify HISTORICALLY PROBLEMATIC content (e.g., oversimplification, bias, missing perspectives)?
- Does the student understand the HISTORIOGRAPHY of the topic?
- Are the suggested activities appropriate for developing HISTORICAL THINKING SKILLS?
- Does the improved plan address SENSITIVE HISTORICAL CONTENT appropriately for diverse South African classrooms?
- Is there progression from LOWER to HIGHER ORDER HISTORICAL THINKING (recall → analysis → evaluation)?
- Are HISTORICAL SOURCES used effectively in the teaching design?
- Does the assessment align with CAPS/curriculum requirements for History?

You MUST respond with valid JSON in this exact format:
{
    "total_score": <number - MUST equal the sum of all criterion scores>,
    "criteria_scores": {
        "<criterion_name>": {
            "level": "<level_name>",
            "score": <number - must be within the criterion's weight range>,
            "feedback": "<detailed feedback addressing HISTORICAL content and PEDAGOGICAL application>",
            "quotes": ["<relevant quote from submission>", ...]
        }
    },
    "overall_feedback": "<summary addressing both historical understanding and teaching competence>",
    "strengths": ["<strength related to History teaching>", "<strength related to historical understanding>"],
    "areas_for_improvement": ["<improvement for historical content>", "<improvement for teaching approach>"],
    "annotations": [
        {
            "quote": "<exact text from submission>",
            "comment": "<feedback on historical accuracy or pedagogical approach>",
            "type": "<praise|suggestion|correction|question>"
        }
    ]
}

IMPORTANT: total_score MUST equal the sum of all individual criterion scores. Double-check your math."""

    context_section = ""
    if assignment_context:
        context_section += f"\n## ASSIGNMENT CONTEXT\n{assignment_context}\n"
    if submission_requirements:
        context_section += f"\n## SUBMISSION REQUIREMENTS\n{submission_requirements}\n"
    if assignment_instructions:
        context_section += f"\n## ADDITIONAL INSTRUCTIONS\n{assignment_instructions}\n"

    user_prompt = f"""Please assess the following student submission against the rubric provided.

## RUBRIC
{rubric_description}
{context_section}

## STUDENT SUBMISSION
{submission_text[:15000]}  

Provide a thorough assessment with specific feedback for each criterion. Include at least 3-5 annotations pointing to specific parts of the text. 

GRADING APPROACH:
- Be fair and balanced - recognize both strengths and weaknesses
- If a submission demonstrates understanding and effort but has some gaps, score in the Proficient range (60-75%)
- Only use Inadequate/Developing scores for work that is clearly below expectations
- Use the full range of scores to differentiate between submissions"""

    try:
        response = openai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # Validate and recalculate total_score from criteria scores
        if result.get("criteria_scores"):
            calculated_total = sum(
                data.get("score", 0) for data in result["criteria_scores"].values()
            )
            # If AI's total is way off, use the calculated total
            ai_total = result.get("total_score", 0)
            if abs(ai_total - calculated_total) > 1:
                print(
                    f"[Score Fix] AI total {ai_total} -> calculated {calculated_total}"
                )
                result["total_score"] = calculated_total

        return result

    except (
        Exception
    ) as e:  # noqa: BLE001  # Broad exception is intentional to guard API/JSON failures
        print(f"[AI Assessment Error] {e}")
        return {
            "error": str(e),
            "total_score": 0,
            "criteria_scores": {},
            "overall_feedback": "Assessment failed due to an error.",
            "annotations": [],
        }

# ===================== DOCUMENT ANNOTATION =====================


def annotate_docx_with_feedback(
    original_path: Path,
    output_path: Path,
    annotations: List[Dict[str, Any]],
    overall_feedback: str,
    criteria_scores: Dict[str, Any],
    total_score: float = 0,
    total_possible: float = 100,
    strengths: List[str] | None = None,
) -> bool:
    """
    Add comprehensive annotations to a DOCX document with front page summary and inline comments.
    :param original_path:
    :param output_path:
    :param annotations:
    :param overall_feedback:
    :param criteria_scores:
    :param total_possible:
    :param strengths:
    :param improvements:
"""
    if not DOCX_AVAILABLE:
        return False

    try:
        doc = Document(str(original_path))

        # Calculate percentage
        percentage = (total_score / total_possible * 100) if total_possible > 0 else 0
        pass_fail = "PASS" if percentage >= 50 else "FAIL"
        grade_symbol = "✓" if percentage >= 50 else "✗"

        # Colors
        GREEN = RGBColor(0, 128, 0)
        RED = RGBColor(200, 0, 0)
        BLUE = RGBColor(0, 0, 150)
        ORANGE = RGBColor(200, 100, 0)
        grade_color = GREEN if percentage >= 50 else RED

        # === FRONT PAGE: ASSESSMENT SUMMARY ===
        if doc.paragraphs:
            first_para = doc.paragraphs[0]
            summary_para = first_para.insert_paragraph_before("")
        else:
            summary_para = doc.add_paragraph()

        # Header box with score
        box_top = summary_para.add_run("┌" + "─" * 60 + "┐\n")
        box_top.font.color.rgb = BLUE
        box_top.font.bold = True

        title_line = summary_para.add_run(
            "│" + "  ASSESSMENT FEEDBACK".center(60) + "│\n"
        )
        title_line.font.color.rgb = BLUE
        title_line.font.bold = True
        title_line.font.size = Pt(14)

        score_text = (
            f"│  {grade_symbol} SCORE: {total_score:.1f}/{total_possible} ({percentage:.1f}%) - {pass_fail}  {grade_symbol}".ljust(
                61
            )
            +"│\n"
        )
        score_run = summary_para.add_run(score_text)
        score_run.font.color.rgb = grade_color
        score_run.font.bold = True
        score_run.font.size = Pt(12)

        box_bottom = summary_para.add_run("└" + "─" * 60 + "┘\n\n")
        box_bottom.font.color.rgb = BLUE
        box_bottom.font.bold = True

        # Criteria breakdown
        if criteria_scores:
            criteria_header = summary_para.add_run("CRITERIA BREAKDOWN:\n")
            criteria_header.font.color.rgb = BLUE
            criteria_header.font.bold = True
            criteria_header.font.size = Pt(11)

            for crit_name, crit_data in criteria_scores.items():
                score = crit_data.get("score", 0)
                level = crit_data.get("level", "N/A")
                # Determine tick/cross based on level
                crit_symbol = (
                    "✓"
                    if "excellent" in level.lower() or "proficient" in level.lower()
                    else "→" if "developing" in level.lower() else "✗"
                )
                crit_color = (
                    GREEN
                    if crit_symbol == "✓"
                    else ORANGE if crit_symbol == "→" else RED
                )

                crit_line = summary_para.add_run(
                    f"  {crit_symbol} {crit_name}: {score} ({level})\n"
                )
                crit_line.font.color.rgb = crit_color
                crit_line.font.size = Pt(10)

        summary_para.add_run("\n")

        # Quick feedback summary
        feedback_header = summary_para.add_run("SUMMARY FEEDBACK:\n")
        feedback_header.font.color.rgb = BLUE
        feedback_header.font.bold = True

        # Truncate feedback to ~300 chars for summary
        short_feedback = (
            overall_feedback[:400] + "..."
            if len(overall_feedback) > 400
            else overall_feedback
        )
        feedback_text = summary_para.add_run(short_feedback + "\n\n")
        feedback_text.font.color.rgb = RGBColor(80, 80, 80)
        feedback_text.font.size = Pt(10)
        feedback_text.font.italic = True

        # Separator before original content
        separator = summary_para.add_run(
            "─" * 62
            +"\nORIGINAL SUBMISSION WITH ANNOTATIONS BELOW\n"
            +"─" * 62
            +"\n\n"
        )
        separator.font.color.rgb = BLUE
        separator.font.bold = True

        # === INLINE ANNOTATIONS ===
        # Build lookup dictionary for matching quotes
        annotation_lookup = {}
        for i, ann in enumerate(annotations):
            quote = ann.get("quote", "").strip()
            if quote and len(quote) > 15:
                # Use multiple key lengths for better matching
                key_short = quote.lower()[:30]
                key_med = quote.lower()[:50]
                annotation_lookup[key_short] = {
                    "num": i + 1,
                    "quote": quote,
                    "comment": ann.get("comment", ""),
                    "type": ann.get("type", "suggestion"),
                    "used": False,
                }
                if key_med != key_short:
                    annotation_lookup[key_med] = annotation_lookup[key_short]

        # Process each paragraph and add inline comments
        for para in doc.paragraphs:
            if para == summary_para:
                continue

            para_text_lower = para.text.lower()

            # Try to find matching annotations
            for key, ann_data in annotation_lookup.items():
                if ann_data["used"]:
                    continue

                if key in para_text_lower:
                    # Found match - add inline comment
                    ann_type = ann_data["type"]

                    # Symbols and colors based on type
                    if ann_type == "praise":
                        symbol = "✓"
                        color = GREEN
                    elif ann_type == "correction":
                        symbol = "✗"
                        color = RED
                    else:  # suggestion, question
                        symbol = "→"
                        color = ORANGE

                    # Add comment after paragraph
                    comment_text = (
                        f"\n   [{symbol} #{ann_data['num']}] {ann_data['comment']}"
                    )
                    comment_run = para.add_run(comment_text)
                    comment_run.font.color.rgb = color
                    comment_run.font.size = Pt(9)
                    comment_run.font.italic = True

                    ann_data["used"] = True
                    break

        # Save
        doc.save(str(output_path))
        print(f"[Annotated DOCX] {output_path}")
        return True

    except Exception as e:
        print(f"[DOCX Annotation Error] {e}")
        import traceback

        traceback.print_exc()
        return False


def create_rubric_feedback_document(
    output_path: Path,
    rubric: Dict[str, Any],
    assessment: Dict[str, Any],
    student_id: str,
) -> bool:
    """Create a filled-out rubric document showing scores for each criterion."""
    if not DOCX_AVAILABLE:
        return False

    try:
        doc = Document()

        # Title
        title = doc.add_heading(f"Assessment Rubric - Student {student_id}", 0)
        title.alignment = 1  # Center

        # Score summary
        total_score = assessment.get("total_score", 0)
        total_marks = rubric.get("total_marks", 25)
        percentage = (total_score / total_marks * 100) if total_marks > 0 else 0

        summary = doc.add_paragraph()
        summary_run = summary.add_run(
            f"TOTAL SCORE: {total_score}/{total_marks} ({percentage:.1f}%)"
        )
        summary_run.font.bold = True
        summary_run.font.size = Pt(14)
        if percentage >= 50:
            summary_run.font.color.rgb = RGBColor(0, 128, 0)
        else:
            summary_run.font.color.rgb = RGBColor(255, 0, 0)

        doc.add_paragraph()  # Spacer

        # Add rubric table
        criteria_scores = assessment.get("criteria_scores", {})

        for criterion in rubric.get("criteria", []):
            crit_name = criterion.get("name", "Unknown")
            crit_weight = criterion.get("weight", 0)
            levels = criterion.get("levels", {})

            # Find the score for this criterion
            score_data = None
            for key, data in criteria_scores.items():
                if crit_name.lower() in key.lower() or key.lower() in crit_name.lower():
                    score_data = data
                    break

            actual_score = score_data.get("score", 0) if score_data else 0
            actual_level = score_data.get("level", "N/A") if score_data else "N/A"
            feedback = score_data.get("feedback", "") if score_data else ""

            # Criterion header
            crit_heading = doc.add_heading(
                f"{crit_name} ({crit_weight} marks)", level=2
            )

            # Create table for levels
            table = doc.add_table(rows=len(levels) + 1, cols=4)
            table.style = "Table Grid"

            # Header row
            header_cells = table.rows[0].cells
            header_cells[0].text = "Level"
            header_cells[1].text = "Score Range"
            header_cells[2].text = "Description"
            header_cells[3].text = "Achieved"

            for cell in header_cells:
                cell.paragraphs[0].runs[0].font.bold = True

            # Level rows
            for i, (level_name, level_data) in enumerate(levels.items()):
                row = table.rows[i + 1]
                row.cells[0].text = level_name
                row.cells[1].text = (
                    f"{level_data.get('min_score', 0)}-{level_data.get('max_score', 0)}"
                )
                row.cells[2].text = level_data.get("description", "")[:100]

                # Check if this is the achieved level
                if (
                    level_name.lower() in actual_level.lower()
                    or actual_level.lower() in level_name.lower()
                ):
                    row.cells[3].text = f"✓ {actual_score}"
                    # Highlight this row
                    for cell in row.cells:
                        for para in cell.paragraphs:
                            for run in para.runs:
                                run.font.bold = True
                else:
                    row.cells[3].text = ""

            # Add feedback below table
            if feedback:
                feedback_para = doc.add_paragraph()
                feedback_label = feedback_para.add_run("Feedback: ")
                feedback_label.font.bold = True
                feedback_text = feedback_para.add_run(feedback)
                feedback_text.font.italic = True
                feedback_text.font.color.rgb = RGBColor(0, 0, 128)

            doc.add_paragraph()  # Spacer

        # Strengths and Areas for Improvement
        doc.add_heading("Summary", level=1)

        strengths = assessment.get("strengths", [])
        if strengths:
            doc.add_heading("Strengths ✓", level=2)
            for s in strengths:
                p = doc.add_paragraph(s, style="List Bullet")
                p.runs[0].font.color.rgb = RGBColor(0, 128, 0)

        improvements = assessment.get("areas_for_improvement", [])
        if improvements:
            doc.add_heading("Areas for Improvement →", level=2)
            for imp in improvements:
                p = doc.add_paragraph(imp, style="List Bullet")
                p.runs[0].font.color.rgb = RGBColor(200, 100, 0)

        # Overall feedback
        overall = assessment.get("overall_feedback", "")
        if overall:
            doc.add_heading("Overall Feedback", level=2)
            doc.add_paragraph(overall)

        # Save
        doc.save(str(output_path))
        print(f"[Rubric Document] {output_path}")
        return True

    except Exception as e:
        print(f"[Rubric Document Error] {e}")
        import traceback

        traceback.print_exc()
        return False


def create_feedback_txt(output_path: Path, assessment: Dict[str, Any]) -> bool:
    """Create a text feedback file as fallback."""
    try:
        content = []
        content.append("=" * 60)
        content.append("ASSESSMENT FEEDBACK")
        content.append("=" * 60)
        content.append("")
        content.append(f"Total Score: {assessment.get('total_score', 0)}")
        content.append("")
        content.append("OVERALL FEEDBACK:")
        content.append(assessment.get("overall_feedback", ""))
        content.append("")
        content.append("STRENGTHS:")
        for s in assessment.get("strengths", []):
            content.append(f"  + {s}")
        content.append("")
        content.append("AREAS FOR IMPROVEMENT:")
        for a in assessment.get("areas_for_improvement", []):
            content.append(f"  - {a}")
        content.append("")
        content.append("DETAILED CRITERIA SCORES:")
        for crit_name, crit_data in assessment.get("criteria_scores", {}).items():
            content.append(f"\n  {crit_name}:")
            content.append(f"    Level: {crit_data.get('level', 'N/A')}")
            content.append(f"    Score: {crit_data.get('score', 0)}")
            content.append(f"    Feedback: {crit_data.get('feedback', '')}")
        content.append("")
        content.append("ANNOTATIONS:")
        for i, ann in enumerate(assessment.get("annotations", [])):
            content.append(f"\n  [{i + 1}] ({ann.get('type', 'note').upper()})")
            content.append(f"      {ann.get('comment', '')}")
            if ann.get("quote"):
                content.append(f'      Re: "{ann["quote"][:100]}..."')

        output_path.write_text("\n".join(content), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[Feedback TXT Error] {e}")
        return False


def annotate_pdf_with_feedback(
    original_path: Path,
    output_path: Path,
    annotations: List[Dict[str, Any]],
    overall_feedback: str,
    criteria_scores: Dict[str, Any]=None,
    total_score: float=0,
    total_marks: float=25,
) -> bool:
    """Annotate a PDF document with assessment feedback using PyMuPDF."""

    if not PYMUPDF_AVAILABLE:
        print("[PDF Annotation] PyMuPDF not available, falling back to text feedback")
        return False

    try:
        doc = fitz.open(str(original_path))
        first_page = doc[0]
        page_width = first_page.rect.width

        percentage = (total_score / total_marks * 100) if total_marks > 0 else 0
        pass_fail = "PASS" if percentage >= 50 else "FAIL"
        symbol = "✓" if percentage >= 50 else "✗"
        score_color = (0, 0.5, 0) if percentage >= 50 else (0.8, 0, 0)

        # === ADD SCORE BOX AT TOP OF FIRST PAGE ===
        # Draw background rectangle
        score_box = fitz.Rect(10, 10, page_width - 10, 90)
        shape = first_page.new_shape()
        shape.draw_rect(score_box)
        shape.finish(color=(0, 0, 0.5), fill=(0.95, 0.95, 1), width=2)
        shape.commit()

        # Add main score text
        score_text = f"{symbol} SCORE: {total_score:.1f}/{total_marks} ({percentage:.1f}%) - {pass_fail} {symbol}"
        first_page.insert_text(
            fitz.Point(20, 35),
            score_text,
            fontsize=16,
            color=score_color,
            fontname="helv",
        )

        # Add criteria summary below score
        y_pos = 55
        if criteria_scores:
            for crit_name, crit_data in list(criteria_scores.items())[:3
            ]:  # First 3 criteria
                score = crit_data.get("score", 0)
                level = crit_data.get("level", "N/A")
                crit_symbol = (
                    "✓"
                    if "excellent" in level.lower() or "proficient" in level.lower()
                    else "✗"
                )
                crit_color = (0, 0.5, 0) if crit_symbol == "✓" else (0.8, 0.4, 0)

                first_page.insert_text(
                    fitz.Point(20, y_pos),
                    f"{crit_symbol} {crit_name[:30]}: {score}",
                    fontsize=9,
                    color=crit_color,
                    fontname="helv",
                )
                y_pos += 12

        # === ADD STICKY NOTE WITH FULL FEEDBACK ===
        full_feedback = f"""ASSESSMENT FEEDBACK
─────────────────────────
Score: {total_score}/{total_marks} ({percentage:.1f}%)

SUMMARY:
{overall_feedback[:600]}

CRITERIA:
"""
        for crit_name, crit_data in (criteria_scores or {}).items():
            full_feedback += f"\n• {crit_name}: {crit_data.get('score', 0)} ({crit_data.get('level', 'N/A')})"

        # Add main feedback sticky note
        first_page.add_text_annot(
            fitz.Point(page_width - 30, 10), full_feedback, icon="Comment"
        )

        # === ADD ANNOTATIONS THROUGHOUT DOCUMENT ===
        for i, ann in enumerate(annotations):
            quote = ann.get("quote", "")
            comment = ann.get("comment", "")
            ann_type = ann.get("type", "suggestion")

            # Determine icon based on type
            if ann_type == "praise":
                icon = "Check"
            elif ann_type == "correction":
                icon = "Cross"
            else:
                icon = "Note"

            # Search for quote in all pages
            found = False
            for page_num, page in enumerate(doc):
                # Search for the text
                search_text = quote[:60] if len(quote) > 60 else quote
                text_instances = page.search_for(search_text)

                if text_instances:
                    inst = text_instances[0]

                    # Add highlight annotation
                    highlight = page.add_highlight_annot(inst)
                    if ann_type == "praise":
                        highlight.set_colors(stroke=(0.7, 1, 0.7))  # Light green
                    elif ann_type == "correction":
                        highlight.set_colors(stroke=(1, 0.7, 0.7))  # Light red
                    else:
                        highlight.set_colors(stroke=(1, 1, 0.5))  # Yellow
                    highlight.update()

                    # Add comment annotation near the highlighted text
                    ann_text = f"[{i + 1}] {ann_type.upper()}\n{comment}"
                    page.add_text_annot(
                        fitz.Point(inst.x1 + 5, inst.y0), ann_text, icon=icon
                    )
                    found = True
                    break

            if not found and i < 5:  # Add first 5 unfound annotations to first page
                first_page.add_text_annot(
                    fitz.Point(page_width - 30, 100 + i * 20),
                    f"[{i + 1}] {ann_type.upper()}: {comment}",
                    icon=icon,
                )

        # Save
        doc.save(str(output_path))
        doc.close()
        print(f"[PDF Annotated] {output_path}")
        return True

    except Exception as e:
        print(f"[PDF Annotation Error] {e}")
        import traceback

        traceback.print_exc()
        return False

# ===================== EFUNDI ZIP HANDLING =====================


def extract_student_id(folder_name: str) -> Optional[str]:
    """Extract student ID from folder name like 'SURNAME, NAME(12345678)'."""
    match = re.search(r"\((\d{5,})\)", folder_name)
    return match.group(1) if match else None


def extract_group_member_ids(text: str, valid_student_ids: set) -> List[str]:
    """
    Extract group member student IDs from the first page of a submission.
    Looks for 8-digit student numbers that exist in the valid_student_ids set.
    """
    # Find all 8-digit numbers in the text (typical student ID format)
    potential_ids = re.findall(r"\b(\d{8})\b", text)

    # Filter to only include IDs that exist in the grades.csv
    group_ids = [sid for sid in potential_ids if sid in valid_student_ids]

    # Remove duplicates while preserving order
    seen = set()
    unique_ids = []
    for sid in group_ids:
        if sid not in seen:
            seen.add(sid)
            unique_ids.append(sid)

    return unique_ids


def get_first_page_text(file_path: Path) -> str:
    """Extract text from approximately the first page of a document."""
    suffix = file_path.suffix.lower()

    if suffix == ".docx":
        if not DOCX_AVAILABLE:
            return ""
        try:
            doc = Document(str(file_path))
            # Get first ~500 words (approximately first page)
            text_parts = []
            word_count = 0
            for para in doc.paragraphs:
                text_parts.append(para.text)
                word_count += len(para.text.split())
                if word_count > 500:
                    break
            return "\n".join(text_parts)
        except Exception as e:
            print(f"[First Page Extract Error] {e}")
            return ""

    elif suffix == ".pdf":
        if not PDF_AVAILABLE:
            return ""
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                if len(reader.pages) > 0:
                    return reader.pages[0].extract_text() or ""
            return ""
        except Exception as e:
            print(f"[PDF First Page Error] {e}")
            return ""

    return ""


async def process_efundi_zip(
    zip_path: Path,
    rubric: Dict[str, Any],
    output_dir: Path,
    progress_callback: callable=None,
    instructions: str=None,
) -> Dict[str, Any]:
    """Process an eFundi assignment zip file and assess all submissions."""

    results = {
        "job_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "submissions_processed": 0,
        "total_submissions": 0,
        "total_marks": rubric.get("total_marks", 25),
        "assessments": [],
        "current_student": None,
        "grades_csv_path": None,
        "output_zip_path": None,
    }

    temp_dir = Path(tempfile.mkdtemp(prefix="efundi_"))

    try:
        # Extract zip
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)

        # Find root folder (e.g., "Assignment 1 /")
        contents = list(temp_dir.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            root_dir = contents[0]
        else:
            root_dir = temp_dir

        # Find grades.csv and extract all valid student IDs
        grades_csv = None
        valid_student_ids = set()
        for f in root_dir.glob("*.csv"):
            if "grade" in f.name.lower():
                grades_csv = f
                # Extract all student IDs from the CSV
                try:
                    csv_content = grades_csv.read_text(encoding="utf-8-sig")
                    for line in csv_content.split("\n")[3:]:  # Skip header rows
                        parts = line.split(",")
                        if len(parts) >= 2:
                            sid = parts[1].strip().strip('"')
                            if sid.isdigit() and len(sid) >= 5:
                                valid_student_ids.add(sid)
                except Exception as e:
                    print(f"[CSV Parse Error] {e}")
                break

        print(f"[Found {len(valid_student_ids)} valid student IDs in grades.csv]")

        # Process each student folder
        grades_map = {}  # student_id -> score
        group_grades_map = {}  # Maps group member IDs to their grades
        feedback_files = {}  # student_folder_name -> [(source_path, dest_filename)]
        comments_map = {}  # student_id -> comment text

        # Count total student folders with submissions first
        student_folders_to_process = []
        for student_folder in root_dir.iterdir():
            if not student_folder.is_dir():
                continue
            student_id = extract_student_id(student_folder.name)
            if not student_id:
                continue
            submission_dir = student_folder / "Submission attachment(s)"
            if not submission_dir.exists():
                submission_dir = student_folder
            submission_files = (
                list(submission_dir.glob("*.docx"))
                +list(submission_dir.glob("*.pdf"))
                +list(submission_dir.glob("*.doc"))
            )
            if submission_files:
                student_folders_to_process.append(
                    (student_folder, student_id, submission_files[0])
                )

        results["total_submissions"] = len(student_folders_to_process)
        print(f"[Found {len(student_folders_to_process)} submissions to process]")

        # Call progress callback with initial state
        if progress_callback:
            await progress_callback(results)

        for idx, (student_folder, student_id, submission_file) in enumerate(
            student_folders_to_process
        ):
            # Update current student being processed
            results["current_student"] = {
                "id": student_id,
                "file": submission_file.name,
                "index": idx + 1,
            }

            if progress_callback:
                await progress_callback(results)

            # Extract text from submission
            submission_text = extract_document_content(submission_file)

            if not submission_text.strip():
                print(f"[Skipping] Empty submission for {student_id}")
                continue

            # Run AI assessment
            print(f"[Processing] Student {student_id}: {submission_file.name}")
            assessment = await assess_with_ai(submission_text, rubric, instructions)

            assessment["student_id"] = student_id
            assessment["student_folder"] = student_folder.name
            assessment["submission_file"] = submission_file.name

            # Calculate percentage and final grade
            total_possible = rubric.get("total_marks", 100)
            total_score = assessment.get("total_score", 0)

            # Normalize score if criteria weights sum to more than total_marks
            criteria_weight_sum = sum(
                c.get("weight", 0) for c in rubric.get("criteria", [])
            )
            if criteria_weight_sum > 0 and criteria_weight_sum != total_possible:
                # Scale raw score to fit within total_marks
                normalized_score = (total_score / criteria_weight_sum) * total_possible
                print(
                    f"[Score Normalize] {student_id}: raw {total_score}/{criteria_weight_sum} -> {normalized_score:.1f}/{total_possible}"
                )
                total_score = round(normalized_score, 2)
                assessment["total_score"] = total_score

            # Cap at total_possible to prevent >100%
            if total_score > total_possible:
                print(
                    f"[Score Cap] {student_id}: {total_score} capped to {total_possible}"
                )
                total_score = total_possible
                assessment["total_score"] = total_score

            percentage = (
                (total_score / total_possible * 100) if total_possible > 0 else 0
            )
            assessment["percentage"] = round(min(percentage, 100), 2)
            assessment["max_score"] = total_possible

            # Enrich criteria_scores with max_score from rubric
            rubric_criteria_map = {
                c["name"]: c["weight"] for c in rubric.get("criteria", [])
            }
            if assessment.get("criteria_scores"):
                for crit_name, crit_data in assessment["criteria_scores"].items():
                    if isinstance(crit_data, dict) and "max_score" not in crit_data:
                        crit_data["max_score"] = rubric_criteria_map.get(
                            crit_name,
                            total_possible / max(len(assessment["criteria_scores"]), 1),
                        )

            # Store grade for CSV update - primary student
            grades_map[student_id] = total_score

            # Check for group members in the first page of the submission
            first_page_text = get_first_page_text(submission_file)
            group_member_ids = extract_group_member_ids(
                first_page_text, valid_student_ids
            )

            # If group members found, apply the same grade to all of them
            if group_member_ids:
                # Filter out the primary student and any IDs already graded
                other_members = [
                    gid
                    for gid in group_member_ids
                    if gid != student_id and gid not in grades_map
                ]
                if other_members:
                    print(
                        f"[Group Detected] Primary: {student_id}, Members: {other_members}"
                    )
                    assessment["group_members"] = other_members
                    for member_id in other_members:
                        grades_map[member_id] = total_score
                        group_grades_map[member_id] = {
                            "score": total_score,
                            "from_student": student_id,
                            "submission_file": submission_file.name,
                        }
                        print(
                            f"[Group Grade] {member_id} gets {total_score} (same as {student_id})"
                        )

            # Create feedback folder for this student
            feedback_folder = student_folder / "Feedback Attachment(s)"
            feedback_folder.mkdir(parents=True, exist_ok=True)

            # Create annotated copy of the ORIGINAL submission in the Feedback folder
            feedback_files[student_folder.name] = []

            if submission_file.suffix.lower() == ".docx":
                # Annotate the original DOCX and save to feedback folder
                annotated_filename = submission_file.name  # Keep same name as original
                annotated_path = feedback_folder / annotated_filename

                success = annotate_docx_with_feedback(
                    submission_file,  # Source: original submission
                    annotated_path,  # Dest: feedback folder with same name
                    assessment.get("annotations", []),
                    assessment.get("overall_feedback", ""),
                    assessment.get("criteria_scores", {}),
                    total_score,
                    total_possible,
                )

                if success:
                    feedback_files[student_folder.name].append(annotated_path)
                    print(f"[Annotated] {annotated_path}")

                # Also create filled rubric document
                rubric_filename = f"{submission_file.stem}_RUBRIC.docx"
                rubric_path = feedback_folder / rubric_filename
                create_rubric_feedback_document(
                    rubric_path, rubric, assessment, student_id
                )
                feedback_files[student_folder.name].append(rubric_path)

            elif submission_file.suffix.lower() == ".pdf":
                # Try to annotate PDF with PyMuPDF
                annotated_filename = submission_file.name  # Keep same name as original
                annotated_path = feedback_folder / annotated_filename

                success = annotate_pdf_with_feedback(
                    submission_file,
                    annotated_path,
                    assessment.get("annotations", []),
                    assessment.get("overall_feedback", ""),
                    assessment.get("criteria_scores", {}),
                    total_score,
                    total_possible,
                )

                if success:
                    feedback_files[student_folder.name].append(annotated_path)
                    print(f"[PDF Annotated] {annotated_path}")
                else:
                    # Fallback to text file if PDF annotation fails
                    feedback_txt_path = (
                        feedback_folder / f"{submission_file.stem}_FEEDBACK.txt"
                    )
                    create_feedback_txt(feedback_txt_path, assessment)
                    feedback_files[student_folder.name].append(feedback_txt_path)

                # Also create filled rubric document for PDF submissions
                rubric_filename = f"{submission_file.stem}_RUBRIC.docx"
                rubric_path = feedback_folder / rubric_filename
                create_rubric_feedback_document(
                    rubric_path, rubric, assessment, student_id
                )
                feedback_files[student_folder.name].append(rubric_path)

            # Create/update comments.txt with the overall feedback
            comments_txt = f"""Score: {total_score}/{total_possible} ({percentage:.1f}%)

{assessment.get("overall_feedback", "")}

STRENGTHS:
{chr(10).join("• " + s for s in assessment.get("strengths", []))}

AREAS FOR IMPROVEMENT:
{chr(10).join("• " + a for a in assessment.get("areas_for_improvement", []))}

CRITERIA BREAKDOWN:
"""
            for crit_name, crit_data in assessment.get("criteria_scores", {}).items():
                comments_txt += f"\n{crit_name}: {crit_data.get('score', 0)} ({crit_data.get('level', 'N/A')})\n"
                comments_txt += f"  {crit_data.get('feedback', '')}\n"

            comments_map[student_id] = comments_txt

            # Write comments.txt directly to the student folder
            comments_path = student_folder / "comments.txt"
            comments_path.write_text(comments_txt, encoding="utf-8")

            results["assessments"].append(assessment)
            results["submissions_processed"] += 1
            results["current_student"] = None  # Clear current student after processing

            # Report progress after each assessment
            if progress_callback:
                await progress_callback(results)

        # Add comments for group members in their respective folders
        for member_id, grade_info in group_grades_map.items():
            # Find the member's folder
            for student_folder in root_dir.iterdir():
                if not student_folder.is_dir():
                    continue
                folder_student_id = extract_student_id(student_folder.name)
                if folder_student_id == member_id:
                    group_comment = f"""Score: {grade_info["score"]}/{total_possible} (Group Submission)

This grade was assigned based on the group submission: {grade_info["submission_file"]}
Primary submitter student ID: {grade_info["from_student"]}

Please refer to the feedback in the primary submitter's folder for detailed assessment.
"""
                    comments_path = student_folder / "comments.txt"
                    comments_path.write_text(group_comment, encoding="utf-8")
                    comments_map[member_id] = group_comment
                    print(f"[Group Comment] Added comment to {member_id}'s folder")
                    break

        # Update grades.csv in place
        if grades_csv and grades_csv.exists():
            print(f"[Updating grades.csv] {len(grades_map)} grades to update")
            updated_csv_content = update_grades_csv_content(grades_csv, grades_map)
            grades_csv.write_bytes(updated_csv_content)
            results["grades_csv_path"] = str(grades_csv)

        # Create output zip - repackage the entire extracted folder
        output_zip = output_dir / f"efundi_upload_{results['job_id']}.zip"
        print(f"[Creating ZIP] {output_zip}")

        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for file_path in root_dir.rglob("*"):
                if file_path.is_file():
                    arcname = str(file_path.relative_to(temp_dir))
                    zout.write(file_path, arcname)
                elif file_path.is_dir():
                    # Add empty directories
                    arcname = str(file_path.relative_to(temp_dir)) + "/"
                    zout.writestr(arcname, "")

        results["output_zip_path"] = str(output_zip)
        print(f"[Complete] Processed {results['submissions_processed']} submissions")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return results


def update_grades_csv_content(csv_path: Path, grades_map: Dict[str, Any]) -> bytes:
    """Update grades.csv with assessment scores."""
    csv_bytes = csv_path.read_bytes()
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()

    if len(lines) < 3:
        return csv_bytes

    # eFundi CSV format:
    # Line 1: "Assignment Name","SCORE_GRADE_TYPE"
    # Line 2: (empty)
    # Line 3: Header row with columns
    # Line 4+: Data rows

    prefix = lines[:2]
    header = lines[2]
    data_lines = lines[3:]

    # Parse header to find column indices
    reader = csv.DictReader([header] + data_lines)
    fieldnames = reader.fieldnames

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()

    updated_count = 0
    for row in reader:
        # Try both "ID" and "Display ID" columns
        sid = (row.get("ID") or row.get("Display ID") or "").strip()
        if sid in grades_map:
            row["grade"] = str(grades_map[sid])
            updated_count += 1
            print(f"[Grade] {sid}: {grades_map[sid]}")
        writer.writerow(row)

    print(f"[Grades CSV] Updated {updated_count} grades")

    updated = "\r\n".join(prefix) + "\r\n" + out.getvalue().rstrip("\r\n") + "\r\n"
    return updated.encode("utf-8-sig")


def repackage_efundi_zip(
    download_zip: Path,
    output_zip: Path,
    grades_map: Dict[str, Any],
    feedback_files: Dict[str, List[Path]],
    comments_map: Dict[str, str],
) -> Path:
    """Repackage eFundi zip with grades and feedback."""

    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(download_zip, "r") as zin, zipfile.ZipFile(
        output_zip, "w", compression=zipfile.ZIP_DEFLATED
    ) as zout:
        names = zin.namelist()
        root = names[0].split("/")[0] if names else ""

        for name in names:
            data = zin.read(name)

            # Update grades.csv
            if name.endswith("/grades.csv") or name == "grades.csv":
                csv_bytes = data
                text = csv_bytes.decode("utf-8-sig", errors="replace")
                lines = text.splitlines()

                if len(lines) >= 3:
                    prefix = lines[:2]
                    header = lines[2]
                    data_lines = lines[3:]

                    reader = csv.DictReader([header] + data_lines)
                    out_io = io.StringIO()
                    writer = csv.DictWriter(
                        out_io, fieldnames=reader.fieldnames, lineterminator="\r\n"
                    )
                    writer.writeheader()

                    for row in reader:
                        sid = (row.get("ID") or row.get("Display ID") or "").strip()
                        if sid in grades_map:
                            row["grade"] = str(grades_map[sid])
                        writer.writerow(row)

                    updated = (
                        "\r\n".join(prefix)
                        +"\r\n"
                        +out_io.getvalue().rstrip("\r\n")
                        +"\r\n"
                    )
                    data = updated.encode("utf-8-sig")

                zout.writestr(name, data)
                continue

            # Skip comments.txt if we have new ones
            if name.endswith("/comments.txt"):
                folder = name.rsplit("/", 1)[0]
                student_folder = folder.split("/")[-1]
                sid = extract_student_id(student_folder)
                if sid and sid in comments_map:
                    continue

            zout.writestr(name, data)

        # Add feedback files
        for student_folder, files in feedback_files.items():
            sid = extract_student_id(student_folder)
            if not sid:
                continue

            base = f"{root}/{student_folder}"
            fb_dir = f"{base}/Feedback Attachment(s)"
            zout.writestr(fb_dir + "/", b"")

            for f in files:
                if f.exists():
                    zout.write(f, arcname=f"{fb_dir}/{f.name}")

        # Add comments.txt
        for sid, comment in comments_map.items():
            student_folder = None
            for name in names:
                if name.startswith(root + "/"):
                    parts = name[len(root) + 1:].split("/")
                    if parts and parts[0]:
                        if extract_student_id(parts[0]) == sid:
                            student_folder = parts[0]
                            break

            if student_folder:
                path = f"{root}/{student_folder}/comments.txt"
                zout.writestr(path, comment)

    return output_zip

# ===================== API ENDPOINTS =====================


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/rubric/upload")
async def upload_rubric(file: UploadFile=File(...)):
    file_path = None
    try:
        # 1. Establish absolute safe path markers
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        file_path = temp_dir / file.filename

        # 2. Write the incoming payload asset safely to block memory
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        # 3. Extract content using our sync/async routine
        rubric_data = await parse_essay_matrix_from_docx(file_path)

        # 4. Clean up the temp asset immediately
        if file_path and file_path.exists():
            file_path.unlink()

        # 5. Clean and sanitize the object tree before returning
        clean_rubric = sanitize_for_json(rubric_data)

        # Ensure a valid fallback structure exists if parsing came up short
        if not clean_rubric or not isinstance(clean_rubric, dict):
            clean_rubric = {"name": file.filename, "total_marks": 0, "criteria": []}
        elif "criteria" not in clean_rubric:
            clean_rubric["criteria"] = []
            clean_rubric["name"] = clean_rubric.get("name", file.filename)
            clean_rubric["total_marks"] = clean_rubric.get("total_marks", 0)

        # 6. Build universal layout structure mapping for the React context receiver
        response_payload = {
            "success": True,
            "message": "Rubric processed successfully.",
            "rubric": clean_rubric,
            "data": clean_rubric,
            **clean_rubric,
        }

        return JSONResponse(status_code=200, content=response_payload)

    except Exception as e:
        print(f"[Backend Upload Endpoint Crash] {e}")
        # Safeguard fallback unlink step inside exception loop block
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": f"Server extraction engine fault: {str(e)}",
            },
        )


@app.post("/api/rubric/create")
async def create_rubric(rubric_data: dict):
    """Create a rubric manually with specified criteria."""
    rubric_data["created_at"] = datetime.now(timezone.utc).isoformat()

    # Calculate total marks
    total = sum(c.get("weight", 0) for c in rubric_data.get("criteria", []))
    rubric_data["total_marks"] = total

    result = rubrics_collection.insert_one(rubric_data)
    rubric_data["_id"] = str(result.inserted_id)

    return {"success": True, "rubric": rubric_data}


@app.post("/api/rubric/essay-default")
async def create_default_essay_rubric(
    name: str=Form("Essay Assessment Rubric"), total_marks: float=Form(50)
):
    """Create a default essay assessment rubric with standard criteria."""

    # Standard essay rubric criteria
    criteria = [
        {
            "name": "Thesis Statement & Argument",
            "weight": total_marks * 0.2,  # 20%
            "levels": {
                "Excellent (80-100%)": {
                    "description": "Clear, focused, arguable thesis directly addressing the prompt. Consistently supports thesis with insightful analysis. Logical, well-structured, persuasive argument.",
                    "min_score": total_marks * 0.2 * 0.8,
                    "max_score": total_marks * 0.2,
                },
                "Good (60-79%)": {
                    "description": "Clear thesis addressing the prompt. Generally supports thesis with relevant evidence and analysis. Mostly logical argument.",
                    "min_score": total_marks * 0.2 * 0.6,
                    "max_score": total_marks * 0.2 * 0.79,
                },
                "Satisfactory (40-59%)": {
                    "description": "Thesis present but may be vague or underdeveloped. Support limited or superficial. Argument may lack clarity.",
                    "min_score": total_marks * 0.2 * 0.4,
                    "max_score": total_marks * 0.2 * 0.59,
                },
                "Needs Improvement (0-39%)": {
                    "description": "Thesis absent, unclear, or doesn't address prompt. Lacks central argument or supporting evidence. Disorganized.",
                    "min_score": 0,
                    "max_score": total_marks * 0.2 * 0.39,
                },
            },
        },
        {
            "name": "Evidence & Historical Accuracy",
            "weight": total_marks * 0.3,  # 30%
            "levels": {
                "Excellent (80-100%)": {
                    "description": "Extensive use of accurate, relevant evidence. Evidence integrated seamlessly. Deep understanding demonstrated.",
                    "min_score": total_marks * 0.3 * 0.8,
                    "max_score": total_marks * 0.3,
                },
                "Good (60-79%)": {
                    "description": "Good range of accurate evidence. Generally well-integrated. Solid understanding of the period.",
                    "min_score": total_marks * 0.3 * 0.6,
                    "max_score": total_marks * 0.3 * 0.79,
                },
                "Satisfactory (40-59%)": {
                    "description": "Some evidence but limited in scope or accuracy. May be listed rather than integrated. Basic understanding.",
                    "min_score": total_marks * 0.3 * 0.4,
                    "max_score": total_marks * 0.3 * 0.59,
                },
                "Needs Improvement (0-39%)": {
                    "description": "Little to no relevant evidence. Claims unsubstantiated. Fundamental lack of understanding.",
                    "min_score": 0,
                    "max_score": total_marks * 0.3 * 0.39,
                },
            },
        },
        {
            "name": "Analysis & Interpretation",
            "weight": total_marks * 0.3,  # 30%
            "levels": {
                "Excellent (80-100%)": {
                    "description": "Critical thinking and insightful interpretation. Explains how and why events occurred. Identifies nuances and complexities.",
                    "min_score": total_marks * 0.3 * 0.8,
                    "max_score": total_marks * 0.3,
                },
                "Good (60-79%)": {
                    "description": "Good analytical skills. Explains key events and significance. Connects cause and effect reasonably well.",
                    "min_score": total_marks * 0.3 * 0.6,
                    "max_score": total_marks * 0.3 * 0.79,
                },
                "Satisfactory (40-59%)": {
                    "description": "Basic explanation but analysis often descriptive. Cause-effect may be simplistic or unclear.",
                    "min_score": total_marks * 0.3 * 0.4,
                    "max_score": total_marks * 0.3 * 0.59,
                },
                "Needs Improvement (0-39%)": {
                    "description": "Lacks analytical depth. Primarily descriptive. Fails to engage with complexities.",
                    "min_score": 0,
                    "max_score": total_marks * 0.3 * 0.39,
                },
            },
        },
        {
            "name": "Structure & Organization",
            "weight": total_marks * 0.1,  # 10%
            "levels": {
                "Excellent (80-100%)": {
                    "description": "Logically structured with clear intro, body, conclusion. Smooth transitions. Each paragraph focused and contributing.",
                    "min_score": total_marks * 0.1 * 0.8,
                    "max_score": total_marks * 0.1,
                },
                "Good (60-79%)": {
                    "description": "Recognizable structure. Paragraphs generally organized. Transitions mostly clear.",
                    "min_score": total_marks * 0.1 * 0.6,
                    "max_score": total_marks * 0.1 * 0.79,
                },
                "Satisfactory (40-59%)": {
                    "description": "Structure present but inconsistent. Paragraphs may lack focus. Transitions abrupt or missing.",
                    "min_score": total_marks * 0.1 * 0.4,
                    "max_score": total_marks * 0.1 * 0.59,
                },
                "Needs Improvement (0-39%)": {
                    "description": "Disorganized. Lacks clear structure. Difficult to follow.",
                    "min_score": 0,
                    "max_score": total_marks * 0.1 * 0.39,
                },
            },
        },
        {
            "name": "Language, Style & Referencing",
            "weight": total_marks * 0.1,  # 10%
            "levels": {
                "Excellent (80-100%)": {
                    "description": "Clear, concise, sophisticated writing. Precise vocabulary. Minimal errors. Accurate referencing if required.",
                    "min_score": total_marks * 0.1 * 0.8,
                    "max_score": total_marks * 0.1,
                },
                "Good (60-79%)": {
                    "description": "Generally clear and appropriate. Minor errors that don't impede understanding. Mostly accurate referencing.",
                    "min_score": total_marks * 0.1 * 0.6,
                    "max_score": total_marks * 0.1 * 0.79,
                },
                "Satisfactory (40-59%)": {
                    "description": "May be unclear or contain frequent errors. Inconsistent referencing.",
                    "min_score": total_marks * 0.1 * 0.4,
                    "max_score": total_marks * 0.1 * 0.59,
                },
                "Needs Improvement (0-39%)": {
                    "description": "Unclear or confusing. Pervasive errors. Absent or fundamentally flawed referencing.",
                    "min_score": 0,
                    "max_score": total_marks * 0.1 * 0.39,
                },
            },
        },
    ]

    rubric_data = {
        "name": name,
        "total_marks": total_marks,
        "criteria": criteria,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    result = rubrics_collection.insert_one(rubric_data)
    rubric_data["_id"] = str(result.inserted_id)

    return {"success": True, "rubric": rubric_data}


@app.get("/api/rubrics")
async def list_rubrics():
    """List all uploaded rubrics."""
    rubrics = list(
        rubrics_collection.find(
            {}, {"_id": 1, "name": 1, "total_marks": 1, "criteria": 1, "created_at": 1}
        )
    )
    for r in rubrics:
        r["_id"] = str(r["_id"])
    return {"rubrics": rubrics}


@app.get("/api/rubric/{rubric_id}")
async def get_rubric(rubric_id: str):
    """Get a specific rubric by ID."""
    try:
        rubric = rubrics_collection.find_one({"_id": ObjectId(rubric_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid rubric ID format")
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")
    rubric["_id"] = str(rubric["_id"])
    return rubric


@app.delete("/api/rubric/{rubric_id}")
async def delete_rubric(rubric_id: str):
    """Delete a rubric by ID."""
    try:
        result = rubrics_collection.delete_one({"_id": ObjectId(rubric_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid rubric ID format")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return {"success": True, "message": "Rubric deleted"}


@app.post("/api/assess/single")
async def assess_single_submission(
    file: UploadFile=File(...),
    rubric_id: str=Form(...),
    student_id: str=Form(None),
):
    """Assess a single submission file."""

    # Get rubric
    rubric = rubrics_collection.find_one({"_id": ObjectId(rubric_id)})
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    # Save submission
    submission_path = UPLOAD_DIR / file.filename
    with open(submission_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Extract text
    submission_text = extract_document_content(submission_path)
    if not submission_text.strip():
        raise HTTPException(
            status_code=400, detail="Could not extract text from submission"
        )

    # Run AI assessment
    assessment = await assess_with_ai(submission_text, rubric)
    assessment["student_id"] = student_id or submission_path.stem
    assessment["submission_file"] = file.filename
    assessment["rubric_id"] = str(rubric["_id"])
    assessment["rubric_name"] = rubric["name"]
    assessment["timestamp"] = datetime.now(timezone.utc).isoformat()

    # Calculate percentage
    total_possible = rubric.get("total_marks", 100)
    total_score = assessment.get("total_score", 0)
    assessment["percentage"] = round(
        (total_score / total_possible * 100) if total_possible > 0 else 0, 2
    )
    assessment["max_score"] = total_possible

    # Create annotated document
    if submission_path.suffix.lower() == ".docx":
        output_path = OUTPUT_DIR / f"{submission_path.stem}_GRADED.docx"
        annotate_docx_with_feedback(
            submission_path,
            output_path,
            assessment.get("annotations", []),
            assessment.get("overall_feedback", ""),
        )
        assessment["annotated_file"] = str(output_path)

    # Store assessment
    result = assessments_collection.insert_one(assessment)
    assessment["_id"] = str(result.inserted_id)

    return assessment


@app.post("/api/assess/bulk")
async def assess_bulk_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile=File(...),
    rubric_id: str=Form(...),
    instructions: Optional[str]=Form(None),
    instructions_file: Optional[UploadFile]=File(None),
):
    """Process an eFundi zip file with multiple submissions."""

    # Get rubric
    rubric = rubrics_collection.find_one({"_id": ObjectId(rubric_id)})
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    # Process instructions
    assignment_instructions = instructions or ""
    if instructions_file and instructions_file.filename:
        instructions_content = await instructions_file.read()
        if instructions_file.filename.endswith(".txt"):
            assignment_instructions = instructions_content.decode(
                "utf-8", errors="ignore"
            )
        elif instructions_file.filename.endswith(".docx"):
            # Extract text from DOCX
            temp_instructions = (
                UPLOAD_DIR
                / f"instructions_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
            )
            temp_instructions.write_bytes(instructions_content)
            assignment_instructions = extract_document_content(temp_instructions)
            temp_instructions.unlink(missing_ok=True)
        elif instructions_file.filename.endswith(".pdf"):
            temp_instructions = (
                UPLOAD_DIR
                / f"instructions_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            )
            temp_instructions.write_bytes(instructions_content)
            assignment_instructions = extract_document_content(temp_instructions)
            temp_instructions.unlink(missing_ok=True)

    # Save zip
    zip_path = UPLOAD_DIR / file.filename
    with open(zip_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Create job
    job_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    job = {
        "job_id": job_id,
        "status": "processing",
        "rubric_id": str(rubric["_id"]),
        "rubric_name": rubric["name"],
        "zip_file": file.filename,
        "instructions": (
            assignment_instructions[:2000] if assignment_instructions else None
        ),  # Store truncated
        "created_at": datetime.now(timezone.utc).isoformat(),
        "progress": 0,
        "total": 0,
        "results": None,
    }
    jobs_collection.insert_one(job)

    # Process in background
    async def process_job():
        try:
            output_dir = OUTPUT_DIR / job_id
            output_dir.mkdir(parents=True, exist_ok=True)

            # Progress callback to update job in real-time
            async def update_progress(results):
                jobs_collection.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "progress": results.get("submissions_processed", 0),
                            "total": results.get("total_submissions", 0),
                            "current_student": results.get("current_student"),
                            "results": results,
                        }
                    },
                )

            results = await process_efundi_zip(
                zip_path, rubric, output_dir, update_progress, assignment_instructions
            )

            jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "completed",
                        "results": results,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
        except Exception as e:
            jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(e),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )

    background_tasks.add_task(process_job)

    return {
        "success": True,
        "job_id": job_id,
        "message": "Processing started. Check /api/job/{job_id} for status.",
    }


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a bulk assessment job."""
    job = jobs_collection.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/job/{job_id}/logs")
async def get_job_logs(job_id: str):
    """Get the logs for a job."""
    job = jobs_collection.find_one({"job_id": job_id}, {"logs": 1, "_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"logs": job.get("logs", [])}


@app.get("/api/jobs")
async def list_jobs():
    """List all assessment jobs explicitly returning empty list instead of crashing if DB is empty."""
    try:
        jobs = list(jobs_collection.find().sort("created_at", -1).limit(50))
        for job in jobs:
            job["_id"] = str(job["_id"])
            if not job.get("job_id"):
                job["job_id"] = job["_id"]
        return {"jobs": jobs}
    except Exception as e:
        print(f"[Backend Error] /api/jobs failed: {e}")
        return {"jobs": [], "error": str(e)}


@app.get("/api/download/{job_id}")
async def download_results(job_id: str):
    """Download the processed eFundi zip for a job."""
    print(f"[Download] Looking for job_id: {job_id}")

    # Try to find by job_id field first, then by _id
    job = jobs_collection.find_one({"job_id": job_id})
    print(f"[Download] Find by job_id: {job is not None}")

    if not job:
        try:
            job = jobs_collection.find_one({"_id": ObjectId(job_id)})
            print(f"[Download] Find by _id: {job is not None}")
        except Exception as e:
            print(f"[Download] ObjectId error: {e}")

    if not job:
        # Debug: list all jobs
        all_jobs = list(jobs_collection.find())
        print(f"[Download] Total jobs in DB: {len(all_jobs)}")
        for j in all_jobs:
            print(f"[Download]   job_id={j.get('job_id')}, _id={j.get('_id')}")
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")

    # Check both locations for output_zip_path
    results = job.get("results", {})
    zip_path = results.get("output_zip_path") or job.get("output_zip_path")
    print(f"[Download] zip_path: {zip_path}")

    if not zip_path or not Path(zip_path).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(
        zip_path, media_type="application/zip", filename=Path(zip_path).name
    )


@app.get("/api/assessments")
async def list_assessments():
    """List recent assessments."""
    assessments = list(
        assessments_collection.find(
            {},
            {
                "_id": 1,
                "student_id": 1,
                "total_score": 1,
                "percentage": 1,
                "rubric_name": 1,
                "timestamp": 1,
            },
        )
        .sort("timestamp", -1)
        .limit(100)
    )
    for a in assessments:
        a["_id"] = str(a["_id"])
    return {"assessments": assessments}


@app.get("/api/assessment/{assessment_id}")
async def get_assessment(assessment_id: str):
    """Get a specific assessment."""
    try:
        assessment = assessments_collection.find_one({"_id": ObjectId(assessment_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid assessment ID format")
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    assessment["_id"] = str(assessment["_id"])
    return assessment


@app.get("/api/assessment/{assessment_id}/download")
async def download_annotated_document(assessment_id: str):
    """Download the annotated document for an assessment."""
    try:
        assessment = assessments_collection.find_one({"_id": ObjectId(assessment_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid assessment ID format")

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    annotated_file = assessment.get("annotated_file")
    if not annotated_file or not Path(annotated_file).exists():
        raise HTTPException(status_code=404, detail="Annotated document not found")

    return FileResponse(
        annotated_file,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(annotated_file).name,
    )


# Webhook endpoint for eFundi
@app.post("/api/webhook/efundi")
async def efundi_webhook(
    background_tasks: BackgroundTasks,
    file: UploadFile=File(None),
    rubric_id: str=Form(None),
    callback_url: str=Form(None),
):
    """Webhook to receive eFundi zip files for processing."""

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Use default rubric if not specified
    if not rubric_id:
        rubric = rubrics_collection.find_one({}, sort=[("created_at", -1)])
        if rubric:
            rubric_id = str(rubric["_id"])
        else:
            raise HTTPException(status_code=400, detail="No rubric available")

    # Same as bulk assess
    return await assess_bulk_zip(background_tasks, file, rubric_id)

# ===================== EFUNDI AUTOMATION =====================


# Store eFundi sessions
efundi_sessions = db["efundi_sessions"]


class EfundiCredentials(BaseModel):
    username: str
    password: str


class EfundiDownloadRequest(BaseModel):
    assignment_url: str
    rubric_id: str
    assignment_name: str = None  # Optional: to find specific assignment by name


@app.post("/api/efundi/authenticate")
async def efundi_authenticate(credentials: EfundiCredentials):
    """Authenticate with eFundi and save session."""
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(
            status_code=500, detail="Playwright not available for browser automation"
        )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Go to eFundi login
            await page.goto(
                "https://efundi.nwu.ac.za/portal", wait_until="domcontentloaded"
            )
            await page.wait_for_timeout(2000)

            # Click login if needed
            login_link = page.locator("a:has-text('Login')")
            if await login_link.count() > 0:
                await login_link.first.click()
                await page.wait_for_timeout(2000)

            # Fill credentials - eFundi uses CAS/institutional login
            # Try to find username field
            username_field = page.locator(
                "input[name='username'], input[id='username'], input[type='text']"
            ).first
            password_field = page.locator(
                "input[name='password'], input[id='password'], input[type='password']"
            ).first

            await username_field.fill(credentials.username)
            await password_field.fill(credentials.password)

            # Submit
            submit_btn = page.locator(
                "button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign')"
            ).first
            await submit_btn.click()
            await page.wait_for_timeout(5000)

            # Check if login was successful by looking for user menu or dashboard elements
            if "portal" in page.url and "login" not in page.url.lower():
                # Save session state
                storage_state = await context.storage_state()

                # Store in database (encrypted in production)
                efundi_sessions.update_one(
                    {"username": credentials.username},
                    {
                        "$set": {
                            "username": credentials.username,
                            "storage_state": storage_state,
                            "authenticated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                    upsert=True,
                )

                await browser.close()
                return {
                    "success": True,
                    "message": "Successfully authenticated with eFundi",
                }
            else:
                await browser.close()
                raise HTTPException(
                    status_code=401,
                    detail="Authentication failed. Please check your credentials.",
                )

    except Exception as e:
        print(f"[eFundi Auth Error] {e}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")


@app.get("/api/efundi/status")
async def efundi_status():
    """Check if we have a valid eFundi session."""
    session = efundi_sessions.find_one({}, sort=[("authenticated_at", -1)])
    if session:
        return {
            "authenticated": True,
            "username": session.get("username"),
            "authenticated_at": session.get("authenticated_at"),
        }
    return {"authenticated": False}


@app.post("/api/efundi/debug-page")
async def efundi_debug_page(url: str=Form(...)):
    """Navigate to a URL and capture the page HTML and screenshot for debugging."""
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(status_code=500, detail="Playwright not available")

    session = efundi_sessions.find_one({}, sort=[("authenticated_at", -1)])
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=session["storage_state"])
            page = await context.new_page()
            page.set_default_timeout(30000)

            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # Get page info
            title = await page.title()
            current_url = page.url

            # Get all links on the page
            links = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a')).map(a => ({
                    text: a.innerText.trim().substring(0, 100),
                    href: a.href,
                    className: a.className
                })).filter(l => l.text.length > 0)
            }""")

            # Get all buttons
            buttons = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]')).map(b => ({
                    text: (b.innerText || b.value || '').trim().substring(0, 100),
                    type: b.type,
                    className: b.className
                })).filter(b => b.text.length > 0)
            }""")

            # Save screenshot
            debug_dir = OUTPUT_DIR / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = (
                debug_dir / f"debug_{datetime.now().strftime('%H%M%S')}.png"
            )
            await page.screenshot(path=str(screenshot_path), full_page=True)

            await browser.close()

            # Filter for relevant links
            relevant_links = [
                l
                for l in links
                if any(
                    kw in l["text"].lower()
                    for kw in ["download", "grade", "assignment", "submission", "all"]
                )
            ]

            return {
                "title": title,
                "url": current_url,
                "screenshot": str(screenshot_path),
                "relevant_links": relevant_links[:20],
                "all_links_count": len(links),
                "buttons": buttons[:10],
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/efundi/download-and-assess")
async def efundi_download_and_assess(
    background_tasks: BackgroundTasks, request: EfundiDownloadRequest
):
    """Download assignment ZIP from eFundi and start assessment."""
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(status_code=500, detail="Playwright not available")

    # Get saved session
    session = efundi_sessions.find_one({}, sort=[("authenticated_at", -1)])
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with eFundi. Please authenticate first.",
        )

    # Verify rubric exists
    try:
        rubric = rubrics_collection.find_one({"_id": ObjectId(request.rubric_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid rubric ID")
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    # Create job
    job_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    job = {
        "job_id": job_id,
        "status": "starting",
        "rubric_id": str(rubric["_id"]),
        "rubric_name": rubric["name"],
        "assignment_url": request.assignment_url,
        "assignment_name": request.assignment_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "progress": 0,
        "total": 0,
        "results": None,
        "logs": [],
    }
    jobs_collection.insert_one(job)

    def update_job_log(message):
        jobs_collection.update_one(
            {"job_id": job_id},
            {
                "$push": {
                    "logs": {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "message": message,
                    }
                }
            },
        )
        print(f"[Job {job_id}] {message}")

    def update_status(status):
        jobs_collection.update_one({"job_id": job_id}, {"$set": {"status": status}})

    # Process in background
    async def download_and_process():
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    storage_state=session["storage_state"]
                )
                page = await context.new_page()
                page.set_default_timeout(60000)  # 60 second timeout

                update_job_log("Starting browser automation...")
                update_status("navigating")

                assignment_url = request.assignment_url
                assignment_name = request.assignment_name

                # Step 1: Navigate to the site/tool URL
                update_job_log(f"Navigating to: {assignment_url}")
                await page.goto(assignment_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)

                # Save debug screenshot
                debug_dir = OUTPUT_DIR / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                await page.screenshot(
                    path=str(debug_dir / f"{job_id}_01_initial.png"), full_page=True
                )
                update_job_log("Saved initial page screenshot")

                # Step 2: Click on "Assignments" in the left sidebar if we're not already there
                update_job_log("Looking for Assignments tab in sidebar...")
                assignments_selectors = [
                    "a.Mrphs-toolsNav__menuitem--link:has-text('Assignments')",
                    "li a:has-text('Assignments')",
                    ".Mrphs-toolsNav__menuitem span:has-text('Assignments')",
                    "a[title*='Assignments']",
                ]

                for selector in assignments_selectors:
                    try:
                        loc = page.locator(selector)
                        if await loc.count() > 0:
                            update_job_log(f"Found Assignments with: {selector}")
                            await loc.first.click()
                            await page.wait_for_timeout(3000)
                            break
                    except:
                        continue

                await page.screenshot(
                    path=str(debug_dir / f"{job_id}_02_assignments_tab.png"),
                    full_page=True,
                )

                # Step 3: Find the specific assignment row and click "Grade" link
                # The assignments are in a table with columns: Assignment Title, For, Status, Open Date, Due Date, In/New, Scale, Remove?
                # Each row has links: Edit | Duplicate | Grade
                # IMPORTANT: There are 2 Grade links per row - we need the one with sakai_action=doGrade_assignment
                update_job_log("Looking for assignment row to click Grade...")
                update_status("finding_assignment")

                assignment_name = request.assignment_name
                grade_clicked = False

                if assignment_name:
                    update_job_log(f"Looking for assignment: {assignment_name}")

                    # Look for the specific Grade link with the correct action
                    # The Grade link has onclick containing 'doGrade_assignment'
                    grade_link_selectors = [
                        "a[onclick*='doGrade_assignment']:has-text('Grade')",
                        f"tr:has-text('{assignment_name}') a[onclick*='doGrade_assignment']",
                        f"a[href*='doGrade_assignment'][href*='{assignment_name.replace(' ', '')}']",
                    ]

                    for selector in grade_link_selectors:
                        try:
                            loc = page.locator(selector)
                            count = await loc.count()
                            update_job_log(
                                f"Selector '{selector}' found {count} elements"
                            )
                            if count > 0:
                                # Click the first matching one
                                await loc.first.click()
                                await page.wait_for_timeout(4000)
                                grade_clicked = True
                                update_job_log(f"Clicked Grade link with: {selector}")
                                break
                        except Exception as e:
                            update_job_log(f"Selector error: {e}")
                            continue

                # If still not clicked, try a more general approach but be specific about the action
                if not grade_clicked:
                    update_job_log(
                        "Trying to find Grade link with doGrade_assignment action..."
                    )

                    # Get all links and find ones with the correct action
                    grade_links = page.locator("a[onclick*='doGrade_assignment']")
                    count = await grade_links.count()
                    update_job_log(
                        f"Found {count} Grade links with doGrade_assignment action"
                    )

                    if count > 0:
                        # If we have an assignment name, try to find the right one
                        if assignment_name:
                            for i in range(count):
                                link = grade_links.nth(i)
                                onclick = await link.get_attribute("onclick") or ""
                                text = await link.inner_text()
                                update_job_log(f"Grade link {i}: text='{text}'")
                                # The assignment name might be in the onclick or nearby
                                if assignment_name.lower().replace(
                                    " ", ""
                                ) in onclick.lower().replace(" ", ""):
                                    await link.click()
                                    await page.wait_for_timeout(4000)
                                    grade_clicked = True
                                    update_job_log(
                                        f"Clicked Grade link {i} for {assignment_name}"
                                    )
                                    break

                        # If still not clicked, click the last one (Assignment 1 is typically at the bottom)
                        if not grade_clicked:
                            await grade_links.last.click()
                            await page.wait_for_timeout(4000)
                            grade_clicked = True
                            update_job_log(
                                "Clicked last Grade link (likely Assignment 1)"
                            )

                if not grade_clicked:
                    await page.screenshot(
                        path=str(debug_dir / f"{job_id}_03_no_grade.png"),
                        full_page=True,
                    )
                    raise Exception("Could not find Grade link for any assignment")

                await page.screenshot(
                    path=str(debug_dir / f"{job_id}_03_after_grade_click.png"),
                    full_page=True,
                )
                current_url = page.url
                update_job_log(f"Current URL after Grade click: {current_url}")

                # Verify we're on the submissions page, not Gradebook
                if "Gradebook" in await page.title() or "/tool/9f40a622" in current_url:
                    update_job_log(
                        "WARNING: Landed on Gradebook instead of submissions page!"
                    )
                    # Go back and try a different approach
                    await page.go_back()
                    await page.wait_for_timeout(2000)

                # Step 4: Now we should be on the grading/submissions page
                # Look for "Download All" link
                update_job_log("Looking for Download All on grading page...")
                update_status("finding_download")

                download_all_found = False
                download_all_selectors = [
                    "a:has-text('Download All')",
                    "a.assignment-item:has-text('Download All')",
                    "a[href*='doPrep_download_all']",
                    "a[href*='downloadAll']",
                    "a.navIntraTool:has-text('Download')",
                    "span:has-text('Download All') a",
                    "input[value='Download All']",
                ]

                for selector in download_all_selectors:
                    try:
                        loc = page.locator(selector)
                        count = await loc.count()
                        update_job_log(f"Selector '{selector}' found {count} elements")
                        if count > 0:
                            update_job_log(f"Clicking Download All with: {selector}")
                            await loc.first.click()
                            await page.wait_for_timeout(3000)
                            download_all_found = True
                            break
                    except Exception as e:
                        update_job_log(f"Selector error: {e}")
                        continue

                await page.screenshot(
                    path=str(debug_dir / f"{job_id}_04_download_page.png"),
                    full_page=True,
                )

                download_all_selectors = [
                    "a:has-text('Download All')",
                    "a.actionLink:has-text('Download')",
                    "a[href*='downloadAll']",
                    "span:has-text('Download All') a",
                    ".navIntraTool a:has-text('Download')",
                ]

                download_all_found = False
                for selector in download_all_selectors:
                    try:
                        loc = page.locator(selector)
                        if await loc.count() > 0:
                            update_job_log(f"Found Download All with: {selector}")
                            await loc.first.click()
                            await page.wait_for_timeout(3000)
                            download_all_found = True
                            break
                    except:
                        continue

                if not download_all_found:
                    # Maybe we're already on the download page, or it's in a different location
                    update_job_log(
                        "Download All link not found with standard selectors"
                    )
                    # Check if we can see the download options already
                    if (
                        await page.locator(
                            "input#selectall, input[value='all']"
                        ).count()
                        > 0
                    ):
                        update_job_log("Already on download options page")
                        download_all_found = True

                await page.screenshot(
                    path=str(debug_dir / f"{job_id}_04_download_page.png"),
                    full_page=True,
                )

                if not download_all_found:
                    # Provide detailed error with page content
                    page_title = await page.title()
                    page_url = page.url
                    update_job_log(f"Page title: {page_title}, URL: {page_url}")
                    raise Exception(
                        f"Could not find Download All. Check debug screenshots in {debug_dir}"
                    )

                # Step 5: Select download options
                update_job_log("Selecting download options...")
                update_status("selecting_options")

                # Check "All" checkbox
                all_checkbox = page.locator(
                    "input#selectall, input[type='checkbox'][name='selectall'], input[value='all']"
                )
                if await all_checkbox.count() > 0:
                    await all_checkbox.first.check()
                    update_job_log("Checked 'All' checkbox")

                # Check "Student submission attachment(s)"
                student_attach = page.locator(
                    "input#withSubmission, input[name='withSubmission']"
                )
                if await student_attach.count() > 0:
                    await student_attach.first.check()
                    update_job_log("Checked student submissions")

                # Check "Grade file"
                grade_file = page.locator("input#withGrade, input[name='withGrade']")
                if await grade_file.count() > 0:
                    await grade_file.first.check()
                    update_job_log("Checked grade file")

                # Select CSV format
                csv_radio = page.locator(
                    "input[type='radio'][value='csv'], input#csvFormat"
                )
                if await csv_radio.count() > 0:
                    await csv_radio.first.check()
                    update_job_log("Selected CSV format")

                # Check "Feedback comments"
                feedback_comments = page.locator(
                    "input#withFeedbackText, input[name='withFeedbackText']"
                )
                if await feedback_comments.count() > 0:
                    await feedback_comments.first.check()
                    update_job_log("Checked feedback comments")

                # Check "Feedback Attachment(s)"
                feedback_attach = page.locator(
                    "input#withFeedbackAttach, input[name='withFeedbackAttach']"
                )
                if await feedback_attach.count() > 0:
                    await feedback_attach.first.check()
                    update_job_log("Checked feedback attachments")

                # Check "Include students who have not yet submitted"
                non_submit = page.locator(
                    "input#withoutSubmission, input[name='withoutSubmission']"
                )
                if await non_submit.count() > 0:
                    await non_submit.first.check()
                    update_job_log("Checked include non-submitters")

                await page.wait_for_timeout(1000)
                await page.screenshot(
                    path=str(debug_dir / f"{job_id}_05_options_selected.png"),
                    full_page=True,
                )

                # Step 6: Click Download button
                update_job_log("Clicking Download button...")
                update_status("downloading_zip")

                zip_path = UPLOAD_DIR / f"efundi_{job_id}.zip"

                # The download button is a button with class "active" or text "Download"
                download_btn_selectors = [
                    "button.active:has-text('Download')",
                    "button:has-text('Download')",
                    "input[type='submit'][value='Download']",
                    "input.active[type='submit']",
                    "form button.active",
                    "input[name='eventSubmit_doDownload_all']",
                ]

                download_btn = None
                for selector in download_btn_selectors:
                    try:
                        loc = page.locator(selector)
                        count = await loc.count()
                        update_job_log(
                            f"Download button selector '{selector}' found {count} elements"
                        )
                        if count > 0:
                            download_btn = loc.first
                            update_job_log(f"Found Download button with: {selector}")
                            break
                    except Exception as e:
                        update_job_log(f"Button selector error: {e}")
                        continue

                if not download_btn:
                    await page.screenshot(
                        path=str(debug_dir / f"{job_id}_06_no_download_btn.png"),
                        full_page=True,
                    )
                    raise Exception("Could not find Download button")

                # Wait for download
                try:
                    async with page.expect_download(
                        timeout=180000
                    ) as download_info:  # 3 min timeout
                        await download_btn.click()
                        update_job_log("Waiting for download to complete...")

                    download = await download_info.value
                    await download.save_as(str(zip_path))
                    update_job_log(f"Downloaded ZIP to: {zip_path}")
                except Exception as e:
                    await page.screenshot(
                        path=str(debug_dir / f"{job_id}_07_download_error.png"),
                        full_page=True,
                    )
                    raise Exception(f"Download failed: {e}")

                await browser.close()

                # Step 7: Process the downloaded ZIP
                update_job_log("Processing downloaded submissions...")
                update_status("processing")
                jobs_collection.update_one(
                    {"job_id": job_id}, {"$set": {"zip_file": str(zip_path)}}
                )

                output_dir = OUTPUT_DIR / job_id
                output_dir.mkdir(parents=True, exist_ok=True)

                results = await process_efundi_zip(zip_path, rubric, output_dir)
                update_job_log(
                    f"Processed {results.get('submissions_processed', 0)} submissions"
                )

                jobs_collection.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "status": "completed",
                            "results": results,
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )
                update_job_log("Job completed successfully!")

        except Exception as e:
            error_msg = str(e)
            print(f"[eFundi Download Error] {error_msg}")
            update_job_log(f"ERROR: {error_msg}")
            jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": error_msg,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )

    background_tasks.add_task(download_and_process)

    return {
        "success": True,
        "job_id": job_id,
        "message": "Download and assessment started. Check /api/job/{job_id} for status.",
    }


@app.post("/api/efundi/upload-results/{job_id}")
async def efundi_upload_results(job_id: str, background_tasks: BackgroundTasks):
    """Upload graded results back to eFundi."""
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(status_code=500, detail="Playwright not available")

    # Get job
    job = jobs_collection.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")

    results = job.get("results", {})
    output_zip = results.get("output_zip_path")

    if not output_zip or not Path(output_zip).exists():
        raise HTTPException(status_code=404, detail="Output ZIP not found")

    # Get session
    session = efundi_sessions.find_one({}, sort=[("authenticated_at", -1)])
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated with eFundi")

    assignment_url = job.get("assignment_url")
    if not assignment_url:
        raise HTTPException(status_code=400, detail="Assignment URL not found in job")

    async def upload_to_efundi():
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    storage_state=session["storage_state"]
                )
                page = await context.new_page()

                await page.goto(assignment_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                # Click Upload All
                upload_all = page.locator("a:has-text('Upload All')")
                if await upload_all.count() > 0:
                    await upload_all.first.click()
                    await page.wait_for_timeout(2000)

                # Upload file
                file_input = page.locator("input[type='file']").first
                await file_input.set_input_files(output_zip)

                # Click Upload button
                upload_btn = page.locator(
                    "button:has-text('Upload'), input[type='submit'][value='Upload']"
                )
                await upload_btn.first.click()
                await page.wait_for_timeout(5000)

                await browser.close()

                jobs_collection.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "upload_status": "completed",
                            "uploaded_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )

        except Exception as e:
            jobs_collection.update_one(
                {"job_id": job_id},
                {"$set": {"upload_status": "failed", "upload_error": str(e)}},
            )

    background_tasks.add_task(upload_to_efundi)

    return {
        "success": True,
        "message": "Upload started. Results will be uploaded to eFundi.",
    }

# ===================== EXAM BUILDER =====================


class ExamTopic(BaseModel):
    topic: str
    time_period: Optional[str] = None
    key_events: Optional[List[str]] = None
    key_figures: Optional[List[str]] = None


class ExamGenerationRequest(BaseModel):
    module_code: str = "HISE411"
    module_name: str = "HISTORY SNR & FET 4A"
    topics: List[str]  # Topics for source-based questions
    essay_topic: str  # Topic for the essay question
    methodology_topic: str  # Topic for methodology question
    total_marks: int = 125
    duration_hours: int = 3
    additional_instructions: Optional[str] = None


async def generate_exam_sources(
    topic: str, question_number: int, opportunity: int=1
) -> Dict[str, Any]:
    """Generate legitimate historical sources for a source-based question."""

    variation_instruction = ""
    if opportunity == 2:
        variation_instruction = """
IMPORTANT: This is for a SECOND OPPORTUNITY exam. Generate DIFFERENT sources than would typically be used.
- Use alternative primary sources from the same period
- Choose different perspectives or lesser-known documents
- Include different visual sources (different cartoons, maps, or photographs)
- Maintain the same academic rigor but with fresh material"""

    prompt = f"""You are a History exam creator. Generate authentic historical sources for a source-based question on: "{topic}"
{variation_instruction}

Generate 2-3 PRIMARY SOURCES that are historically accurate and legitimate. Include:
1. A text excerpt (speech, memoir, letter, treaty, newspaper article) with author, date, and context
2. A visual source description (political cartoon, photograph, map, or propaganda poster) with date and origin
3. Optionally, a secondary source (historian's analysis) with author and publication

For each source, provide:
- Source label (Source A, Source B, etc.)
- Type (Speech/Cartoon/Map/Memoir/etc.)
- Author or origin
- Date
- Full text or detailed description
- Historical context

IMPORTANT: Use REAL historical figures, events, and approximate historical content. The sources should be educationally accurate.

Respond in JSON format:
{{
    "topic": "{topic}",
    "sources": [
        {{
            "label": "Source A",
            "type": "Political Cartoon",
            "title": "The Iron Curtain Descends",
            "author": "David Low",
            "date": "March 1946",
            "publication": "Evening Standard",
            "content": "Description of the cartoon showing Churchill's Iron Curtain speech...",
            "context": "Published shortly after Churchill's famous Fulton speech..."
        }}
    ]
}}"""

    try:
        response = openai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a History education expert who creates authentic, academically rigorous exam materials using real historical sources.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[Exam Source Generation Error] {e}")
        return {"topic": topic, "sources": [], "error": str(e)}


async def generate_source_questions(
    sources: List[Dict], topic: str, total_marks: int=25
) -> List[Dict]:
    """Generate questions based on the provided sources."""

    sources_text = "\n\n".join(
        [
            f"{s['label']}: {s['type']} - {s.get('title', '')} by {s.get('author', 'Unknown')} ({s.get('date', '')})\n{s.get('content', '')}"
            for s in sources
        ]
    )

    prompt = f"""Create source-based questions for a History exam on "{topic}".

SOURCES PROVIDED:
{sources_text}

Create questions totaling {total_marks} marks using these cognitive levels:
- LEVEL 1 (1-2 marks): Extraction/identification questions
- LEVEL 2 (3-4 marks): Explanation/interpretation questions  
- LEVEL 3 (5-6 marks): Analysis/evaluation questions
- LEVEL 4 (6-8 marks): Synthesis/comparison questions

Include questions that:
1. Ask students to identify/extract information from sources (2-3 questions)
2. Ask students to explain concepts or motivations (2-3 questions)
3. Ask students to analyze bias, reliability, or perspective (1-2 questions)
4. Ask students to use multiple sources together (1 question)

Respond in JSON format:
{{
    "questions": [
        {{
            "number": "1.1",
            "source_reference": "Source A",
            "question": "What does the cartoonist suggest about...",
            "marks": 2,
            "cognitive_level": 1,
            "expected_answer_points": ["Point 1", "Point 2"]
        }}
    ],
    "total_marks": {total_marks}
}}"""

    try:
        response = openai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a History exam question writer. Create clear, academically appropriate questions that test historical thinking skills.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=2500,
            response_format={"type": "json_object"},
        )

        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[Question Generation Error] {e}")
        return {"questions": [], "error": str(e)}


async def generate_methodology_question(topic: str, marks: int=25) -> Dict[str, Any]:
    """Generate a methodology question for trainee teachers."""

    prompt = f"""Create a methodology question for History education students (B.Ed.) on the topic: "{topic}"

The question should ask students to create a lesson plan or teaching resource. Include:
1. A clear task description
2. Required components (lesson steps, resources, aims, historical skills, classroom management)
3. A marking rubric with clear criteria

This tests pedagogical skills, not just historical knowledge.

Respond in JSON format:
{{
    "question_number": "3",
    "title": "Methodology Question",
    "topic": "{topic}",
    "task": "Use the topic on {topic} to construct a lesson plan strategy...",
    "requirements": [
        "Lesson steps for teacher and learner",
        "Resources to be used",
        "Aim of lesson",
        "Historical skills integration",
        "Classroom management strategies"
    ],
    "marks": {marks},
    "rubric": {{
        "Lesson Steps": {{
            "3 marks": "Clear, detailed steps with logical progression",
            "2 marks": "Adequate steps but lacks detail",
            "1 mark": "Minimal or unclear steps"
        }},
        "Resources": {{
            "3 marks": "Varied, appropriate resources identified",
            "2 marks": "Some resources mentioned",
            "1 mark": "Limited resource identification"
        }},
        "Aim & Outcomes": {{
            "3 marks": "Clear, measurable learning outcomes",
            "2 marks": "Outcomes present but vague",
            "1 mark": "Unclear or missing outcomes"
        }},
        "Historical Skills": {{
            "3 marks": "Multiple skills integrated effectively",
            "2 marks": "Some skills mentioned",
            "1 mark": "Limited skill integration"
        }},
        "Classroom Management": {{
            "3 marks": "Detailed strategies for diverse learners",
            "2 marks": "Basic management strategies",
            "1 mark": "Minimal consideration"
        }}
    }}
}}"""

    try:
        response = openai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an education expert creating assessment materials for trainee History teachers.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[Methodology Question Error] {e}")
        return {"error": str(e)}


async def generate_essay_question(
    topic: str, marks: int=50, opportunity: int=1
) -> Dict[str, Any]:
    """Generate an essay question with marking matrix."""

    variation_instruction = ""
    if opportunity == 2:
        variation_instruction = """
IMPORTANT: This is for a SECOND OPPORTUNITY exam. Create a DIFFERENT essay question on the same topic:
- Use a different angle or perspective on the topic
- Ask about different aspects (e.g., if first asks about causes, this should ask about consequences)
- Phrase the question differently while maintaining the same academic rigor
- The essay matrix/rubric can remain the same"""

    prompt = f"""Create a {marks}-mark essay question for a History exam on the topic: "{topic}"
{variation_instruction}

The question should:
1. Be thought-provoking and allow for argumentation
2. Require analysis of causes, consequences, or significance
3. Allow students to demonstrate in-depth historical knowledge

Also create an essay matrix/rubric with these criteria:
- Content & Knowledge (15 marks)
- Analysis & Argumentation (15 marks)
- Use of Evidence (10 marks)
- Structure & Coherence (5 marks)
- Language & Expression (5 marks)

Respond in JSON format:
{{
    "question_number": "4",
    "title": "Essay Question",
    "topic": "{topic}",
    "question": "Evaluate the extent to which...",
    "context": "Brief contextual statement to set up the question",
    "marks": {marks},
    "matrix": {{
        "Content & Knowledge": {{
            "weight": 15,
            "levels": {{
                "Excellent (13-15)": "Comprehensive knowledge, accurate facts, nuanced understanding",
                "Good (10-12)": "Good knowledge with minor gaps",
                "Satisfactory (7-9)": "Basic knowledge, some inaccuracies",
                "Needs Work (0-6)": "Limited knowledge, significant gaps"
            }}
        }},
        "Analysis & Argumentation": {{
            "weight": 15,
            "levels": {{
                "Excellent (13-15)": "Sophisticated analysis, clear thesis, well-reasoned arguments",
                "Good (10-12)": "Good analysis with clear argument",
                "Satisfactory (7-9)": "Some analysis but superficial",
                "Needs Work (0-6)": "Descriptive rather than analytical"
            }}
        }},
        "Use of Evidence": {{
            "weight": 10,
            "levels": {{
                "Excellent (9-10)": "Excellent use of relevant evidence",
                "Good (7-8)": "Good evidence with some gaps",
                "Satisfactory (5-6)": "Limited evidence",
                "Needs Work (0-4)": "Little to no supporting evidence"
            }}
        }},
        "Structure & Coherence": {{
            "weight": 5,
            "levels": {{
                "Excellent (5)": "Clear introduction, body, conclusion; logical flow",
                "Good (4)": "Generally well-structured",
                "Satisfactory (3)": "Some structure issues",
                "Needs Work (0-2)": "Poor organization"
            }}
        }},
        "Language & Expression": {{
            "weight": 5,
            "levels": {{
                "Excellent (5)": "Clear, academic language; appropriate terminology",
                "Good (4)": "Generally clear expression",
                "Satisfactory (3)": "Some language issues",
                "Needs Work (0-2)": "Significant language problems"
            }}
        }}
    }}
}}"""

    try:
        response = openai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a History education expert creating rigorous essay questions.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2500,
            response_format={"type": "json_object"},
        )

        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[Essay Question Error] {e}")
        return {"error": str(e)}


def create_exam_docx(exam_data: Dict[str, Any], output_path: Path) -> Path:
    """Generate a formatted DOCX exam paper."""

    if not DOCX_AVAILABLE:
        raise HTTPException(status_code=500, detail="python-docx not available")

    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Set up styles
    style = doc.styles["Normal"]
    font = style.font  # type: ignore[attr-defined]
    font.name = "Times New Roman"
    font.size = Pt(12)

    # ===== HEADER =====
    header = doc.add_paragraph()
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header.add_run(f"{exam_data['module_code']}: {exam_data['module_name']}")
    run.bold = True
    run.font.size = Pt(16)

    # Add opportunity label if present
    if exam_data.get("opportunity_label"):
        opp_para = doc.add_paragraph()
        opp_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = opp_para.add_run(f"({exam_data['opportunity_label']})")
        run.bold = True
        run.font.size = Pt(12)

    # Exam details table
    details_table = doc.add_table(rows=4, cols=2)
    details_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    details = [
        ("Duration:", f"{exam_data['duration_hours']} hours"),
        ("Total Marks:", str(exam_data["total_marks"])),
        ("Date:", datetime.now().strftime("%B %Y")),
        ("Instructions:", "Answer ALL questions"),
    ]
    for i, (label, value) in enumerate(details):
        details_table.rows[i].cells[0].text = label
        details_table.rows[i].cells[1].text = value

    doc.add_paragraph()  # Spacer

    # ===== SECTION 1: SOURCE-BASED QUESTIONS =====
    for q_num, source_question in enumerate(exam_data.get("source_questions", []), 1):
        # Question header
        q_header = doc.add_paragraph()
        run = q_header.add_run(
            f"QUESTION {q_num}: {source_question.get('topic', 'Source-Based Question')}"
        )
        run.bold = True
        run.font.size = Pt(14)

        marks_para = doc.add_paragraph()
        marks_para.add_run(
            f"[{source_question.get('total_marks', 25)} marks]"
        ).italic = True

        # Sources
        for source in source_question.get("sources", []):
            source_para = doc.add_paragraph()
            source_para.add_run(f"{source['label']}: ").bold = True
            source_para.add_run(f"{source.get('type', '')} - {source.get('title', '')}")

            if source.get("author"):
                doc.add_paragraph(
                    f"Author/Origin: {source['author']}, {source.get('date', '')}"
                )

            content_para = doc.add_paragraph()
            content_para.add_run(source.get("content", "")).italic = True

            if source.get("context"):
                ctx = doc.add_paragraph()
                ctx.add_run(f"Context: {source['context']}").font.size = Pt(10)

            doc.add_paragraph()  # Spacer

        # Questions
        questions_header = doc.add_paragraph()
        questions_header.add_run(
            "Study the sources above and answer the following questions:"
        ).bold = True

        for q in source_question.get("questions", []):
            q_para = doc.add_paragraph()
            q_para.add_run(f"{q['number']} ")
            if q.get("source_reference"):
                q_para.add_run(f"[{q['source_reference']}] ")
            q_para.add_run(q["question"])
            q_para.add_run(f" ({q['marks']})").bold = True

        doc.add_paragraph()  # Spacer
        doc.add_paragraph("_" * 60)

    # ===== SECTION 2: METHODOLOGY =====
    if exam_data.get("methodology_question"):
        mq = exam_data["methodology_question"]

        m_header = doc.add_paragraph()
        run = m_header.add_run(
            f"QUESTION {len(exam_data.get('source_questions', [])) + 1}: METHODOLOGY"
        )
        run.bold = True
        run.font.size = Pt(14)

        marks_para = doc.add_paragraph()
        marks_para.add_run(f"[{mq.get('marks', 25)} marks]").italic = True

        task_para = doc.add_paragraph()
        task_para.add_run(mq.get("task", ""))

        if mq.get("requirements"):
            req_para = doc.add_paragraph()
            req_para.add_run("Your response must address:").bold = True
            for req in mq["requirements"]:
                doc.add_paragraph(f"• {req}", style="List Bullet")

        # Rubric table
        if mq.get("rubric"):
            doc.add_paragraph()
            rubric_header = doc.add_paragraph()
            rubric_header.add_run("Detailed Marking Rubric:").bold = True

            rubric = mq["rubric"]
            table = doc.add_table(rows=len(rubric) + 1, cols=4)
            table.style = "Table Grid"

            # Header row
            headers = [
                "Criterion",
                "3 Marks (Excellent)",
                "2 Marks (Good)",
                "1 Mark (Basic)",
            ]
            for i, h in enumerate(headers):
                cell = table.rows[0].cells[i]
                cell.text = h
                cell.paragraphs[0].runs[0].bold = True
                # Shade header row
                from docx.oxml import parse_xml
                from docx.oxml.ns import nsdecls

                shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="D9E2F3"/>')
                cell._tc.get_or_add_tcPr().append(shading_elm)

            # Data rows
            for row_idx, (criterion, levels) in enumerate(rubric.items(), 1):
                table.rows[row_idx].cells[0].text = criterion
                table.rows[row_idx].cells[1].text = levels.get("3 marks", "")
                table.rows[row_idx].cells[2].text = levels.get("2 marks", "")
                table.rows[row_idx].cells[3].text = levels.get("1 mark", "")

        # Marking notes
        doc.add_paragraph()
        notes = doc.add_paragraph()
        notes.add_run("Marking Notes:").bold = True
        doc.add_paragraph(
            "• Award marks holistically based on overall quality", style="List Bullet"
        )
        doc.add_paragraph(
            "• Consider creativity and practical applicability", style="List Bullet"
        )
        doc.add_paragraph(
            "• Historical accuracy of content is essential", style="List Bullet"
        )

        doc.add_paragraph("_" * 60)

    # ===== SECTION 3: ESSAY =====
    if exam_data.get("essay_question"):
        eq = exam_data["essay_question"]

        e_header = doc.add_paragraph()
        q_num = len(exam_data.get("source_questions", [])) + 2
        run = e_header.add_run(f"QUESTION {q_num}: ESSAY")
        run.bold = True
        run.font.size = Pt(14)

        marks_para = doc.add_paragraph()
        marks_para.add_run(f"[{eq.get('marks', 50)} marks]").italic = True

        if eq.get("context"):
            ctx = doc.add_paragraph()
            ctx.add_run(eq["context"]).italic = True

        q_para = doc.add_paragraph()
        q_para.add_run(eq.get("question", ""))

        # Essay matrix
        if eq.get("matrix"):
            doc.add_paragraph()
            matrix_header = doc.add_paragraph()
            matrix_header.add_run("ESSAY ASSESSMENT MATRIX:").bold = True
            matrix_header.runs[0].font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

            matrix = eq["matrix"]

            # Create comprehensive table
            table = doc.add_table(rows=len(matrix) + 1, cols=5)
            table.style = "Table Grid"

            # Header with mark ranges
            headers = [
                "Criterion (Weight)",
                "Excellent",
                "Good",
                "Satisfactory",
                "Needs Improvement",
            ]
            for i, h in enumerate(headers):
                cell = table.rows[0].cells[i]
                cell.text = h
                cell.paragraphs[0].runs[0].bold = True
                # Shade header
                from docx.oxml import parse_xml
                from docx.oxml.ns import nsdecls

                shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="FDE9D9"/>')
                cell._tc.get_or_add_tcPr().append(shading_elm)

            # Data rows with full descriptors
            for row_idx, (criterion, data) in enumerate(matrix.items(), 1):
                weight = data.get("weight", 0)
                table.rows[row_idx].cells[0].text = f"{criterion}\n({weight} marks)"

                levels = data.get("levels", {})
                level_names = ["Excellent", "Good", "Satisfactory", "Needs Work"]

                for col_idx, level_name in enumerate(level_names):
                    matching_key = [
                        k for k in levels.keys() if level_name.lower() in k.lower()
                    ]
                    if matching_key:
                        # Include mark range in cell
                        key = matching_key[0]
                        # Extract mark range from key if present
                        mark_range = ""
                        import re

                        range_match = re.search(r"\(([^)]+)\)", key)
                        if range_match:
                            mark_range = f"[{range_match.group(1)}]\n"
                        table.rows[row_idx].cells[
                            col_idx + 1
                        ].text = f"{mark_range}{levels[key]}"

            doc.add_paragraph()

            # Marking guidelines
            guide_header = doc.add_paragraph()
            guide_header.add_run("Essay Marking Guidelines:").bold = True

            doc.add_paragraph(
                "1. Read the entire essay before assigning marks", style="List Bullet"
            )
            doc.add_paragraph(
                "2. Assess each criterion independently using the matrix",
                style="List Bullet",
            )
            doc.add_paragraph(
                "3. Use the full range of marks within each level", style="List Bullet"
            )
            doc.add_paragraph(
                "4. Provide written feedback highlighting strengths and areas for improvement",
                style="List Bullet",
            )
            doc.add_paragraph(
                "5. Total marks = sum of all criteria scores", style="List Bullet"
            )

            # Mark calculation box
            doc.add_paragraph()
            calc_header = doc.add_paragraph()
            calc_header.add_run("Mark Calculation:").bold = True

            calc_table = doc.add_table(rows=len(matrix) + 2, cols=2)
            calc_table.style = "Table Grid"

            calc_table.rows[0].cells[0].text = "Criterion"
            calc_table.rows[0].cells[1].text = "Score"
            calc_table.rows[0].cells[0].paragraphs[0].runs[0].bold = True
            calc_table.rows[0].cells[1].paragraphs[0].runs[0].bold = True

            for row_idx, (criterion, data) in enumerate(matrix.items(), 1):
                calc_table.rows[row_idx].cells[
                    0
                ].text = f"{criterion} (max {data.get('weight', 0)})"
                calc_table.rows[row_idx].cells[1].text = "_____ / " + str(
                    data.get("weight", 0)
                )

            # Total row
            total_row = len(matrix) + 1
            calc_table.rows[total_row].cells[0].text = "TOTAL"
            calc_table.rows[total_row].cells[0].paragraphs[0].runs[0].bold = True
            calc_table.rows[total_row].cells[1].text = f"_____ / {eq.get('marks', 50)}"
            calc_table.rows[total_row].cells[1].paragraphs[0].runs[0].bold = True

    # ===== FOOTER =====
    doc.add_paragraph()
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run(f"TOTAL: {exam_data['total_marks']} marks").bold = True

    confidential = doc.add_paragraph()
    confidential.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = confidential.add_run("CONFIDENTIAL - FOR EXAMINER USE ONLY")
    run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
    run.bold = True

    # Save
    doc.save(str(output_path))
    return output_path


def create_memorandum_docx(exam_data: Dict[str, Any], output_path: Path) -> Path:
    """Generate a memorandum/answer key document for the exam."""

    if not DOCX_AVAILABLE:
        raise HTTPException(status_code=500, detail="python-docx not available")

    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Set up styles
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(12)

    # ===== HEADER =====
    header = doc.add_paragraph()
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header.add_run(f"{exam_data['module_code']}: {exam_data['module_name']}")
    run.bold = True
    run.font.size = Pt(16)

    # Add opportunity label if present
    if exam_data.get("opportunity_label"):
        opp_para = doc.add_paragraph()
        opp_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = opp_para.add_run(f"({exam_data['opportunity_label']})")
        run.bold = True
        run.font.size = Pt(12)

    memo_title = doc.add_paragraph()
    memo_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = memo_title.add_run("MEMORANDUM / MARKING GUIDE")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)  # Dark red

    doc.add_paragraph()

    # ===== SOURCE-BASED QUESTIONS ANSWERS =====
    for q_num, source_question in enumerate(exam_data.get("source_questions", []), 1):
        q_header = doc.add_paragraph()
        run = q_header.add_run(
            f"QUESTION {q_num}: {source_question.get('topic', 'Source-Based Question')} - ANSWERS"
        )
        run.bold = True
        run.font.size = Pt(14)

        marks_para = doc.add_paragraph()
        marks_para.add_run(
            f"[{source_question.get('total_marks', 25)} marks]"
        ).italic = True

        # Answer key for each question
        for q in source_question.get("questions", []):
            q_para = doc.add_paragraph()
            q_para.add_run(f"{q['number']} ").bold = True
            q_para.add_run(f"({q['marks']} marks)")

            # Question text
            question_text = doc.add_paragraph()
            question_text.add_run(f"Question: {q['question']}").italic = True

            # Expected answer points
            if q.get("expected_answer_points"):
                answer_header = doc.add_paragraph()
                answer_header.add_run("Expected Answer Points:").bold = True

                for point in q["expected_answer_points"]:
                    point_para = doc.add_paragraph(f"• {point}", style="List Bullet")
                    # Color the answer points green
                    for run in point_para.runs:
                        run.font.color.rgb = RGBColor(0x00, 0x80, 0x00)

            # Cognitive level
            if q.get("cognitive_level"):
                level_para = doc.add_paragraph()
                level_para.add_run(
                    f"Cognitive Level: {q['cognitive_level']}"
                ).font.size = Pt(10)

            doc.add_paragraph()  # Spacer

        doc.add_paragraph("_" * 60)

    # ===== METHODOLOGY MARKING GUIDE =====
    if exam_data.get("methodology_question"):
        mq = exam_data["methodology_question"]

        m_header = doc.add_paragraph()
        run = m_header.add_run(
            f"QUESTION {len(exam_data.get('source_questions', [])) + 1}: METHODOLOGY - MARKING GUIDE"
        )
        run.bold = True
        run.font.size = Pt(14)

        marks_para = doc.add_paragraph()
        marks_para.add_run(f"[{mq.get('marks', 25)} marks]").italic = True

        # Marking rubric table with detailed descriptors
        if mq.get("rubric"):
            rubric_header = doc.add_paragraph()
            rubric_header.add_run("Detailed Marking Rubric:").bold = True

            rubric = mq["rubric"]
            table = doc.add_table(rows=len(rubric) + 1, cols=4)
            table.style = "Table Grid"

            # Header row
            headers = [
                "Criterion",
                "3 Marks (Excellent)",
                "2 Marks (Good)",
                "1 Mark (Basic)",
            ]
            for i, h in enumerate(headers):
                cell = table.rows[0].cells[i]
                cell.text = h
                cell.paragraphs[0].runs[0].bold = True
                # Shade header row
                from docx.oxml import parse_xml
                from docx.oxml.ns import nsdecls

                shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="D9E2F3"/>')
                cell._tc.get_or_add_tcPr().append(shading_elm)

            # Data rows
            for row_idx, (criterion, levels) in enumerate(rubric.items(), 1):
                table.rows[row_idx].cells[0].text = criterion
                table.rows[row_idx].cells[1].text = levels.get("3 marks", "")
                table.rows[row_idx].cells[2].text = levels.get("2 marks", "")
                table.rows[row_idx].cells[3].text = levels.get("1 mark", "")

        # Marking notes
        doc.add_paragraph()
        notes = doc.add_paragraph()
        notes.add_run("Marking Notes:").bold = True
        doc.add_paragraph(
            "• Award marks holistically based on overall quality", style="List Bullet"
        )
        doc.add_paragraph(
            "• Consider creativity and practical applicability", style="List Bullet"
        )
        doc.add_paragraph(
            "• Historical accuracy of content is essential", style="List Bullet"
        )

        doc.add_paragraph("_" * 60)

    # ===== ESSAY MARKING MATRIX =====
    if exam_data.get("essay_question"):
        eq = exam_data["essay_question"]

        e_header = doc.add_paragraph()
        q_num = len(exam_data.get("source_questions", [])) + 2
        run = e_header.add_run(f"QUESTION {q_num}: ESSAY - MARKING MATRIX")
        run.bold = True
        run.font.size = Pt(14)

        marks_para = doc.add_paragraph()
        marks_para.add_run(f"[{eq.get('marks', 50)} marks]").italic = True

        # Essay question reminder
        q_para = doc.add_paragraph()
        q_para.add_run("Question: ").bold = True
        q_para.add_run(eq.get("question", ""))

        doc.add_paragraph()

        # Full Essay Assessment Matrix
        if eq.get("matrix"):
            matrix_header = doc.add_paragraph()
            matrix_header.add_run("ESSAY ASSESSMENT MATRIX:").bold = True
            matrix_header.runs[0].font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

            matrix = eq["matrix"]

            # Create comprehensive table
            table = doc.add_table(rows=len(matrix) + 1, cols=5)
            table.style = "Table Grid"

            # Header with mark ranges
            headers = [
                "Criterion (Weight)",
                "Excellent",
                "Good",
                "Satisfactory",
                "Needs Improvement",
            ]
            for i, h in enumerate(headers):
                cell = table.rows[0].cells[i]
                cell.text = h
                cell.paragraphs[0].runs[0].bold = True
                # Shade header
                from docx.oxml import parse_xml
                from docx.oxml.ns import nsdecls

                shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="FDE9D9"/>')
                cell._tc.get_or_add_tcPr().append(shading_elm)

            # Data rows with full descriptors
            for row_idx, (criterion, data) in enumerate(matrix.items(), 1):
                weight = data.get("weight", 0)
                table.rows[row_idx].cells[0].text = f"{criterion}\n({weight} marks)"

                levels = data.get("levels", {})
                level_names = ["Excellent", "Good", "Satisfactory", "Needs Work"]

                for col_idx, level_name in enumerate(level_names):
                    matching_key = [
                        k for k in levels.keys() if level_name.lower() in k.lower()
                    ]
                    if matching_key:
                        # Include mark range in cell
                        key = matching_key[0]
                        # Extract mark range from key if present
                        mark_range = ""
                        import re

                        range_match = re.search(r"\(([^)]+)\)", key)
                        if range_match:
                            mark_range = f"[{range_match.group(1)}]\n"
                        table.rows[row_idx].cells[
                            col_idx + 1
                        ].text = f"{mark_range}{levels[key]}"

            doc.add_paragraph()

            # Marking guidelines
            guide_header = doc.add_paragraph()
            guide_header.add_run("Essay Marking Guidelines:").bold = True

            doc.add_paragraph(
                "1. Read the entire essay before assigning marks", style="List Bullet"
            )
            doc.add_paragraph(
                "2. Assess each criterion independently using the matrix",
                style="List Bullet",
            )
            doc.add_paragraph(
                "3. Use the full range of marks within each level", style="List Bullet"
            )
            doc.add_paragraph(
                "4. Provide written feedback highlighting strengths and areas for improvement",
                style="List Bullet",
            )
            doc.add_paragraph(
                "5. Total marks = sum of all criteria scores", style="List Bullet"
            )

            # Mark calculation box
            doc.add_paragraph()
            calc_header = doc.add_paragraph()
            calc_header.add_run("Mark Calculation:").bold = True

            calc_table = doc.add_table(rows=len(matrix) + 2, cols=2)
            calc_table.style = "Table Grid"

            calc_table.rows[0].cells[0].text = "Criterion"
            calc_table.rows[0].cells[1].text = "Score"
            calc_table.rows[0].cells[0].paragraphs[0].runs[0].bold = True
            calc_table.rows[0].cells[1].paragraphs[0].runs[0].bold = True

            for row_idx, (criterion, data) in enumerate(matrix.items(), 1):
                calc_table.rows[row_idx].cells[
                    0
                ].text = f"{criterion} (max {data.get('weight', 0)})"
                calc_table.rows[row_idx].cells[1].text = "_____ / " + str(
                    data.get("weight", 0)
                )

            # Total row
            total_row = len(matrix) + 1
            calc_table.rows[total_row].cells[0].text = "TOTAL"
            calc_table.rows[total_row].cells[0].paragraphs[0].runs[0].bold = True
            calc_table.rows[total_row].cells[1].text = f"_____ / {eq.get('marks', 50)}"
            calc_table.rows[total_row].cells[1].paragraphs[0].runs[0].bold = True

    # ===== FOOTER =====
    doc.add_paragraph()
    doc.add_paragraph("_" * 60)
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run(f"TOTAL EXAM MARKS: {exam_data['total_marks']}").bold = True

    confidential = doc.add_paragraph()
    confidential.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = confidential.add_run("CONFIDENTIAL - FOR EXAMINER USE ONLY")
    run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
    run.bold = True

    # Save
    doc.save(str(output_path))
    return output_path


@app.post("/api/exams/generate")
async def generate_exam(request: ExamGenerationRequest):
    """Generate complete History exam papers (1st and 2nd opportunity) with memorandums."""

    print(f"[Exam Builder] Generating exam set for topics: {request.topics}")

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = {"first_opportunity": None, "second_opportunity": None}

        # Generate both opportunities
        for opp in [1, 2]:
            opp_label = "1st" if opp == 1 else "2nd"
            print(f"[Exam Builder] === Generating {opp_label} Opportunity Exam ===")

            exam_data = {
                "module_code": request.module_code,
                "module_name": request.module_name,
                "total_marks": request.total_marks,
                "duration_hours": request.duration_hours,
                "opportunity": opp,
                "opportunity_label": f"{opp_label} Opportunity",
                "source_questions": [],
                "methodology_question": None,
                "essay_question": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Generate source-based questions (2 x 25 marks each = 50 marks)
            marks_per_source_question = 25
            for i, topic in enumerate(request.topics[:2]):
                print(
                    f"[Exam Builder] {opp_label} Opp - Source question {i + 1}: {topic}"
                )

                # Generate sources (different for 2nd opportunity)
                sources_data = await generate_exam_sources(
                    topic, i + 1, opportunity=opp
                )
                sources = sources_data.get("sources", [])

                # Generate questions
                questions_data = await generate_source_questions(
                    sources, topic, marks_per_source_question
                )

                exam_data["source_questions"].append(
                    {
                        "question_number": i + 1,
                        "topic": topic,
                        "sources": sources,
                        "questions": questions_data.get("questions", []),
                        "total_marks": marks_per_source_question,
                    }
                )

            # Generate methodology question (25 marks) - same for both opportunities
            print(
                f"[Exam Builder] {opp_label} Opp - Methodology: {request.methodology_topic}"
            )
            exam_data["methodology_question"] = await generate_methodology_question(
                request.methodology_topic, marks=25
            )

            # Generate essay question (50 marks) - different for 2nd opportunity
            print(f"[Exam Builder] {opp_label} Opp - Essay: {request.essay_topic}")
            exam_data["essay_question"] = await generate_essay_question(
                request.essay_topic, marks=50, opportunity=opp
            )

            # Calculate actual total
            actual_total = sum(
                sq.get("total_marks", 0) for sq in exam_data["source_questions"]
            )
            actual_total += (
                exam_data["methodology_question"].get("marks", 0)
                if exam_data["methodology_question"]
                else 0
            )
            actual_total += (
                exam_data["essay_question"].get("marks", 0)
                if exam_data["essay_question"]
                else 0
            )
            exam_data["calculated_total"] = actual_total

            # Generate DOCX files
            opp_suffix = "1stOpp" if opp == 1 else "2ndOpp"

            # Exam paper
            filename = f"{request.module_code}_Exam_{opp_suffix}_{timestamp}.docx"
            output_path = OUTPUT_DIR / filename
            create_exam_docx(exam_data, output_path)
            exam_data["filename"] = filename

            # Memorandum
            memo_filename = f"{request.module_code}_Memo_{opp_suffix}_{timestamp}.docx"
            memo_path = OUTPUT_DIR / memo_filename
            create_memorandum_docx(exam_data, memo_path)
            exam_data["memo_filename"] = memo_filename

            print(
                f"[Exam Builder] Generated {opp_label} Opp: {filename}, {memo_filename}"
            )

            # Store result
            if opp == 1:
                results["first_opportunity"] = exam_data
            else:
                results["second_opportunity"] = exam_data

        # Store in database as a single record with both opportunities
        exam_record = {
            "module_code": request.module_code,
            "module_name": request.module_name,
            "total_marks": request.total_marks,
            "duration_hours": request.duration_hours,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "first_opportunity": results["first_opportunity"],
            "second_opportunity": results["second_opportunity"],
            # Legacy fields for backwards compatibility
            "filename": results["first_opportunity"]["filename"],
            "memo_filename": results["first_opportunity"]["memo_filename"],
            "calculated_total": results["first_opportunity"]["calculated_total"],
        }
        result = db["exams"].insert_one(exam_record)

        return {
            "success": True,
            "exam": {
                "_id": str(result.inserted_id),
                "module_code": request.module_code,
                "module_name": request.module_name,
                "total_marks": request.total_marks,
                "calculated_total": results["first_opportunity"]["calculated_total"],
                "duration_hours": request.duration_hours,
                "created_at": exam_record["created_at"],
                "first_opportunity": {
                    "filename": results["first_opportunity"]["filename"],
                    "memo_filename": results["first_opportunity"]["memo_filename"],
                    "source_questions": results["first_opportunity"][
                        "source_questions"
                    ],
                    "methodology_question": results["first_opportunity"][
                        "methodology_question"
                    ],
                    "essay_question": results["first_opportunity"]["essay_question"],
                },
                "second_opportunity": {
                    "filename": results["second_opportunity"]["filename"],
                    "memo_filename": results["second_opportunity"]["memo_filename"],
                    "source_questions": results["second_opportunity"][
                        "source_questions"
                    ],
                    "methodology_question": results["second_opportunity"][
                        "methodology_question"
                    ],
                    "essay_question": results["second_opportunity"]["essay_question"],
                },
            },
        }

    except Exception as e:
        print(f"[Exam Generation Error] {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/exams/download/{filename}")
async def download_exam(filename: str):
    """Download a generated exam paper."""
    file_path = OUTPUT_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Exam file not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/exams")
async def list_exams():
    """List all generated exams."""
    exams = list(db["exams"].find().sort("created_at", -1).limit(20))
    for exam in exams:
        exam["_id"] = str(exam["_id"])
    return {"exams": exams}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3001)
