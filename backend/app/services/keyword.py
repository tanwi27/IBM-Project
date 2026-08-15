import math
import re
from typing import List, Dict, Any, Optional, Tuple
from app.core.llm import generate_llm_json, generate_embeddings

# A rich, cross-industry gazetteer of standard professional skills, tools, frameworks, and domains.
SKILLS_GAZETTEER = {
    # Tech / Engineering
    "python", "javascript", "typescript", "c++", "java", "golang", "rust", "ruby", "php", "swift", "kotlin",
    "react", "angular", "vue", "next.js", "node.js", "django", "fastapi", "flask", "spring boot", "laravel",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "sqlite", "oracle", "cassandra", "dynamodb",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible", "jenkins", "git", "ci/cd", "github",
    "html", "css", "sass", "tailwind", "graphql", "rest api", "soap", "microservices", "serverless",
    "machine learning", "deep learning", "nlp", "computer vision", "pytorch", "tensorflow", "scikit-learn",
    "pandas", "numpy", "spark", "hadoop", "tableau", "power bi", "data warehousing", "sql", "nosql",
    
    # PM / Agile
    "scrum", "agile", "kanban", "jira", "confluence", "product roadmap", "wireframing", "prototyping",
    "user stories", "market research", "ab testing", "product lifecycle", "prd", "stakeholder management",
    
    # Marketing / Sales
    "seo", "sem", "google analytics", "hubspot", "salesforce", "content marketing", "copywriting",
    "email marketing", "social media marketing", "lead generation", "crm", "funnel optimization",
    
    # Finance / Business
    "financial modeling", "accounting", "excel", "valuation", "risk assessment", "budgeting",
    "forecasting", "m&a", "portfolio management", "sap", "audit", "compliance", "strategic planning",
    
    # Design
    "figma", "sketch", "adobe photoshop", "illustrator", "adobe xd", "ui/ux", "user research",
    "wireframes", "interaction design", "visual design", "typography"
}

def extract_keywords_from_jd(jd_text: str) -> List[Tuple[str, str]]:
    """
    Deterministically extracts keywords (skills and noun phrases) from the job description.
    Returns a list of tuples: (keyword, surrounding_sentence).
    """
    extracted = []
    seen = set()
    
    # Split text into sentences for context
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', jd_text)
    
    for sentence in sentences:
        clean_sentence = sentence.strip()
        if not clean_sentence:
            continue
            
        # 1. Gazetteer lookup (case-insensitive word boundary match)
        # Look for standard terms
        sentence_lower = clean_sentence.lower()
        for skill in SKILLS_GAZETTEER:
            pattern = rf'\b{re.escape(skill)}\b'
            if re.search(pattern, sentence_lower):
                if skill not in seen:
                    seen.add(skill)
                    extracted.append((skill, clean_sentence))
                    
        # 2. Extract title/important capitalized phrases (e.g. "React Native", "Google Analytics")
        # To avoid adding common words, verify they aren't starting sentences or lowercase.
        capitalized_phrases = re.findall(r'\b[A-Z][a-zA-Z0-9\+#\.]+(?:\s+[A-Z][a-zA-Z0-9\+#\.]+)*\b', clean_sentence)
        for phrase in capitalized_phrases:
            phrase_lower = phrase.lower()
            if phrase_lower not in seen and len(phrase) > 2:
                # Basic check: do not add common sentence starters like "The", "We", "This", "Candidate"
                if phrase in ["The", "We", "This", "You", "Our", "Candidate", "Role", "Job", "Requirements", "Responsibilities"]:
                    continue
                seen.add(phrase_lower)
                extracted.append((phrase, clean_sentence))

    # Keep a maximum of 25 keywords to prevent heavy LLM and embedding overhead
    return extracted[:25]

def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes the dot product of two vectors (assuming they are normalized)."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    return dot_product

