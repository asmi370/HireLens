HireLens AI — Streamlit Resume Parser (spaCy SkillNER + PhraseMatcher)
  HireLens is an AI-based Resume Parser and Job Matching System built using Machine Learning and NLP.


Features:
 - Upload resume (pdf/docx/txt) or paste text
 - Extract name, email, phone, skills (phrase-matching + spaCy entities)
 - Compute ATS score
 - Recommend best matching roles (heuristic)
 - Optional live job fetch via SerpAPI (set SERPAPI_KEY below)

## 🛠 Tech Stack
- Python
- Streamlit
- spaCy (NLP)
- Regex
- PyPDF2
- python-docx
- Requests (API integration)

## ▶️ How to Run
1. Install dependencies:
   pip install -r requirements.txt

2. Run the project:
   resume_parcer.py

## 📌 Future Improvements
- Add web interface
- Improve accuracy
- Deploy online
