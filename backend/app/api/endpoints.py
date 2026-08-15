import hashlib
import json
import logging
import os
import shutil
import tempfile
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from app.db.session import get_db
from app.db.models import Resume, Score, BulletRewrite
from app.services.parser import parse_resume_file
from app.services.rules import run_tier1_checks
from app.services.evaluator import run_module_a_ats_checker, run_module_d_eligibility_checker
from app.services.keyword import check_keyword_targeting
from app.services.autofix import run_autofix_bullet
from app.services.seed import seed_bullet_library

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
    jd_text: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Parses the file, computes its hash, checks the database cache,
    and runs the full evaluation pipeline if not cached.
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

    # 3. Create or get Resume record
    resume = db.query(Resume).filter(Resume.file_hash == file_hash).first()
    if not resume:
        resume = Resume(
            filename=file.filename,
            file_hash=file_hash,
            text=text,
            structural_metadata=structural_metadata
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)

    # 4. Check score cache
    cache_key = get_cache_key(file_hash, level, jd_text)
    cached_score = db.query(Score).filter(Score.cache_key == cache_key).first()
    
    if cached_score:
        logger.info("Serving score from cache.")
        return {
            "resume_id": resume.id,
            "filename": resume.filename,
            "file_hash": resume.file_hash,
            "structural_metadata": resume.structural_metadata,
            "score": cached_score.score_data
        }

    # 5. Run full pipeline if not cached
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

    # Save score to cache database
    new_score = Score(
        resume_id=resume.id,
        level=level,
        target_role=target_role,
        jd_text=jd_text,
        cache_key=cache_key,
        score_data=full_score_data
    )
    db.add(new_score)
    db.commit()
    
    return {
        "resume_id": resume.id,
        "filename": resume.filename,
        "file_hash": resume.file_hash,
        "structural_metadata": resume.structural_metadata,
        "score": full_score_data
    }

@router.post("/autofix")
def autofix_bullet(
    original_bullet: str = Form(...),
    context: str = Form(""),
    role: str = Form("Software Engineering"),
    level: str = Form("Mid-level"),
    flagged_issue: str = Form("General improvement"),
    db: Session = Depends(get_db)
):
    """
    Module B AutoFix bullet rewriter endpoint.
    Retrieves semantic references from seed bullet library and submits it to LLM rewriter.
    """
    result = run_autofix_bullet(db, original_bullet, context, role, level, flagged_issue)
    return result

@router.post("/feedback")
def update_feedback(
    rewrite_id: int = Form(...),
    feedback: str = Form(...), # "approved" | "rejected"
    db: Session = Depends(get_db)
):
    """Logs whether user accepted or rejected the suggested rewrite."""
    log = db.query(BulletRewrite).filter(BulletRewrite.id == rewrite_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Rewrite log entry not found.")
    
    log.feedback = feedback
    db.commit()
    return {"message": "Feedback submitted successfully."}

@router.get("/history")
def get_score_history(
    file_hash: str,
    db: Session = Depends(get_db)
):
    """
    Returns score tracking points for the 'Watch your score climb' chart.
    Retrieves all historic scoring events for this specific resume.
    """
    resume = db.query(Resume).filter(Resume.file_hash == file_hash).first()
    if not resume:
        return []
        
    scores = db.query(Score).filter(Score.resume_id == resume.id).order_by(Score.created_at.asc()).all()
    
    history = []
    for s in scores:
        history.append({
            "score_id": s.id,
            "overall_score": s.score_data.get("overall_score", 0),
            "level": s.level,
            "target_role": s.target_role,
            "date": s.created_at.strftime("%Y-%m-%d %H:%M")
        })
        
    return history

@router.post("/seed-db")
def seed_database_vector_library(db: Session = Depends(get_db)):
    """Triggers the seeding of the 150+ vector-enabled style library manually."""
    seed_bullet_library(db)
    return {"message": "Database seeder run successfully."}
