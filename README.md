# ResumeAI – AI Resume Analyzer

A full-stack resume analyzer built with **Python / Flask**, **MySQL**, **Claude AI** and **Groq API**

---

## Project Structure

```
resume_analyzer/
├── app.py                  # Flask app + MySQL + Claude API
├── requirements.txt
├── templates/
│   ├── index.html          # Upload page + results
│   └── history.html        # Past analyses table + detail modal
└── static/
    ├── css/style.css       # All styling
    └── js/main.js          # Drag-drop, form submit, results render
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure MySQL

Edit the `DB_CONFIG` block in `app.py`, or set environment variables:

```bash
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=yourpassword
export MYSQL_DB=resume_analyzer
```

The app will **auto-create** the `resume_analyzer` database and `analyse` table on first run.

### 3. Set your Anthropic (or your favourite) API key

The `/analyze` route calls `https://api.anthropic.com/v1/messages`.  
Make sure your server/proxy has the `x-api-key` header handled, or add it to the `requests.post` headers in `app.py`:

```python
headers={
    'Content-Type': 'application/json',
    'x-api-key': 'sk-ant-...',
    'anthropic-version': '2023-06-01',
},
```

### 4. Run

```bash
python app.py
```

Visit **http://localhost:5000**

---

## MySQL Schema

```sql
CREATE TABLE analyses (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    filename   VARCHAR(255)  NOT NULL,
    job_role   VARCHAR(255),
    score      INT,
    summary    TEXT,
    strengths  TEXT,
    gaps       TEXT,
    tips       TEXT,
    keywords   TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## Features

| Feature | Detail |
|---|---|
| Upload | PDF, DOCX, TXT (max 10 MB) |
| Drag & drop | Full drop-zone UI |
| AI analysis | Score 0-100, summary, strengths, gaps, tips, keywords |
| Target role | Optional job-role context for tailored feedback |
| MySQL storage | Every analysis saved; viewable in History |
| Delete | Remove individual analyses from History |
| Modal detail | Click "View" in History to see full breakdown |
