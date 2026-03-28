# resumeparser_spacy_app.py
"""
HireSmart AI — Streamlit Resume Parser (spaCy SkillNER + PhraseMatcher)
Features:
 - Upload resume (pdf/docx/txt) or paste text
 - Extract name, email, phone, skills (phrase-matching + spaCy entities)
 - Compute ATS score
 - Recommend best matching roles (heuristic)
 - Optional live job fetch via SerpAPI (set SERPAPI_KEY below)
"""


# resumeparser_spacy_app.py
"""
HireSmart AI — Streamlit Resume Parser (spaCy SkillNER + PhraseMatcher)
Features:
 - Upload resume (pdf/docx/txt) or paste text
 - Extract name, email, phone, skills (phrase-matching + spaCy entities)
 - Compute ATS score
 - Recommend best matching roles (heuristic)
 - Optional live job fetch via SerpAPI
"""

import streamlit as st
import re
import requests
import docx
import PyPDF2
from io import BytesIO
from collections import Counter
from pathlib import Path
import html

# --- Attempt to import spaCy and load model ---
try:
    import spacy
    from spacy.matcher import PhraseMatcher
    SPACY_AVAILABLE = True
except Exception:
    SPACY_AVAILABLE = False

# ----------------------------------------
# CONFIG
# ----------------------------------------
st.set_page_config(page_title="HireSmart AI — Resume Parser", layout="wide", page_icon="📄")

SERPAPI_KEY = "17f0b6b0f1f20cc6c42c2237321f247c5347d285bbb97601c7acf6dbed9054ca"

PREFERRED_SPACY_MODEL = "en_core_web_trf"
FALLBACK_SPACY_MODEL = "en_core_web_sm"

