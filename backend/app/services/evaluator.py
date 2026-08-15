import re
from typing import Dict, Any, Optional
from app.core.llm import generate_llm_json

def run_module_a_ats_checker(resume_text: str, level: str, target_role: Optional[str] = None) -> Dict[str, Any]:
    """
    Module A: ATS Score Checker (Tier 2 / Qualitative)
    Evaluates 10 qualitative dimensions of resume content.
    """
    target_role_str = target_role or "general"
    
    system_prompt = f"""You are a deterministic resume-quality evaluator. You do not check formatting,
file structure, or keyword presence — those are handled elsewhere. You ONLY
evaluate the 10 qualitative checks below. Score each 0-10. Do not average or
invent an overall score; the caller aggregates.

Checks:
1. achievement_vs_duty — bullets state outcomes, not just responsibilities
2. quantification_quality — numbers present are meaningful, not vague ("many")
3. specificity — avoids generic filler ("hardworking team player")
4. impact_clarity — reader understands what changed because of this person
5. seniority_alignment — language matches the candidate's stated level: {level}
6. action_verb_strength — verbs are strong and varied, not repeated/weak
7. narrative_coherence — resume tells a consistent career story
8. role_relevance — content emphasizes what matters for: {target_role_str}
9. conciseness — bullets are tight, no filler phrases
10. red_flags — unexplained gaps, inconsistent titles, first-person pronouns

Rules:
- Base every score ONLY on text explicitly present in the resume. Never assume
  unstated achievements or infer numbers.
- For each check scoring below 7, return one concrete, actionable reason tied
  to a specific line — not general advice.
- Output ONLY valid JSON matching the schema. No prose, no markdown fences.

Output schema:
{{
  "checks": [
    {{"id": "achievement_vs_duty", "score": 0-10, "issues": [{{"line": "<quoted line>", "reason": "<specific>"}}]}},
    ... (all 10 checks)
  ]
}}"""

    user_prompt = f"""Input:
Resume text: {resume_text}
Candidate level: {level}
Target role (if any): {target_role_str}"""

    # Structured mock data to return as fallback if LLM is unavailable
    mock_fallback = {
        "checks": [
            {
                "id": "achievement_vs_duty",
                "score": 6,
                "issues": [{"line": "Responsible for managing a team of software developers.", "reason": "States a duty rather than an achievement. Describe what the team built and the business outcome."}]
            },
            {
                "id": "quantification_quality",
                "score": 5,
                "issues": [{"line": "Improved website performance significantly.", "reason": "Contains vague improvement ('significantly'). Quantify with exact page load times or percentages."}]
            },
            {
                "id": "specificity",
                "score": 7,
                "issues": []
            },
            {
                "id": "impact_clarity",
                "score": 6,
                "issues": [{"line": "Wrote backend microservices in Go.", "reason": "Unclear what impact these microservices had on the overall system or users."}]
            },
            {
                "id": "seniority_alignment",
                "score": 8,
                "issues": []
            },
            {
                "id": "action_verb_strength",
                "score": 8,
                "issues": []
            },
            {
                "id": "narrative_coherence",
                "score": 7,
                "issues": []
            },
            {
                "id": "role_relevance",
                "score": 8,
                "issues": []
            },
            {
                "id": "conciseness",
                "score": 9,
                "issues": []
            },
            {
                "id": "red_flags",
                "score": 9,
                "issues": []
            }
        ]
    }
    
    return generate_llm_json(system_prompt, user_prompt, mock_fallback)


def run_module_d_eligibility_checker(resume_text: str, level: str, jd_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Module D: Role & Level Eligibility Checker
    Validates work duration, seniority signals, and domain alignment.
    """
    jd_text_str = jd_text or "No Job Description Provided"
    
    system_prompt = """You assess whether a resume's actual content supports the candidate's
selected experience level and, if a job description is provided, the target
role — and where it doesn't, you say so plainly and specifically.

You are not gatekeeping the candidate from using the product. You are giving
them an honest signal, the same way a recruiter's first 6-second scan would.

Input:
- resume_text: {resume_text}
- selected_level: {level}  // Entry-level / Mid-level / Senior-level
- target_jd: {jd_text_or_null}

Evaluate:
1. years_alignment — does total work history (internships count for
   Entry-level; full-time roles count more for Mid/Senior) roughly match
   the selected band? Entry: <2 yrs. Mid: 2-10 yrs. Senior: 10+ yrs.
2. seniority_signal_alignment — does the resume show the KIND of impact
   expected at that level (Entry: projects/coursework/internships fine;
   Mid: independent ownership of workstreams; Senior: leading others,
   strategy, org-level impact)? A resume can have the right years but read
   junior, or vice versa.
3. IF target_jd provided — domain_fit: does the candidate's skill set and
   experience domain plausibly match what the JD is asking for? Flag a
   clear mismatch (e.g. resume is finance-analyst but JD is backend
   engineering) rather than silently scoring it like a normal application.

Do NOT reject or refuse to score a mismatched resume — always still produce
Modules A/B/C output. This module only adds a clear, honest flag so the user
isn't optimizing a resume for the wrong target.

Output ONLY JSON:
{
  "level_match": "match" | "underqualified_for_selection" | "overqualified_for_selection",
  "level_reason": "<specific, e.g. 'resume shows 1 internship, 0 full-time roles — reads as Entry-level, not Mid'>",
  "role_fit": "match" | "partial" | "mismatch" | "no_jd_provided",
  "role_fit_reason": "<specific evidence, or null>"
}"""

    user_prompt = f"""Input:
- resume_text: {resume_text}
- selected_level: {level}
- target_jd: {jd_text_str}"""

    # Mock fallback data for eligibility checker
    mock_fallback = {
        "level_match": "match",
        "level_reason": "Total visible experience is ~4 years, which fits within the 2-10 years band for Mid-level.",
        "role_fit": "match" if jd_text else "no_jd_provided",
        "role_fit_reason": "The candidate has experience with React and Node.js which aligns with the Frontend Developer role requested." if jd_text else None
    }
    
    # Try to make a basic rule-based inference for mock if offline, to be slightly smarter
    words = resume_text.lower().split()
    word_count = len(words)
    
    # Basic heuristics for the mock fallback
    if word_count > 100:
        # Check years of experience
        years_matches = re.findall(r'\b(19\d{2}|20\d{2})\b', resume_text)
        if len(years_matches) >= 2:
            years = [int(y) for y in years_matches]
            span = max(years) - min(years)
            
            if level == "Senior-level" and span < 6:
                mock_fallback["level_match"] = "underqualified_for_selection"
                mock_fallback["level_reason"] = f"Resume shows a historical span of {span} years. This is under the 10+ year typical threshold for Senior-level positions."
            elif level == "Entry-level" and span > 3:
                mock_fallback["level_match"] = "overqualified_for_selection"
                mock_fallback["level_reason"] = f"Resume shows {span} years of timeline. You may be overqualified for Entry-level, consider targeting Mid-level."
                
    return generate_llm_json(system_prompt, user_prompt, mock_fallback)
