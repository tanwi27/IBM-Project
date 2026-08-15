import re
import spacy
from typing import Dict, List, Any, Tuple

# Load spaCy English model (we will ensure en_core_web_sm is loaded)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Fallback to loading it if download hasn't finished, or just simple split
    nlp = None

BUZZWORDS = [
    "synergy", "go-getter", "team player", "detail-oriented", "hardworking",
    "proven track record", "results-oriented", "passionate", "self-motivated",
    "dynamic", "think outside the box", "leverage", "bottom-line", "value-add",
    "proactive", "motivated", "enthusiastic", "fast learner", "expert"
]

COMMON_HEADERS = {
    "work_experience": ["work experience", "experience", "professional experience", "employment history", "work history", "career history"],
    "education": ["education", "academic history", "academic background", "credentials"],
    "skills": ["skills", "technical skills", "areas of expertise", "core competencies", "technologies"],
    "projects": ["projects", "personal projects", "academic projects", "key projects"],
    "summary": ["summary", "professional summary", "about me", "profile", "objective", "career objective"]
}

def load_spacy_doc(text: str):
    if nlp is not None:
        # Increase max_length just in case of giant text
        return nlp(text[:100000])
    return None

def check_contact_info(text: str) -> Tuple[int, List[Dict[str, str]]]:
    """Checks for contact details (Email, Phone, LinkedIn, Website)."""
    issues = []
    
    email_re = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    phone_re = re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
    linkedin_re = re.compile(r'linkedin\.com/in/[a-zA-Z0-9-_]+', re.IGNORECASE)
    url_re = re.compile(r'(https?://)?(www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(/[a-zA-Z0-9-_#]+)?')

    has_email = bool(email_re.search(text))
    has_phone = bool(phone_re.search(text))
    has_linkedin = bool(linkedin_re.search(text))
    
    # Portfolio/GitHub or personal site
    has_portfolio = False
    urls = url_re.finditer(text)
    for url in urls:
        url_str = url.group(0).lower()
        if "linkedin.com" not in url_str and ("github.com" in url_str or "portfolio" in url_str or "personal" in url_str or "resume" not in url_str):
            has_portfolio = True
            break

    score = 10
    if not has_email:
        score -= 4
        issues.append({"message": "No email address detected. Recruiters cannot reach you.", "severity": "error"})
    if not has_phone:
        score -= 3
        issues.append({"message": "No phone number detected.", "severity": "warning"})
    if not has_linkedin:
        score -= 2
        issues.append({"message": "No LinkedIn profile URL detected. Over 85% of screeners verify profiles.", "severity": "warning"})
    if not has_portfolio:
        score -= 1
        issues.append({"message": "No portfolio or personal website link found. Adding links to GitHub/work examples increases response rate.", "severity": "info"})
        
    return max(0, score), issues

def check_section_headers(text: str) -> Tuple[int, List[Dict[str, str]]]:
    """Checks if standard section headers are present."""
    issues = []
    detected = {}
    text_lower = text.lower()
    
    for category, aliases in COMMON_HEADERS.items():
        found = False
        for alias in aliases:
            # Match aliases standing alone on a line to resemble headers
            pattern = rf'(?:^|\n)\s*{re.escape(alias)}\s*(?:\n|:|$)'
            if re.search(pattern, text_lower):
                found = True
                detected[category] = alias
                break
        if not found:
            detected[category] = None

    score = 10
    if not detected["work_experience"]:
        score -= 4
        issues.append({"message": "Could not identify a 'Work Experience' or 'Experience' section header. This breaks parser indexing.", "severity": "error"})
    if not detected["education"]:
        score -= 3
        issues.append({"message": "Could not identify an 'Education' section header.", "severity": "error"})
    if not detected["skills"]:
        score -= 2
        issues.append({"message": "Could not identify a 'Skills' section header.", "severity": "warning"})
    if not detected["summary"] and not detected["projects"]:
        score -= 1
        issues.append({"message": "Consider adding a 'Summary' or 'Projects' section header to separate sections.", "severity": "info"})
        
    return max(0, score), issues

