# 🎯 AI Resume Screener & Optimizer

An advanced, full-stack application designed to parse, score, and optimize professional resumes against industry standards and job descriptions. Combining a deterministic rule engine with state-of-the-art Large Language Models (LLMs), the platform provides real-time feedback, multi-tiered qualitative scoring, and an interactive **AutoFix** workspace to rewrite and refine weak resume bullets.

---

## 🚀 Key Features

### 1. Multi-Tiered Evaluation Pipeline
*   **Tier 1 (Deterministic Score - 100pts):** Written using `spaCy`, this module scans structure, contact details (email, phone, LinkedIn, portfolio/GitHub), standard headers (Experience, Education, Skills, Projects, Summary), formatting constraints (page counts, word counts), and screens for common corporate buzzwords.
*   **Tier 2 (Qualitative Score - 100pts):** Leverages LLMs to grade resumes across 10 critical dimensions:
    1.  *Achievement vs. Duty* (Focus on outcomes, not responsibilities)
    2.  *Quantification Quality* (Presence of impact-driven metrics)
    3.  *Specificity* (Actionable examples over generic fluff)
    4.  *Impact Clarity* (Understanding the business/product outcomes)
    5.  *Seniority Alignment* (Language appropriate to level)
    6.  *Action Verb Strength* (Use of strong, active verbs)
    7.  *Narrative Coherence* (Consistent career story)
    8.  *Role Relevance* (Keyword and task overlap with target role)
    9.  *Conciseness* (Filler word reduction)
    10. *Red Flags* (Unexplained gaps, first-person pronouns, inconsistency)

### 2. Job Description & Keyword Matcher (Module C & D)
*   Computes semantic similarity and checks for critical skill coverage against an uploaded job description.
*   Evaluates role eligibility (Module D) using LLMs to verify if the candidate matches the target experience tier.
*   Uses a **keyless local embedding fallback** (deterministic mathematical hashes/cosine similarity) to support offline keyword targeting without API keys.

### 3. Agentic AutoFix Bullet Optimizer (Module B)
*   An interactive sandbox that identifies weaker bullets and leverages LLM editors to rewrite them.
*   Retrieves nearest-neighbor style templates based on the user's role and target seniority level.
*   Refines sentences without fabricating details, prompting the user to supply metrics where necessary.
*   Includes user approval logging to track acceptance rates and watch scores improve in real-time.

### 4. Premium Next.js UI Dashboard
*   Interactive drag-and-drop file upload interface (supporting `.pdf` and `.docx` formats).
*   Live scoring widgets, issue checklists categorized by severity, and tabbed deep-dives.
*   Interactive sandbox to test/rewrite bullets.
*   Responsive layout styled with Tailwind CSS and premium design elements.

---