# ----------------------------------------
# UI Styling
# ----------------------------------------
st.markdown(
    """
    <style>
    .main, body, .block-container {background-color: #0d1117 !important; color: #e6edf3 !important;}
    .header-box {background: linear-gradient(90deg,#0f172a,#00264d); padding: 18px; border-radius: 10px; margin-bottom: 20px; color: #fff; border: 1px solid #174078;}
    .card {background:#161b22; padding:14px; border-radius:10px; border:1px solid #30363d; margin-bottom:12px;}
    .skill-pill {display:inline-block; padding:7px 12px; margin:6px 6px 6px 0; background:#21262d; color:#e6edf3; border-radius:18px; font-size:13px; border:1px solid #30363d;}
    .stFileUploader label {background:#1f6feb !important; color:white !important; padding:8px 12px !important; border-radius:8px !important; font-weight:600 !important;}
    .stFileUploader div[data-testid="stFileDropzone"]{background:#161b22 !important; border:2px dashed #30363d !important; color:#e6edf3 !important;}
    .stButton>button {background:linear-gradient(90deg,#2563eb,#3b82f6) !important; color:white !important; border-radius:10px !important; padding:10px 20px !important; font-weight:700 !important;}
    a {color:#58a6ff !important; font-weight:600;}
    h2,h3,h4 {color:#58a6ff !important;}
    div, span, p {color:#e6edf3 !important;}
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    "<div class='header-box'><h1 style='margin:0'>📄 HireSmart AI — Resume Parser</h1>"
    "<div style='color:#cfefff;margin-top:6px'>spaCy SkillNER + PhraseMatcher | ATS Score | Role Recommendations</div></div>",
    unsafe_allow_html=True
)

# ----------------------------------------
# Regex & Utilities
# ----------------------------------------
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', re.IGNORECASE)
PHONE_RE = re.compile(r'[0-9]{10,15}')

def clean_text_noise(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = html.unescape(text)
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', text)
    text = text.replace("##", "").replace("▁", " ")
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def read_pdf(file) -> str:
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        try:
            txt = page.extract_text()
            if txt:
                text += txt + "\n"
        except:
            continue
    return text

def read_docx(file) -> str:
    doc = docx.Document(file)
    return "\n".join([p.text for p in doc.paragraphs])

def read_uploaded(file) -> str:
    if not file:
        return ""
    name = file.name.lower()
    if name.endswith(".pdf"):
        return read_pdf(file)
    elif name.endswith(".docx"):
        return read_docx(file)
    else:
        raw = file.read()
        try:
            return raw.decode("utf-8")
        except:
            return str(raw)

def extract_email(text):
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None


# -------------------------------------------------------------
# ⭐ FIXED — BEST POSSIBLE NAME EXTRACTION (NO WRONG TECH WORDS)
# -------------------------------------------------------------
def extract_name_by_spacy(doc):
    TECH_BLACKLIST = {
        "java","python","html","css","javascript","frontend","backend",
        "developer","technologies","technology","fullstack","engineer",
        "react","angular","sql","aws","azure","machine","learning","html5"
    }

    # 1. Try PERSON entities
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            cand = ent.text.strip()
            words = cand.split()

            # Must be 2–4 alphabetic words
            if not (2 <= len(words) <= 4):
                continue
            if not all(w.replace(".", "").isalpha() for w in words):
                continue
            if any(w.lower() in TECH_BLACKLIST for w in words):
                continue

            return cand

    # 2. Fallback: first clean line
    lines = [l.strip() for l in doc.text.splitlines() if l.strip()]
    for line in lines[:5]:
        words = line.split()

        if not (2 <= len(words) <= 4):
            continue
        if not all(w.replace(".", "").isalpha() for w in words):
            continue
        if any(w.lower() in TECH_BLACKLIST for w in words):
            continue

        return line

    # 3. Fallback: from email prefix
    email = extract_email(doc.text)
    if email:
        prefix = email.split("@")[0].replace(".", " ").replace("_", " ")
        pw = [w for w in prefix.split() if w.isalpha()]
        if 2 <= len(pw) <= 4:
            return " ".join(w.capitalize() for w in pw)

    return "N/A"


# -------------------------------------------------------------
# ⭐ FIXED — BEST MOBILE NUMBER EXTRACTION (INDIA FOCUSED)
# -------------------------------------------------------------
def extract_phone(text):
    patterns = [
        r"\+91[\s\-]?[6-9]\d{9}",
        r"91[\s\-]?[6-9]\d{9}",
        r"[6-9]\d{9}",
        r"[6-9]\d{2}[\s\-]?\d{3}[\s\-]?\d{4}"
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            num = re.sub(r"\D", "", m.group(0))
            if len(num) >= 10:
                return num[-10:]
    return None


# ----------------------------------------
# Skills & Roles
# ----------------------------------------
SKILL_PHRASES = [
    "python","pandas","numpy","scikit-learn","tensorflow","keras","pytorch",
    "machine learning","deep learning","nlp","natural language processing",
    "data science","data analysis","sql","mysql","nosql","mongodb","spark","hadoop",
    "javascript","react","angular","vue","html","css","node","express","django","flask",
    "docker","kubernetes","aws","azure","gcp","terraform","jenkins","ci/cd",
    "android","ios","swift","kotlin","tableau","power bi","excel","git","github"
]

ROLE_SKILL_MAP = {
    "Data Scientist": ["python","pandas","numpy","machine learning","data science","nlp"],
    "Machine Learning Engineer": ["python","tensorflow","pytorch","keras","docker"],
    "Data Analyst": ["excel","sql","tableau","power bi","data analysis"],
    "Backend Developer": ["javascript","django","node","rest api","sql"],
    "Full Stack Developer": ["react","node","django","javascript","html","css"],
    "DevOps Engineer": ["docker","kubernetes","aws","ci/cd","terraform"],
    "Mobile Developer": ["android","ios","swift","kotlin"],
    "Product Manager": ["product","roadmap","stakeholder","analytics"],
    "Digital Marketer": ["seo","google analytics","content","social media"]
}

# ----------------------------------------
# Load spaCy + Matcher
# ----------------------------------------
@st.cache_resource(show_spinner=False)
def load_spacy_and_matcher():
    if not SPACY_AVAILABLE:
        return None, None
    nlp = None
    for model in (PREFERRED_SPACY_MODEL, FALLBACK_SPACY_MODEL):
        try:
            nlp = spacy.load(model)
            break
        except:
            continue
    if not nlp:
        raise RuntimeError("spaCy models not found. Install en_core_web_sm.")
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    matcher.add("SKILLS", [nlp.make_doc(s) for s in SKILL_PHRASES])
    return nlp, matcher

# ----------------------------------------
# Extract Skills
# ----------------------------------------
def extract_skills_from_text(spacy_nlp, matcher, text):
    text = clean_text_noise(text)
    try:
        doc = spacy_nlp(text)
    except:
        doc = spacy.blank("en")(text)

    skills_found = set()
    matches = matcher(doc)
    for _, start, end in matches:
        span = doc[start:end]
        skills_found.add(span.text.lower())

    token_counts = Counter([t.text.lower() for t in doc if t.is_alpha])
    for sk in SKILL_PHRASES:
        if sk.lower() in token_counts:
            skills_found.add(sk.lower())

    skills_cleaned = sorted(skills_found)
    return skills_cleaned, doc

# ----------------------------------------
# Role Scoring
# ----------------------------------------
def score_roles_from_skills(skills):
    sset = set(skills)
    scores = {}
    for role, triggers in ROLE_SKILL_MAP.items():
        tset = set(triggers)
        matched = sum(1 for t in tset if t in sset)
        scores[role] = round((matched / len(tset)) * 100, 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

# ----------------------------------------
# ATS Score
# ----------------------------------------
ATS_KEYWORDS = [
    "experience","project","projects","internship","certification","responsibilities",
    "achievements","skills","education","summary","objective","github","linkedin"
]

def calculate_ats_score(text, skills, has_email, has_phone):
    t = text.lower()
    score = 0
    score += min(len(skills) * 6, 40)
    score += min(sum(1 for k in ATS_KEYWORDS if k in t) * 3, 30)

    lines = [l for l in text.splitlines() if l.strip()]
    formatting = 10
    if len(lines) >= 8: formatting += 6
    if len(text) >= 500: formatting += 4
    score += min(formatting, 20)

    if has_email: score += 5
    if has_phone: score += 5

    return min(round(score, 1), 100.0)

# ----------------------------------------
# SerpAPI Job Fetch
# ----------------------------------------
def serpapi_job_search(role, num=5, location="India"):
    if not SERPAPI_KEY:
        return []
    try:
        params = {"engine": "google", "q": f"{role} jobs in {location}", "num": num, "api_key": SERPAPI_KEY}
        r = requests.get("https://serpapi.com/search", params=params)
        data = r.json()
        jobs = []
        for j in data.get("organic_results", [])[:num]:
            jobs.append({
                "title": j.get("title"),
                "snippet": j.get("snippet"),
                "link": j.get("link")
            })
        return jobs
    except:
        return []

# ----------------------------------------
# UI Inputs
# ----------------------------------------
col1, col2 = st.columns([2,1])
with col1:
    st.subheader("📤 Upload Resume (PDF / DOCX / TXT)")
    uploaded_file = st.file_uploader("Choose a resume file", type=["pdf","docx","txt"])
    pasted = st.text_area("Or paste resume text here", height=240)

with col2:
    st.subheader("⚙️ Options")
    try:
        snlp, smatcher = load_spacy_and_matcher()
        st.success("spaCy model loaded")
    except:
        st.error("spaCy model not found")
    if SERPAPI_KEY:
        st.success("SerpAPI configured")
    else:
        st.warning("SerpAPI not configured")

resume_text = ""
if uploaded_file:
    resume_text = read_uploaded(uploaded_file)
elif pasted:
    resume_text = pasted

# ----------------------------------------
# Analyze
# ----------------------------------------
if st.button("Analyze Resume"):
    if not resume_text.strip():
        st.error("Please upload or paste a resume.")
    else:
        resume_text = clean_text_noise(resume_text)

        nlp, matcher = load_spacy_and_matcher()

        skills, doc = extract_skills_from_text(nlp, matcher, resume_text)
        name = extract_name_by_spacy(doc)
        email = extract_email(resume_text)
        phone = extract_phone(resume_text)

        role_scores = score_roles_from_skills(skills)
        ats = calculate_ats_score(resume_text, skills, bool(email), bool(phone))

        # Summary
        st.markdown("## 🧾 Parsed Resume Summary")
        st.markdown(
            f"<div class='card'><b>Name:</b> {name} &nbsp;&nbsp; "
            f"<b>Email:</b> {email} &nbsp;&nbsp; "
            f"<b>Phone:</b> {phone}</div>", 
            unsafe_allow_html=True
        )

        # ATS
        if ats >= 80:
            color = "#00ff66"; remark = "Excellent — ATS Friendly"
        elif ats >= 60:
            color = "#ffcc00"; remark = "Moderate — Improve for ATS"
        else:
            color = "#ff4d4f"; remark = "Low — Needs Improvement"

        st.markdown(
            f"<div class='card' style='border-left:6px solid {color};'>"
            f"<h3 style='color:{color};'>ATS Score: {ats}</h3>"
            f"{remark}</div>",
            unsafe_allow_html=True
        )

        # Skills
        st.markdown("### 🔎 Extracted Skills")
        st.markdown(
            f"<div class='card'>{''.join([f'<span class=skill-pill>{s}</span>' for s in skills])}</div>",
            unsafe_allow_html=True
        )

        # Roles
        st.markdown("### 🎯 Recommended Roles")
        for role, score in role_scores[:5]:
            st.markdown(f"<div class='card'><b>{role}</b> — {score}%</div>", unsafe_allow_html=True)

        # Jobs
        if SERPAPI_KEY:
            st.markdown("### 🌐 Live Job Openings")
            for role, score in role_scores[:3]:
                st.markdown(f"#### 🔍 {role}")
                jobs = serpapi_job_search(role)
                for j in jobs:
                    st.markdown(
                        f"<div class='card'><b>{j['title']}</b><br>{j['snippet']}<br>"
                        f"<a href='{j['link']}' target='_blank'>Apply Here</a></div>",
                        unsafe_allow_html=True
                    )

st.markdown("---")
st.markdown("**HireSmart AI — spaCy Resume Parser | ATS | Roles | Jobs**")