def check_layout_compatibility(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluates columns, tables, text boxes, and images which break ATS parsers."""
    checks = []
    
    # 1. Tables check
    has_tables = metadata.get("has_tables", False)
    tables_count = metadata.get("tables_count", 0)
    checks.append({
        "id": "ats_tables",
        "name": "Tables Check",
        "score": 4 if has_tables else 10,
        "category": "Formatting",
        "passed": not has_tables,
        "issues": [{"message": f"Detected {tables_count} table(s). ATS parsers frequently scramble table cells into chaotic text.", "severity": "error"}] if has_tables else []
    })

    # 2. Columns check
    has_columns = metadata.get("has_columns", False)
    checks.append({
        "id": "ats_columns",
        "name": "Multi-Column Layout",
        "score": 3 if has_columns else 10,
        "category": "Formatting",
        "passed": not has_columns,
        "issues": [{"message": "Detected a multi-column or grid layout. Many ATS read left-to-right across the entire page, merging columns together.", "severity": "error"}] if has_columns else []
    })

    # 3. Text boxes check
    has_text_boxes = metadata.get("has_text_boxes", False)
    checks.append({
        "id": "ats_text_boxes",
        "name": "Text Boxes Check",
        "score": 5 if has_text_boxes else 10,
        "category": "Formatting",
        "passed": not has_text_boxes,
        "issues": [{"message": "Detected text boxes. Many ATS skip text stored in shapes/text-boxes entirely.", "severity": "error"}] if has_text_boxes else []
    })

    # 4. Images check
    has_images = metadata.get("has_images", False)
    images_count = metadata.get("images_count", 0)
    checks.append({
        "id": "ats_images",
        "name": "Images / Graphics Check",
        "score": 5 if has_images else 10,
        "category": "Formatting",
        "passed": not has_images,
        "issues": [{"message": f"Detected {images_count} image(s) or graphics. ATS cannot read text in images, and pictures inflate file size.", "severity": "warning"}] if has_images else []
    })

    return checks

def check_date_consistency(text: str) -> Tuple[int, List[Dict[str, str]]]:
    """Checks if dates are structured consistently."""
    # Find all date-like spans: e.g. "09/2021", "Sept 2021", "September 2021", "2019 - 2022"
    slash_dates = re.findall(r'\b\d{1,2}/\d{2,4}\b', text)
    word_dates = re.findall(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b', text, re.IGNORECASE)
    year_only_dates = re.findall(r'\b[12]\d{3}\b', text)
    
    issues = []
    score = 10
    
    # Filter out years if they are part of word dates or slash dates to avoid double counts
    # But checking consistency between word dates (e.g. Sept 2021) and slash dates (e.g. 09/2021)
    if len(slash_dates) > 1 and len(word_dates) > 1:
        score = 5
        issues.append({"message": "Mixed date formats detected (e.g., '08/2021' and 'Aug 2021'). Use one consistent style.", "severity": "warning"})
    elif len(slash_dates) == 0 and len(word_dates) == 0 and len(year_only_dates) < 2:
        score = 6
        issues.append({"message": "Few or no job dates detected. Ensure your work history contains clear start and end dates.", "severity": "warning"})
        
    return score, issues

def check_bullet_consistency(text: str) -> Tuple[int, List[Dict[str, str]]]:
    """Checks for standard bullet points."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    bullet_lines = 0
    non_std_bullets = 0
    
    std_bullet_chars = ('•', '▪', '-', '*', '◦', '▪', '♦', '–', '—')
    fancy_bullet_chars = ('➢', '➔', '✓', '✔', '★', '▶', '●', '»')
    
    for line in lines:
        if line.startswith(std_bullet_chars):
            bullet_lines += 1
        elif line.startswith(fancy_bullet_chars):
            bullet_lines += 1
            non_std_bullets += 1
            
    score = 10
    issues = []
    if non_std_bullets > 0:
        score = 7
        issues.append({"message": "Detected non-standard, graphic bullet icons (e.g. arrows, checkmarks). These can render as empty rectangles or question marks in older ATS.", "severity": "warning"})
        
    if bullet_lines == 0:
        score = 4
        issues.append({"message": "No bulleted lists detected. Paragraph blocks of text are difficult for human screeners to scan in 6 seconds.", "severity": "error"})
        
    return score, issues

def check_quantification(text: str) -> Tuple[int, List[Dict[str, str]]]:
    """Checks for presence of metrics and numbers in bullet points."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    bullet_count = 0
    quantified_count = 0
    
    bullet_patterns = ('•', '▪', '-', '*', '◦', '▪', '♦', '–', '—', '➢', '➔', '✓', '✔', '★', '▶', '●', '»')
    
    # Regex to detect numbers representing metrics: percentages, dollar values, size counts, multiplier
    # Exclude years like 2020, 2021, 2022, 2023, 2024, 2025, 2026
    metric_re = re.compile(r'(?:\d+%\b|\$\d+|\b\d+\s*(?:million|billion|k|x|percent|times|users|employees|clients|students|projects|dollars)\b|\b\d+(?!\s*(?:19\d{2}|20\d{2}))[0-9,\.]+\b(?:%|\+|\b|s))', re.IGNORECASE)
    
    sample_issues = []
    
    for line in lines:
        if line.startswith(bullet_patterns):
            bullet_count += 1
            # Clean of bullet character for matching
            cleaned_line = re.sub(r'^[^a-zA-Z0-9]+', '', line).strip()
            if metric_re.search(cleaned_line):
                quantified_count += 1
            else:
                # Store sample lines that lack quantification
                if len(sample_issues) < 2 and len(cleaned_line) > 30:
                    sample_issues.append(cleaned_line)
                    
    score = 10
    issues = []
    
    if bullet_count > 0:
        ratio = quantified_count / bullet_count
        if ratio < 0.2:
            score = 3
            issues.append({"message": f"Only {quantified_count} of {bullet_count} bullets ({ratio:.0%}) contain measurable metrics. Aim for at least 40% quantification.", "severity": "error"})
        elif ratio < 0.4:
            score = 7
            issues.append({"message": f"Only {quantified_count} of {bullet_count} bullets ({ratio:.0%}) contain metrics. Bolster bullet impact with percentages, dollar values, or team size metrics.", "severity": "warning"})
    else:
        score = 0
        issues.append({"message": "No bullet points found to measure quantification.", "severity": "error"})
        
    for idx, sample in enumerate(sample_issues):
        issues.append({
            "message": f"Bullet lacking metrics: \"{sample[:70]}...\"",
            "severity": "info"
        })
        
    return score, issues

def check_buzzwords(text: str) -> Tuple[int, List[Dict[str, str]]]:
    """Detects overused clichés and buzzwords."""
    detected = []
    text_lower = text.lower()
    
    for word in BUZZWORDS:
        # Match as whole word
        pattern = rf'\b{re.escape(word)}\b'
        if re.search(pattern, text_lower):
            detected.append(word)
            
    score = 10
    issues = []
    if len(detected) > 0:
        score = max(2, 10 - len(detected))
        issues.append({
            "message": f"Detected {len(detected)} generic clichés / buzzwords: {', '.join(detected)}. Replace these with active verbs and objective metrics.",
            "severity": "warning"
        })
        
    return score, issues

def check_grammar_passive_voice(doc) -> Tuple[int, List[Dict[str, str]]]:
    """Detects passive voice sentences using spaCy parser."""
    issues = []
    passive_sents = []
    
    if doc is None:
        # spaCy failed to load, return pass
        return 10, []
        
    for sent in doc.sents:
        has_be = False
        has_vbn = False
        be_token = None
        
        for token in sent:
            # Check for form of auxiliary "be"
            if token.lemma_ in ["be", "is", "are", "was", "were", "been", "being", "am"]:
                has_be = True
                be_token = token
            # Check for past participle
            if token.tag_ == "VBN" and has_be:
                # If there's an auxiliary passive or head matches
                if token.dep_ == "passive" or token.head == be_token or any(t.dep_ == "auxpass" for t in token.children):
                    has_vbn = True
                    break
        
        if has_be and has_vbn:
            passive_sents.append(sent.text.strip())
            
    score = 10
    if len(passive_sents) > 0:
        score = max(4, 10 - len(passive_sents))
        issues.append({
            "message": f"Detected passive voice in {len(passive_sents)} sentences. Passive framing (e.g. 'Project was managed by me') reads weak. Use active verbs ('Managed project').",
            "severity": "warning"
        })
        # Add two samples
        for sent in passive_sents[:2]:
            issues.append({"message": f"Passive sentence: \"{sent[:80]}...\"", "severity": "info"})
            
    return score, issues

def check_first_person_pronouns(text: str) -> Tuple[int, List[Dict[str, str]]]:
    """Detects first-person pronouns which are red flags in resume writing."""
    pronouns = ["i", "me", "my", "myself", "we", "our", "us", "ourselves"]
    detected = []
    text_lower = text.lower()
    
    for p in pronouns:
        pattern = rf'\b{p}\b'
        if re.search(pattern, text_lower):
            detected.append(p)
            
    score = 10
    issues = []
    if len(detected) > 0:
        score = 6
        issues.append({
            "message": f"First-person pronouns detected: {', '.join(detected)}. Resumes should be written in third-person implied (e.g. instead of 'I managed the team', write 'Managed the team').",
            "severity": "error"
        })
        
    return score, issues

def check_page_and_word_counts(text: str, metadata: Dict[str, Any]) -> Tuple[int, List[Dict[str, str]]]:
    """Checks page and word limits."""
    page_count = metadata.get("page_count", 1)
    word_count = len(text.split())
    
    issues = []
    score = 10
    
    # Page length evaluation
    if page_count > 2:
        score -= 3
        issues.append({"message": f"Resume is {page_count} pages long. Recruiters prefer a concise 1-2 page document unless you have 15+ years of experience.", "severity": "warning"})
    elif page_count == 0 or word_count < 100:
        score -= 8
        issues.append({"message": "Resume text is too sparse or could not be parsed. Verify the file is not empty or scan-only.", "severity": "error"})
        
    # Word count evaluation
    if word_count > 1200:
        score -= 2
        issues.append({"message": f"High word count ({word_count} words). Keep the layout airy and avoid wall-of-text blocks.", "severity": "warning"})
    elif word_count < 300 and word_count > 100:
        score -= 2
        issues.append({"message": f"Low word count ({word_count} words). Add details about your achievements, core skills, or projects.", "severity": "warning"})
        
    return max(0, score), issues

def run_tier1_checks(text: str, metadata: Dict[str, Any]) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Orchestrates all Tier 1 rule-based checks. Returns overall Tier 1 score (0-100) and full list of checks.
    """
    doc = load_spacy_doc(text)
    
    # Gather checks
    t1_checks = []
    
    # 1. Contact info
    score_contact, issues_contact = check_contact_info(text)
    t1_checks.append({
        "id": "contact_info",
        "name": "Contact Information Presence",
        "score": score_contact,
        "category": "Contact Info",
        "passed": score_contact >= 7,
        "issues": issues_contact
    })
    
    # 2. Section headers
    score_headers, issues_headers = check_section_headers(text)
    t1_checks.append({
        "id": "section_headers",
        "name": "Section Header Standards",
        "score": score_headers,
        "category": "Structure",
        "passed": score_headers >= 7,
        "issues": issues_headers
    })
    
    # 3. Layout compatibility (adds 4 checks)
    layout_checks = check_layout_compatibility(metadata)
    t1_checks.extend(layout_checks)
    
    # 4. Dates
    score_dates, issues_dates = check_date_consistency(text)
    t1_checks.append({
        "id": "date_consistency",
        "name": "Date Formatting Consistency",
        "score": score_dates,
        "category": "Formatting",
        "passed": score_dates >= 8,
        "issues": issues_dates
    })
    
    # 5. Bullets
    score_bullets, issues_bullets = check_bullet_consistency(text)
    t1_checks.append({
        "id": "bullet_formatting",
        "name": "Bullet Point Formatting",
        "score": score_bullets,
        "category": "Formatting",
        "passed": score_bullets >= 8,
        "issues": issues_bullets
    })
    
    # 6. Quantification
    score_quant, issues_quant = check_quantification(text)
    t1_checks.append({
        "id": "quantification_presence",
        "name": "Quantification & Metrics",
        "score": score_quant,
        "category": "Language",
        "passed": score_quant >= 7,
        "issues": issues_quant
    })
    
    # 7. Clichés
    score_buzz, issues_buzz = check_buzzwords(text)
    t1_checks.append({
        "id": "buzzword_cliches",
        "name": "Buzzwords & Clichés Match",
        "score": score_buzz,
        "category": "Language",
        "passed": score_buzz >= 8,
        "issues": issues_buzz
    })
    
    # 8. Passive voice
    score_passive, issues_passive = check_grammar_passive_voice(doc)
    t1_checks.append({
        "id": "passive_voice",
        "name": "Active vs. Passive Voice",
        "score": score_passive,
        "category": "Language",
        "passed": score_passive >= 8,
        "issues": issues_passive
    })
    
    # 9. Pronouns
    score_pronouns, issues_pronouns = check_first_person_pronouns(text)
    t1_checks.append({
        "id": "first_person_pronouns",
        "name": "First-Person Pronouns",
        "score": score_pronouns,
        "category": "Language",
        "passed": score_pronouns >= 8,
        "issues": issues_pronouns
    })
    
    # 10. Counts
    score_counts, issues_counts = check_page_and_word_counts(text, metadata)
    t1_checks.append({
        "id": "page_word_limits",
        "name": "Length & Page Counts",
        "score": score_counts,
        "category": "Structure",
        "passed": score_counts >= 8,
        "issues": issues_counts
    })
    
    # Calculate weighted average score for Tier 1
    total_score = sum(c["score"] for c in t1_checks)
    average_score = round((total_score / len(t1_checks)) * 10) # Out of 100
    
    return average_score, t1_checks