## 🛠️ Technology Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) | High-performance, async Python web framework. |
| **Frontend** | [Next.js](https://nextjs.org/) (React 19) | Modern React framework with server/client components. |
| **Styling** | [Tailwind CSS v4](https://tailwindcss.com/) | Utility-first styling framework. |
| **Parsing** | `pdfplumber` & `python-docx` | Robust text and structural metadata extraction from PDFs/DOCXs. |
| **NLP Engine** | [spaCy English Model](https://spacy.io/) | Rule-based entity extraction and token parsing. |
| **AI Integration** | Anthropic (Claude), OpenAI (GPT), Google (Gemini) | Multi-provider support for qualitative grading and autofixes. |
| **Database** | SQLite | Default local storage for tracking scores and bullet suggestions. |

---

## 📁 Repository Structure

```text
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── endpoints.py      # Main router endpoints (upload, autofix, feedback, history)
│   │   ├── core/
│   │   │   ├── config.py         # Application configuration & Pydantic settings
│   │   │   └── llm.py            # LLM API orchestrator (OpenAI, Anthropic, Gemini, Voyage)
│   │   └── services/
│   │       ├── autofix.py        # Bullet rewriter / RAG client
│   │       ├── evaluator.py      # Qualitative/ATS grading logic (Module A & D)
│   │       ├── keyword.py        # Keyword extraction, gazetteer & similarity matchers (Module C)
│   │       ├── parser.py         # PDF & DOCX text and layout parsers
│   │       ├── rules.py          # Deterministic rules & spaCy-based parser checks (Tier 1)
│   │       └── seed.py           # Programmatic database seed scripts
│   ├── requirements.txt          # Python dependencies
│   └── resume_screener.db        # Preconfigured SQLite database
├── frontend/
│   ├── src/
│   │   └── app/
│   │       ├── layout.js         # Root HTML layout and font loading
│   │       ├── page.js           # Core Next.js dashboard UI code
│   │       └── globals.css       # Global styles and theme configuration
│   ├── package.json              # NPM dependencies and project configuration
│   └── next.config.mjs           # Next.js configurations
├── LICENSE                       # MIT License file
└── README.md                     # Project documentation (this file)
```

---

## ⚙️ Installation & Setup

### Prerequisites
*   Python 3.10 or higher
*   Node.js 18.0 or higher
*   NPM, Yarn, PNPM, or Bun

---

### Backend Setup

1.  **Navigate to the backend folder:**
    ```bash
    cd backend
    ```

2.  **Create and activate a virtual environment:**
    *   **Windows (PowerShell):**
        ```powershell
        python -m venv .venv
        .venv\Scripts\Activate.ps1
        ```
    *   **Mac/Linux:**
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Download the spaCy English NLP model:**
    ```bash
    python -m spacy download en_core_web_sm
    ```

5.  **Set up environment variables:**
    *   Copy the template:
        ```bash
        cp .env.example .env
        ```
    *   Open `.env` and fill in your API key(s) to enable advanced AI grading:
        ```env
        PRIMARY_LLM_PROVIDER="openai" # options: openai, anthropic, gemini
        OPENAI_API_KEY="your-openai-api-key"
        # or
        ANTHROPIC_API_KEY="your-anthropic-api-key"
        # or
        GEMINI_API_KEY="your-gemini-api-key"
        ```

6.  **Run the backend server:**
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```
    The server will start running at `http://127.0.0.1:8000`. You can inspect the Swagger API documentation at `http://127.0.0.1:8000/docs`.

---

### Frontend Setup

1.  **Navigate to the frontend folder:**
    ```bash
    cd ../frontend
    ```

2.  **Install node modules:**
    ```bash
    npm install
    ```

3.  **Run the development server:**
    ```bash
    npm run dev
    ```
    The dashboard will launch on `http://localhost:3000`.

---

## 📡 API Reference

### 1. Upload Resume & Score
*   **Endpoint:** `/api/v1/upload`
*   **Method:** `POST`
*   **Request Type:** `multipart/form-data`
*   **Parameters:**
    *   `file`: The resume file (PDF or DOCX).
    *   `level`: Junior/Mid/Senior target seniority level.
    *   `target_role` (Optional): The name of the target position (e.g. Software Engineer).
    *   `jd_text` (Optional): Raw text of the job description to match against.

### 2. AutoFix Bullet Optimization
*   **Endpoint:** `/api/v1/autofix`
*   **Method:** `POST`
*   **Request Type:** `application/x-www-form-urlencoded`
*   **Parameters:**
    *   `original_bullet`: The sentence to rewrite.
    *   `context`: Adjacent sentences or description details.
    *   `role`: Target job role.
    *   `level`: Target seniority level.
    *   `flagged_issue`: The issue type (e.g. `achievement vs duty`).

### 3. Log Rewrite Feedback
*   **Endpoint:** `/api/v1/feedback`
*   **Method:** `POST`
*   **Request Type:** `application/x-www-form-urlencoded`
*   **Parameters:**
    *   `rewrite_id`: Reference index of the suggested rewrite.
    *   `feedback`: `"approved"` or `"rejected"`.

---

## 🛡️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
Copyright (c) 2026 Tanwi Gupta.