def check_keyword_targeting(resume_text: str, jd_text: str) -> Dict[str, Any]:
    """
    Module C: Keyword Targeting Scanner
    Performs keyword extraction, weights importance, embeds segments, and measures similarity.
    """
    # 1. Extract keywords from JD
    jd_keywords_with_context = extract_keywords_from_jd(jd_text)
    if not jd_keywords_with_context:
        return {
            "score": 100,
            "matched_keywords": [],
            "missing_keywords": [],
            "details": "No distinct keywords extracted from the job description."
        }
        
    jd_keywords = [kw[0] for kw in jd_keywords_with_context]
    
    # 2. Weight keywords using LLM (Module C Step 4)
    system_prompt = """You rank job-posting keywords by how much a screener would weight them.
Signals: repeated in JD, appears in title/first paragraph ("must-have"
section), is a hard skill/tool vs. soft trait.
Input: list of extracted keywords + surrounding JD sentence for each.
Output ONLY JSON: [{"keyword": "...", "weight": 0-1, "why": "<one clause>"}]
Do not add keywords not in the input list. Do not judge the resume here."""

    formatted_input = "\n".join([f"- Keyword: {kw}\n  Context: {ctx}" for kw, ctx in jd_keywords_with_context])
    user_prompt = f"Keywords to weight:\n{formatted_input}"
    
    # Fallback weights
    fallback_weights = []
    for kw in jd_keywords:
        # Simple heuristic: longer or tech terms get higher default weights
        weight = 0.8 if kw.lower() in SKILLS_GAZETTEER else 0.5
        fallback_weights.append({
            "keyword": kw,
            "weight": weight,
            "why": "Identified as a critical skill" if kw.lower() in SKILLS_GAZETTEER else "Related context keyword"
        })
        
    weighter_result = generate_llm_json(system_prompt, user_prompt, fallback_weights)
    
    # Map weights by keyword name (case-insensitive)
    weights_map = {}
    if isinstance(weighter_result, list):
        for item in weighter_result:
            if "keyword" in item and "weight" in item:
                weights_map[item["keyword"].lower()] = {
                    "weight": float(item["weight"]),
                    "why": item.get("why", "")
                }
    else:
        # If dict format returned
        items = weighter_result.get("keywords", weighter_result.get("weights", []))
        for item in items:
            if isinstance(item, dict) and "keyword" in item:
                weights_map[item["keyword"].lower()] = {
                    "weight": float(item.get("weight", 0.5)),
                    "why": item.get("why", "")
                }

    # Ensure all extracted keywords have a entry in weights_map
    for kw in jd_keywords:
        kw_l = kw.lower()
        if kw_l not in weights_map:
            weights_map[kw_l] = {"weight": 0.6, "why": "Extracted keyword"}

    # 3. Extract resume phrases (split by sentences/lines)
    resume_phrases = [p.strip() for p in re.split(r'[\n\.]', resume_text) if p.strip()]
    if not resume_phrases:
        resume_phrases = [resume_text]
        
    # 4. Generate embeddings
    # Embed JD keywords
    kw_embeddings = generate_embeddings(jd_keywords)
    # Embed Resume phrases
    phrase_embeddings = generate_embeddings(resume_phrases)
    
    matched_keywords = []
    missing_keywords = []
    
    # 5. Cosine similarity matching
    # Threshold = 0.82
    SIMILARITY_THRESHOLD = 0.82
    
    for i, kw in enumerate(jd_keywords):
        kw_l = kw.lower()
        kw_emb = kw_embeddings[i]
        
        best_similarity = 0.0
        best_matching_phrase = ""
        
        # Compare against all resume phrases
        for j, phrase in enumerate(resume_phrases):
            phrase_emb = phrase_embeddings[j]
            sim = compute_cosine_similarity(kw_emb, phrase_emb)
            if sim > best_similarity:
                best_similarity = sim
                best_matching_phrase = phrase
                
        weight_info = weights_map.get(kw_l, {"weight": 0.5, "why": ""})
        weight = weight_info["weight"]
        why = weight_info["why"]
        
        kw_report = {
            "keyword": kw,
            "weight": weight,
            "why": why,
            "similarity": round(best_similarity, 3)
        }
        
        if best_similarity >= SIMILARITY_THRESHOLD:
            kw_report["matched_in_resume"] = best_matching_phrase
            matched_keywords.append(kw_report)
        else:
            missing_keywords.append(kw_report)
            
    # 6. Combine score: matched/missing × weight
    # Score calculation formula:
    # (Sum of weights of matched keywords / Total weights of all keywords) * 100
    total_weights = sum(item["weight"] for item in matched_keywords) + sum(item["weight"] for item in missing_keywords)
    matched_weights = sum(item["weight"] for item in matched_keywords)
    
    score = 100
    if total_weights > 0:
        score = round((matched_weights / total_weights) * 100)
        
    # Sort missing by weight descending so we present the most critical missing ones first
    missing_keywords.sort(key=lambda x: x["weight"], reverse=True)
    matched_keywords.sort(key=lambda x: x["weight"], reverse=True)
    
    return {
        "score": score,
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords
    }
