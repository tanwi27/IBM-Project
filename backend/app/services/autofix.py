import logging
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.db.models import BulletLibrary, BulletRewrite
from app.core.llm import generate_llm_json, generate_embeddings
from app.services.keyword import compute_cosine_similarity

logger = logging.getLogger("uvicorn.error")

def get_style_references(db: Session, original_bullet: str, role: str, level: str) -> List[str]:
    """
    RAG lookup: Finds 3 nearest-neighbor bullets in our database for style reference.
    Filters by role and level, then ranks by embedding cosine similarity.
    """
    # Fallback default bullets if DB is empty
    default_refs = {
        "Entry-level": [
            "Developed responsive front-end components using React, reducing page load times by 15% across 4 primary customer dashboards.",
            "Collaborated in an Agile team of 5 to design and test RESTful APIs, resolving 20+ blocking bugs during beta cycles.",
            "Analyzed weekly user engagement metrics in Excel, presenting actionable reports that drove a 5% increase in feature discovery."
        ],
        "Mid-level": [
            "Spearheaded migration of legacy payment system to microservices architecture, increasing transaction throughput by 40%.",
            "Led a cross-functional squad to ship a new analytics dashboard, capturing $150K in additional annual recurring revenue.",
            "Refactored relational database schemas and optimized indexing queries, decreasing average response time from 350ms to 90ms."
        ],
        "Senior-level": [
            "Architected cloud infrastructure migration for enterprise CRM platform, saving $1.2M in annual hosting costs while maintaining 99.99% uptime.",
            "Mentored and scaled a high-performing engineering team of 12 from onboarding to delivery, boosting sprint velocity by 25%.",
            "Defined technical vision and engineering roadmap for core data pipeline, scaling ingestion capacity to process 5B+ daily events."
        ]
    }
    
    try:
        # Retrieve candidate items from DB matching role or level
        # If pgvector was present we could do vector distance in DB, but a local fallback query is highly portable
        candidates = db.query(BulletLibrary).filter(
            BulletLibrary.level == level
        ).all()
        
        if not candidates:
            # Try to match just by level
            candidates = db.query(BulletLibrary).filter(BulletLibrary.level == level).all()
            
        if not candidates:
            return default_refs.get(level, default_refs["Mid-level"])
            
        # Generate embedding for the query bullet
        query_embedding = generate_embeddings([original_bullet])[0]
        
        # Rank by cosine similarity
        scored_candidates = []
        for cand in candidates:
            cand_emb = cand.embedding
            if isinstance(cand_emb, str):
                import json
                cand_emb = json.loads(cand_emb)
            sim = compute_cosine_similarity(query_embedding, cand_emb)
            scored_candidates.append((sim, cand.bullet_text))
            
        # Sort descending by similarity
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Return top 3
        refs = [item[1] for item in scored_candidates[:3]]
        # Ensure we have at least 3
        while len(refs) < 3 and len(default_refs[level]) > len(refs):
            refs.append(default_refs[level][len(refs)])
            
        return refs
    except Exception as e:
        logger.error(f"Error retrieving style references: {e}")
        return default_refs.get(level, default_refs["Mid-level"])


def run_autofix_bullet(db: Session, original_bullet: str, context: str, role: str, level: str, flagged_issue: str) -> Dict[str, Any]:
    """
    Module B: AutoFix Agent
    Rewrites a single bullet using the RAG style library context.
    """
    # 1. Retrieve style references
    style_refs = get_style_references(db, original_bullet, role, level)
    
    # 2. Formulate Prompt
    system_prompt = """You rewrite ONE resume bullet at a time. You are not a creative writer — you
are an editor who makes the candidate's own experience read the way a strong
resume would state it. You NEVER invent facts, numbers, tools, or outcomes
that are not in the original bullet or the supporting context provided.

Style References to mimic:
1. {style_ref_1}
2. {style_ref_2}
3. {style_ref_3}

Rules:
1. If the original bullet contains a number, outcome, or scale — keep it, do
   not change the magnitude.
2. If it does NOT contain a quantifiable outcome, do NOT fabricate one. Instead
   sharpen the verb and specificity, and flag in "note" that the candidate
   should add a real number if one exists.
3. Preserve every factual claim (tools, team size, company, timeframe) exactly.
4. One rewrite suggestion per bullet — not multiple options. The user compares
   original vs. rewrite and approves or rejects; don't make them choose among
   several.
5. Output ONLY JSON, no prose outside it.

Output schema:
{
  "original": "<unchanged input>",
  "rewrite": "<new bullet text>",
  "changed_because": "<1 sentence tied to flagged_issue>",
  "note": "<optional — e.g. 'add a real metric here if you have one'>"
}"""

    # Format prompt elements
    system_prompt_formatted = system_prompt.format(
        style_ref_1=style_refs[0] if len(style_refs) > 0 else "",
        style_ref_2=style_refs[1] if len(style_refs) > 1 else "",
        style_ref_3=style_refs[2] if len(style_refs) > 2 else ""
    )

    user_prompt = f"""Input:
- original_bullet: {original_bullet}
- context: {context}
- level: {level}
- flagged_issue: {flagged_issue}"""

    # Mock fallback if LLM is offline/keyless
    mock_rewrite = {
        "original": original_bullet,
        "rewrite": original_bullet,
        "changed_because": f"Addressed issue: {flagged_issue}",
        "note": "Review your bullet to add numbers, percentages, or dollar values if available."
    }
    
    # Try to make a basic rule-based rewrite for mock to look good
    if "responsible for" in original_bullet.lower():
        # Strip "responsible for" and capitalize verb
        cleaned = re.sub(r'^(?:\b(?:i was )?responsible for\b\s*)', '', original_bullet, flags=re.IGNORECASE)
        # If starts with a verb ending in -ing, change to past tense
        words = cleaned.split()
        if words:
            first_word = words[0]
            if first_word.endswith("ing"):
                # Simple replacement rule for common verbs
                verb_mapping = {"managing": "Managed", "building": "Built", "designing": "Designed", "leading": "Led", "improving": "Improved", "creating": "Created", "developing": "Developed"}
                words[0] = verb_mapping.get(first_word.lower(), first_word.capitalize())
            else:
                words[0] = first_word.capitalize()
            mock_rewrite["rewrite"] = " ".join(words)
            mock_rewrite["changed_because"] = "Replaced weak passive opener 'responsible for' with a strong active verb."
            mock_rewrite["note"] = "Consider adding a metric here (e.g. team size or systems delivered) to show the scale of your responsibility."
            
    # Call LLM
    result = generate_llm_json(system_prompt_formatted, user_prompt, mock_rewrite)
    
    # Record rewrite history for "Watch your score climb" / AutoFix audit
    try:
        rewrite_log = BulletRewrite(
            original_bullet=original_bullet,
            rewritten_bullet=result.get("rewrite", original_bullet),
            changed_because=result.get("changed_because", ""),
            note=result.get("note", ""),
            feedback="pending"
        )
        db.add(rewrite_log)
        db.commit()
        db.refresh(rewrite_log)
        result["rewrite_id"] = rewrite_log.id
    except Exception as e:
        logger.error(f"Error logging rewrite: {e}")
        db.rollback()
        
    return result
