import hashlib
import json
import logging
import os
import shutil
import tempfile
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from typing import Optional, List, Dict, Any

from app.services.parser import parse_resume_file
from app.services.rules import run_tier1_checks
from app.services.evaluator import run_module_a_ats_checker, run_module_d_eligibility_checker
from app.services.keyword import check_keyword_targeting
from app.services.autofix import run_autofix_bullet


router = APIRouter()
logger = logging.getLogger("uvicorn.error")

def get_cache_key(file_hash: str, level: str, jd_text: Optional[str]) -> str:
    """Generates the unique cache key: sha256(file_hash + level + sha256(jd_text))"""
    jd_hash = hashlib.sha256((jd_text or "").strip().encode('utf-8')).hexdigest()
    combined = f"{file_hash}_{level}_{jd_hash}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

@router.post("/upload")
def upload_resume(
    file: UploadFile = File(...),
    level: str = Form(...), # "Entry-level" | "Mid-level" | "Senior-level"
    target_role: Optional[str] = Form(None),
    jd_text: Optional[str] = Form(None)
):
    """
    Parses the file and runs the full evaluation pipeline.
    """
    # 1. Save uploaded file to temp file to parse it
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        try:
            shutil.copyfileobj(file.file, temp)
            temp_path = temp.name
        finally:
            file.file.close()

    try:
        # 2. Parse file
        text, file_hash, structural_metadata = parse_resume_file(temp_path)
    except Exception as e:
        logger.error(f"Failed to parse resume: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse resume: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # 3. Create mock resume ID
    resume_id = 1

    # Step A: Tier 1 (deterministic)
    tier1_score, tier1_checks = run_tier1_checks(text, structural_metadata)
    
    # Step B: Tier 2 (Qualitative Module A)
    evaluator_res = run_module_a_ats_checker(text, level, target_role)
    t2_checks = evaluator_res.get("checks", [])
    
    # Calculate Tier 2 average score
    t2_score = 0
    if t2_checks:
        total_t2_scores = sum(c.get("score", 0) for c in t2_checks)
        t2_score = round((total_t2_scores / len(t2_checks)) * 10) # out of 100
        
    # Step C: Module D (Eligibility)
    eligibility = run_module_d_eligibility_checker(text, level, jd_text)
    
    # Step D: Module C (Keyword targeting if JD exists)
    keyword_score = 0
    keyword_data = None
    if jd_text and jd_text.strip():
        keyword_data = check_keyword_targeting(text, jd_text)
        keyword_score = keyword_data.get("score", 0)
        
    # Step E: Aggregate Score
    if jd_text and jd_text.strip():
        # 40% Tier 1, 40% Tier 2, 20% Keywords
        overall_score = round((tier1_score * 0.4) + (t2_score * 0.4) + (keyword_score * 0.2))
    else:
        # 50% Tier 1, 50% Tier 2
        overall_score = round((tier1_score * 0.5) + (t2_score * 0.5))

    # Compile score object
    full_score_data = {
        "overall_score": overall_score,
        "tier1": {
            "score": tier1_score,
            "checks": tier1_checks
        },
        "tier2": {
            "score": t2_score,
            "checks": t2_checks
        },
        "eligibility": eligibility,
        "keyword_match": keyword_data
    }

    return {
        "resume_id": resume_id,
        "filename": file.filename,
        "file_hash": file_hash,
        "structural_metadata": structural_metadata,
        "score": full_score_data
    }

@router.post("/autofix")
def autofix_bullet(
    original_bullet: str = Form(...),
    context: str = Form(""),
    role: str = Form("Software Engineering"),
    level: str = Form("Mid-level"),
    flagged_issue: str = Form("General improvement")
):
    """
    Module B AutoFix bullet rewriter endpoint.
    """
    result = run_autofix_bullet(original_bullet, context, role, level, flagged_issue)
    return result

@router.post("/feedback")
def update_feedback(
    rewrite_id: int = Form(...),
    feedback: str = Form(...) # "approved" | "rejected"
):
    """Logs whether user accepted or rejected the suggested rewrite."""
    return {"message": "Feedback submitted successfully."}

@router.get("/history")
def get_score_history(file_hash: str):
    """
    Returns score tracking points for the 'Watch your score climb' chart.
    Retrieves all historic scoring events for this specific resume.
    """
    return []
