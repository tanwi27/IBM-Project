'use client';

import React, { useState, useEffect, useRef } from 'react';

export default function Home() {
  // App State
  const [level, setLevel] = useState('Mid-level');
  const [targetRole, setTargetRole] = useState('');
  const [jdText, setJdText] = useState('');
  const [file, setFile] = useState(null);
  
  // API Response Data
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [resumeData, setResumeData] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [scoreHistory, setScoreHistory] = useState([]);
  
  // AutoFix State
  const [bullets, setBullets] = useState([]);
  const [selectedBulletIndex, setSelectedBulletIndex] = useState(null);
  const [flaggedIssue, setFlaggedIssue] = useState('duty not achievement');
  const [customRole, setCustomRole] = useState('Software Engineering');
  const [rewriting, setRewriting] = useState(false);
  const [currentRewrite, setCurrentRewrite] = useState(null);
  const [bulletStatus, setBulletStatus] = useState({}); // idx -> 'approved' | 'rejected' | null
  
  const fileInputRef = useRef(null);

  // AutoExtract bullets whenever resume text arrives
  useEffect(() => {
    if (resumeData && resumeData.score) {
      // Fallback extract bullets from text
      const extracted = extractBulletsFromText(resumeData.score.text_raw || '');
      setBullets(extracted);
      setSelectedBulletIndex(extracted.length > 0 ? 0 : null);
      // Fetch history for timeline
      fetchHistory(resumeData.file_hash);
    }
  }, [resumeData]);

  // Extract bullets algorithm
  const extractBulletsFromText = (text) => {
    if (!text) return [];
    const lines = text.split('\n');
    const bulletSymbols = ['•', '▪', '-', '*', '◦', '▪', '♦', '–', '—', '➢', '➔', '✓', '✔', '★', '▶', '●', '»'];
    const extracted = [];
    
    lines.forEach(line => {
      const trimmed = line.trim();
      if (!trimmed) return;
      
      const startsWithBullet = bulletSymbols.some(symbol => trimmed.startsWith(symbol));
      if (startsWithBullet) {
        let cleaned = trimmed;
        bulletSymbols.forEach(symbol => {
          if (cleaned.startsWith(symbol)) {
            cleaned = cleaned.substring(symbol.length).trim();
          }
        });
        if (cleaned.length > 10) {
          extracted.push(cleaned);
        }
      } else if (trimmed.length > 30 && trimmed.length < 200 && 
                (trimmed.startsWith('Responsible') || trimmed.startsWith('Managed') || 
                 trimmed.startsWith('Led') || trimmed.startsWith('Developed') || 
                 trimmed.startsWith('Built') || trimmed.startsWith('Created'))) {
        extracted.push(trimmed);
      }
    });

    if (extracted.length === 0) {
      const sentences = text.split(/[.\n]/);
      sentences.forEach(s => {
        const cleanS = s.trim();
        if (cleanS.length > 30 && cleanS.length < 180) {
          extracted.push(cleanS);
        }
      });
    }
    
    return [...new Set(extracted)].slice(0, 15); // Return unique first 15 bullets for analysis
  };

  const fetchHistory = async (fileHash) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/history?file_hash=${fileHash}`);
      if (res.ok) {
        const data = await res.json();
        setScoreHistory(data);
      }
    } catch (e) {
      console.error("Failed to load history chart data", e);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
  };

  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('dragover');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Please select or drop a PDF/DOCX resume file.");
      return;
    }

    setLoading(true);
    setError(null);
    setResumeData(null);
    setCurrentRewrite(null);
    setBulletStatus({});

    const formData = new FormData();
    formData.append('file', file);
    formData.append('level', level);
    formData.append('target_role', targetRole);
    formData.append('jd_text', jdText);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errDetail = await response.json();
        throw new Error(errDetail.detail || "Internal Server Error during upload");
      }

      const data = await response.json();
      // Inject raw text to let JS parse client-side bullets
      if (data.score) {
        data.score.text_raw = file.name.endsWith('.pdf') ? data.score.text_raw : null; 
      }
      
      // If we don't have raw text from pdfplumber easily in standard response, let's build a fallback text from parsed components
      // or request backend to supply it. Our backend returns it. Let's make sure it loads.
      // We will look at structural metadata and scores.
      setResumeData(data);
      setActiveTab('overview');
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAutoFixSubmit = async () => {
    if (selectedBulletIndex === null || bullets.length === 0) return;
    
    setRewriting(true);
    setCurrentRewrite(null);

    const original = bullets[selectedBulletIndex];
    // Gather surrounding bullets for context
    const prevBullet = selectedBulletIndex > 0 ? bullets[selectedBulletIndex - 1] : "";
    const nextBullet = selectedBulletIndex < bullets.length - 1 ? bullets[selectedBulletIndex + 1] : "";
    const context = `Before: ${prevBullet}\nAfter: ${nextBullet}`;

    const params = new URLSearchParams();
    params.append('original_bullet', original);
    params.append('context', context);
    params.append('role', customRole);
    params.append('level', level);
    params.append('flagged_issue', flaggedIssue);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/autofix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params,
      });

      if (!response.ok) throw new Error("AutoFix generation failed.");
      
      const data = await response.json();
      setCurrentRewrite(data);
    } catch (e) {
      console.error(e);
      setError("Failed to get rewrite suggestion.");
    } finally {
      setRewriting(false);
    }
  };

  const submitFeedback = async (rewriteId, feedback) => {
    const params = new URLSearchParams();
    params.append('rewrite_id', rewriteId);
    params.append('feedback', feedback);
    
    try {
      await fetch('http://127.0.0.1:8000/api/v1/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params,
      });
    } catch (e) {
      console.error("Failed to submit feedback", e);
    }
  };

  const handleAcceptRewrite = async () => {
    if (!currentRewrite) return;
    
    const updatedBullets = [...bullets];
    updatedBullets[selectedBulletIndex] = currentRewrite.rewrite;
    setBullets(updatedBullets);
    
    setBulletStatus({
      ...bulletStatus,
      [selectedBulletIndex]: 'approved'
    });
    
    if (currentRewrite.rewrite_id) {
      await submitFeedback(currentRewrite.rewrite_id, 'approved');
    }
    
    // Refresh history graph after update
    if (resumeData) {
      fetchHistory(resumeData.file_hash);
    }
    
    setCurrentRewrite(null);
  };

  const handleRejectRewrite = async () => {
    if (!currentRewrite) return;
    
    setBulletStatus({
      ...bulletStatus,
      [selectedBulletIndex]: 'rejected'
    });
    
    if (currentRewrite.rewrite_id) {
      await submitFeedback(currentRewrite.rewrite_id, 'rejected');
    }
    
    setCurrentRewrite(null);
  };

  // Compute layout values for radial progress gauge
  const overallScore = resumeData?.score?.overall_score || 0;
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (overallScore / 100) * circumference;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="brand">
          <div className="brand-logo">Δ</div>
          <div>
            <h1 className="brand-title">Antigravity Screener</h1>
            <div className="brand-subtitle">ATS Compliance Checker & AI Bullet AutoFix Platform</div>
          </div>
        </div>
        <div className="badge badge-info">
          {level} Active
        </div>
      </header>

      {/* Main Layout Grid */}
      <div className="grid-layout">
        
        {/* Left Hand side Configuration Drawer */}
        <section className="glass-card">
          <h2 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '20px', borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
            Resume & Target Details
          </h2>
          
          <form onSubmit={handleUploadSubmit}>
            <div className="form-group">
              <label className="form-label">Selected Experience Band</label>
              <select className="form-select" value={level} onChange={(e) => setLevel(e.target.value)}>
                <option value="Entry-level">Entry-level (&lt; 2 years)</option>
                <option value="Mid-level">Mid-level (2 - 10 years)</option>
                <option value="Senior-level">Senior-level (10+ years)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">
                Target Role
                <span className="form-label-desc">Optional</span>
              </label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="e.g. Senior Frontend Engineer" 
                value={targetRole} 
                onChange={(e) => setTargetRole(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                Upload Resume File
                <span className="form-label-desc">PDF or DOCX</span>
              </label>
              <div 
                className="upload-zone"
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current.click()}
              >
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  style={{ display: 'none' }} 
                  accept=".pdf,.docx,.doc" 
                  onChange={handleFileChange}
                />
                <span className="upload-icon">↑</span>
                <span className="upload-title">
                  {file ? file.name : "Drag & drop files here"}
                </span>
                <span className="upload-desc">
                  {file ? `${(file.size / 1024).toFixed(1)} KB` : "or click to browse from system"}
                </span>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">
                Paste Job Description
                <span className="form-label-desc">Optional — enables keyword scanner</span>
              </label>
              <textarea 
                className="form-textarea" 
                placeholder="Paste the target job description to match skills, keywords, and domain fit..."
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
              />
            </div>

            {error && (
              <div style={{ color: 'var(--color-danger)', fontSize: '13px', margin: '12px 0', padding: '10px', background: 'var(--color-danger-bg)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '8px' }} disabled={loading}>
              {loading ? "Analyzing Pipeline..." : "Run Compliance Scanner"}
            </button>
          </form>
        </section>

        {/* Right Hand side Dashboard Report Viewer */}
        <section className="glass-card" style={{ minHeight: '600px' }}>
          
          {!resumeData && !loading && (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '16px', color: 'var(--text-secondary)', padding: '60px 20px', textAlign: 'center' }}>
              <div style={{ fontSize: '48px', opacity: 0.3 }}>📄</div>
              <div>
                <h3 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '6px' }}>Ready to Grade</h3>
                <p style={{ maxWidth: '400px', fontSize: '13px' }}>Upload a candidate's resume and target level to trigger the parallel LangGraph deterministic and AI evaluation nodes.</p>
              </div>
            </div>
          )}

          {loading && (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '20px', padding: '100px 20px' }}>
              <div className="brand-logo" style={{ animation: 'float 2s ease-in-out infinite', width: '52px', height: '52px', fontSize: '24px' }}>Δ</div>
              <div style={{ textAlign: 'center' }}>
                <h3 style={{ fontSize: '15px', fontWeight: '700', marginBottom: '6px' }}>Running Compliance Checkers</h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Determining layout matrices, counting word distributions, calling LLM grading nodes...</p>
              </div>
            </div>
          )}

          {resumeData && !loading && (
            <div className="score-dashboard">
              
              {/* Radial Score Gauge Banner */}
              <div className="scores-banner">
                <div className="score-radial-wrapper">
                  <svg className="score-radial-svg">
                    <defs>
                      <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#6366f1" />
                        <stop offset="50%" stopColor="#a855f7" />
                        <stop offset="100%" stopColor="#d946ef" />
                      </linearGradient>
                    </defs>
                    <circle className="score-radial-bg" cx="85" cy="85" r={radius} />
                    <circle 
                      className="score-radial-progress" 
                      cx="85" 
                      cy="85" 
                      r={radius} 
                      style={{ strokeDashoffset }}
                    />
                  </svg>
                  <div className="score-radial-text">
                    <div className="score-radial-number">{overallScore}</div>
                    <div className="score-radial-label">Match Score</div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '100%' }}>
                  <div>
                    <h3 style={{ fontSize: '20px', fontWeight: '700' }}>{resumeData.filename}</h3>
                    <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      Analyzed level: <strong style={{ color: 'var(--text-primary)' }}>{level}</strong> | 
                      Format: <strong style={{ color: 'var(--text-primary)' }}>{resumeData.structural_metadata.page_count} page(s)</strong>
                    </p>
                  </div>
                  
                  {/* Score Breakdown Cards */}
                  <div className="score-breakdown-grid">
                    <div className="subscore-card">
                      <div className="subscore-val" style={{ color: 'var(--primary-accent)' }}>
                        {resumeData.score.tier1.score}%
                      </div>
                      <div className="subscore-label">Tier 1 Rules</div>
                    </div>
                    
                    <div className="subscore-card">
                      <div className="subscore-val" style={{ color: 'var(--secondary-accent)' }}>
                        {resumeData.score.tier2.score}%
                      </div>
                      <div className="subscore-label">Tier 2 Qualitative</div>
                    </div>

                    {resumeData.score.keyword_match && (
                      <div className="subscore-card">
                        <div className="subscore-val" style={{ color: 'var(--color-success)' }}>
                          {resumeData.score.keyword_match.score}%
                        </div>
                        <div className="subscore-label">Keyword Match</div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Module D Eligibility Notification Bar */}
              {resumeData.score.eligibility && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '16px', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '13px', fontWeight: '700', textTransform: 'uppercase' }}>Recruiter Quick Scan Check:</span>
                    
                    {resumeData.score.eligibility.level_match === 'match' ? (
                      <span className="badge badge-success">Level Verified</span>
                    ) : (
                      <span className="badge badge-danger">Level Mismatch</span>
                    )}

                    {resumeData.score.eligibility.role_fit !== 'no_jd_provided' && (
                      resumeData.score.eligibility.role_fit === 'match' ? (
                        <span className="badge badge-success">Domain Verified</span>
                      ) : resumeData.score.eligibility.role_fit === 'partial' ? (
                        <span className="badge badge-warning">Partial Domain Fit</span>
                      ) : (
                        <span className="badge badge-danger">Domain Mismatch</span>
                      )
                    )}
                  </div>
                  
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    <strong>Level Reasoning:</strong> {resumeData.score.eligibility.level_reason}
                  </div>
                  {resumeData.score.eligibility.role_fit_reason && (
                    <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                      <strong>Domain Fit Reasoning:</strong> {resumeData.score.eligibility.role_fit_reason}
                    </div>
                  )}
                </div>
              )}

              {/* Navigation Tabs */}
              <div className="tabs-header">
                <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
                  Overview
                </button>
                <button className={`tab-btn ${activeTab === 'tier1' ? 'active' : ''}`} onClick={() => setActiveTab('tier1')}>
                  Tier 1 — Rules ({resumeData.score.tier1.checks.filter(c => !c.passed).length})
                </button>
                <button className={`tab-btn ${activeTab === 'tier2' ? 'active' : ''}`} onClick={() => setActiveTab('tier2')}>
                  Tier 2 — Qualitative ({resumeData.score.tier2.checks.filter(c => c.score < 7).length})
                </button>
                {resumeData.score.keyword_match && (
                  <button className={`tab-btn ${activeTab === 'keywords' ? 'active' : ''}`} onClick={() => setActiveTab('keywords')}>
                    Keywords ({resumeData.score.keyword_match.missing_keywords.length} Missing)
                  </button>
                )}
                <button className={`tab-btn ${activeTab === 'autofix' ? 'active' : ''}`} onClick={() => setActiveTab('autofix')}>
                  AutoFix Rewrite Hub
                </button>
                <button className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>
                  Watch Score Climb
                </button>
              </div>

              {/* Active Tab Content */}
              
              {/* Tab 1: Overview Summary */}
              {activeTab === 'overview' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div>
                    <h4 style={{ fontSize: '15px', fontWeight: '700', marginBottom: '8px' }}>Analysis Summary</h4>
                    <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                      This resume is rated at <strong style={{ color: 'var(--text-primary)' }}>{overallScore}/100</strong> overall. 
                      It completed 20+ Tier-1 deterministic parsing checks (score: {resumeData.score.tier1.score}%) and 
                      10 qualitative checks (score: {resumeData.score.tier2.score}%). 
                      {resumeData.score.keyword_match ? " It has been cross-referenced with your job description keywords." : " Paste a Job Description to verify keyword alignment."}
                    </p>
                  </div>
                  
                  {/* Top Critical Fixes */}
                  <div>
                    <h4 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '12px', textTransform: 'uppercase', color: 'var(--color-danger)' }}>
                      Critical ATS Fixes Needed
                    </h4>
                    
                    <div className="issues-feed">
                      {/* Gather all failed formatting checks */}
                      {resumeData.score.tier1.checks.filter(c => !c.passed).slice(0, 3).map((check, i) => (
                        <div className="issue-card severity-error" key={i}>
                          <div className="issue-title">
                            <span>{check.name}</span>
                            <span className="badge badge-danger">Tier 1 Error</span>
                          </div>
                          <div className="issue-text">
                            {check.issues[0]?.message}
                          </div>
                        </div>
                      ))}

                      {/* Qualitative Issues */}
                      {resumeData.score.tier2.checks.filter(c => c.score < 7).slice(0, 2).map((check, i) => (
                        <div className="issue-card severity-warning" key={i}>
                          <div className="issue-title">
                            <span>Improve Qualitative: {check.id.replace(/_/g, ' ')}</span>
                            <span className="badge badge-warning">Tier 2 Grade {check.score}/10</span>
                          </div>
                          <div className="issue-text">
                            {check.issues[0]?.reason}
                          </div>
                          {check.issues[0]?.line && (
                            <div className="issue-line-quote">
                              "{check.issues[0].line}"
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 2: Tier 1 Detailed Rules */}
              {activeTab === 'tier1' && (
                <div className="issues-feed">
                  <h4 style={{ fontSize: '15px', fontWeight: '700', marginBottom: '8px' }}>Deterministic Parser Verification</h4>
                  {resumeData.score.tier1.checks.map((check, i) => (
                    <div className={`issue-card ${check.passed ? 'severity-info' : 'severity-error'}`} key={i} style={{ borderLeftWidth: '4px' }}>
                      <div className="issue-title">
                        <span>{check.name}</span>
                        <span className={`badge ${check.passed ? 'badge-success' : 'badge-danger'}`}>
                          {check.passed ? 'Pass' : 'Failed'}
                        </span>
                      </div>
                      
                      {check.passed ? (
                        <div className="issue-text" style={{ color: 'var(--text-muted)' }}>
                          No structural or formatting compliance flags. Standard ATS safe layout.
                        </div>
                      ) : (
                        <div className="issue-text">
                          {check.issues.map((iss, j) => (
                            <div key={j} style={{ marginBottom: '4px' }}>• {iss.message}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Tab 3: Tier 2 Qualitative Evaluator */}
              {activeTab === 'tier2' && (
                <div className="issues-feed">
                  <h4 style={{ fontSize: '15px', fontWeight: '700', marginBottom: '8px' }}>LLM Qualitative Evaluation</h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                    Evaluated by Claude/Gemini model under temperature = 0 against a fixed quality grading rubric.
                  </p>
                  
                  {resumeData.score.tier2.checks.map((check, i) => {
                    const isFine = check.score >= 7;
                    return (
                      <div className={`issue-card ${isFine ? 'severity-info' : 'severity-warning'}`} key={i}>
                        <div className="issue-title">
                          <span style={{ textTransform: 'capitalize' }}>{check.id.replace(/_/g, ' ')}</span>
                          <span className={`badge ${isFine ? 'badge-success' : 'badge-warning'}`}>
                            {check.score}/10
                          </span>
                        </div>
                        
                        {isFine ? (
                          <div className="issue-text" style={{ color: 'var(--text-muted)' }}>
                            Grade satisfies standard thresholds. Written with active phrasing and specificity.
                          </div>
                        ) : (
                          <div className="issue-text">
                            {check.issues.map((iss, j) => (
                              <div key={j} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                <div><strong>Grading Feedback:</strong> {iss.reason}</div>
                                {iss.line && <div className="issue-line-quote">"{iss.line}"</div>}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Tab 4: Keywords matched/missing */}
              {activeTab === 'keywords' && resumeData.score.keyword_match && (
                <div className="kw-grid">
                  <div>
                    <h4 className="kw-column-title">
                      Missing Keywords
                      <span className="kw-badge-count">{resumeData.score.keyword_match.missing_keywords.length}</span>
                    </h4>
                    <div className="kw-list">
                      {resumeData.score.keyword_match.missing_keywords.map((kw, i) => (
                        <div className="kw-card" key={i} style={{ borderLeft: '3px solid var(--color-danger)' }}>
                          <div className="kw-card-header">
                            <span className="kw-name">{kw.keyword}</span>
                            <span className="badge badge-danger" style={{ fontSize: '9px' }}>
                              Priority: {Math.round(kw.weight * 10)}/10
                            </span>
                          </div>
                          <span className="kw-why">Reason: {kw.why}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="kw-column-title">
                      Matched Keywords
                      <span className="kw-badge-count">{resumeData.score.keyword_match.matched_keywords.length}</span>
                    </h4>
                    <div className="kw-list">
                      {resumeData.score.keyword_match.matched_keywords.map((kw, i) => (
                        <div className="kw-card" key={i} style={{ borderLeft: '3px solid var(--color-success)' }}>
                          <div className="kw-card-header">
                            <span className="kw-name">{kw.keyword}</span>
                            <span className="badge badge-success" style={{ fontSize: '9px' }}>
                              Similarity: {Math.round(kw.similarity * 100)}%
                            </span>
                          </div>
                          <span className="kw-why">In resume: "{kw.matched_in_resume}"</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 5: AutoFix Optimizer */}
              {activeTab === 'autofix' && (
                <div className="autofix-panel">
                  <div>
                    <h4 style={{ fontSize: '15px', fontWeight: '700', marginBottom: '6px' }}>Select Resume Bullet Point to Optimize</h4>
                    <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                      Click on any extracted bullet to rewrite it using RAG-assisted proven bullet templates.
                    </p>
                  </div>

                  <div className="bullet-selector-list">
                    {bullets.map((bullet, idx) => (
                      <div 
                        className={`bullet-row ${selectedBulletIndex === idx ? 'selected' : ''}`}
                        key={idx}
                        onClick={() => {
                          setSelectedBulletIndex(idx);
                          setCurrentRewrite(null);
                        }}
                      >
                        <span className="bullet-text">{bullet}</span>
                        
                        {bulletStatus[idx] === 'approved' && (
                          <span className="badge badge-success" style={{ alignSelf: 'center', fontSize: '9px' }}>Approved</span>
                        )}
                        {bulletStatus[idx] === 'rejected' && (
                          <span className="badge badge-danger" style={{ alignSelf: 'center', fontSize: '9px' }}>Rejected</span>
                        )}
                        {!bulletStatus[idx] && (
                          <span className="bullet-badge">Optimize</span>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Bullet Configuration and Call */}
                  {selectedBulletIndex !== null && bullets[selectedBulletIndex] && (
                    <div style={{ marginTop: '12px', borderTop: '1px solid var(--border-color)', paddingTop: '20px' }}>
                      <h4 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '12px' }}>
                        Configure AutoFix Rules
                      </h4>
                      
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label" style={{ fontSize: '12px' }}>Select Focus Metric</label>
                          <select className="form-select" value={flaggedIssue} onChange={(e) => setFlaggedIssue(e.target.value)}>
                            <option value="duty not achievement">Convert Duty to Achievement</option>
                            <option value="weak verb">Sharpen / Add Strong Action Verb</option>
                            <option value="needs metrics">Quantification (Needs Metrics)</option>
                            <option value="vague phrasing">Remove filler/vague phrases</option>
                          </select>
                        </div>

                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label" style={{ fontSize: '12px' }}>Domain Library Target</label>
                          <select className="form-select" value={customRole} onChange={(e) => setCustomRole(e.target.value)}>
                            <option value="Software Engineering">Software Engineering</option>
                            <option value="Product Management">Product Management</option>
                            <option value="Marketing">Marketing / Growth</option>
                            <option value="Finance">Finance / Auditing</option>
                            <option value="Data Science">Data Science / ML</option>
                          </select>
                        </div>
                      </div>

                      <button 
                        type="button" 
                        className="btn btn-secondary" 
                        style={{ width: '100%', border: '1px solid var(--primary-accent)', color: 'var(--primary-accent)' }}
                        onClick={handleAutoFixSubmit}
                        disabled={rewriting}
                      >
                        {rewriting ? "Generating AI Rewrite..." : "Optimize Selected Bullet"}
                      </button>
                    </div>
                  )}

                  {/* Diff output comparison and Accept/Reject buttons */}
                  {currentRewrite && (
                    <div style={{ animation: 'float 4s ease-in-out infinite' }}>
                      <div className="diff-container">
                        <div className="diff-box diff-box-original">
                          <span className="diff-label diff-label-original">Original Bullet</span>
                          <p style={{ color: 'var(--text-secondary)' }}>{currentRewrite.original}</p>
                        </div>

                        <div className="diff-box diff-box-rewrite">
                          <span className="diff-label diff-label-rewrite">AI Rewrite Suggestion</span>
                          <p style={{ fontWeight: '500' }}>{currentRewrite.rewrite}</p>
                        </div>
                      </div>

                      <div className="diff-meta">
                        <div className="diff-meta-reason">
                          💡 Why it changed: {currentRewrite.changed_because}
                        </div>
                        {currentRewrite.note && (
                          <div className="diff-meta-note">
                            📌 Edits: {currentRewrite.note}
                          </div>
                        )}
                      </div>

                      <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                        <button type="button" className="btn btn-primary" style={{ flex: 1 }} onClick={handleAcceptRewrite}>
                          Accept Rewrite
                        </button>
                        <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={handleRejectRewrite}>
                          Reject
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 6: Watch Score Climb Chart */}
              {activeTab === 'history' && (
                <div>
                  <h4 style={{ fontSize: '15px', fontWeight: '700', marginBottom: '8px' }}>Watch Your Score Climb</h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Track candidate progression across multiple scans as they resolve compliance errors and accept re-written bullet metrics.
                  </p>
                  
                  {scoreHistory.length <= 1 ? (
                    <div style={{ padding: '40px', textLight: 'center', background: 'rgba(255, 255, 255, 0.01)', border: '1px solid var(--border-color)', borderRadius: '12px', marginTop: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      📄 First scan recorded. Click "Optimize Bullet" and run another scan to watch the chart populate.
                    </div>
                  ) : (
                    <div className="history-timeline">
                      {scoreHistory.map((pt, idx) => (
                        <div className="history-point" key={idx}>
                          <div 
                            className="history-bar" 
                            style={{ height: `${(pt.overall_score / 100) * 120}px` }}
                          >
                            <span className="history-val">{pt.overall_score}%</span>
                          </div>
                          <span className="history-label">{pt.date.split(' ')[1] || pt.date}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

            </div>
          )}

        </section>

      </div>
    </div>
  );
}
