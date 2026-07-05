import os
import json
import pdfplumber
import requests
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, redirect, url_for
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.config['SECRET_KEY'] = 'resume-analyzer-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

# ─── MySQL Config ────────────────────────────────────────────────
# Edit these values to match your MySQL server
DB_CONFIG = {
    'host':     os.environ.get('MYSQL_HOST'),
    'port':     int(os.environ.get('MYSQL_PORT')),
    'user':     os.environ.get('MYSQL_USER'),
    'password': os.environ.get('MYSQL_PASSWORD'),
    'database': os.environ.get('MYSQL_DB'),
}

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

# ─── DB helpers ─────────────────────────────────────────────────
def get_connection():
    """Open a new MySQL connection."""
    return mysql.connector.connect(**DB_CONFIG)

def init_db():
    """Create the database and the analyses table if they don't exist."""
    # Connect without specifying a database first so we can CREATE it
    cfg = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
    conn = mysql.connector.connect(**cfg)
    cur  = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`")
    cur.execute(f"USE `{DB_CONFIG['database']}`")
    cur.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
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
    ''')
    conn.commit()
    cur.close()
    conn.close()

# ─── Utilities ──────────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(filepath):
    ext  = filepath.rsplit('.', 1)[1].lower()
    text = ''
    if ext == 'pdf':
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + '\n'
    elif ext == 'docx':
        from docx import Document
        doc  = Document(filepath)
        text = '\n'.join(p.text for p in doc.paragraphs)
    elif ext == 'txt':
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    return text.strip()

def analyze_with_groq(resume_text, job_role):
    """Send resume to Groq API and return a structured dict."""
    
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not set. Add it to your .env file: GROQ_API_KEY=your-api-key"
        )
    
    # Groq API endpoint
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    
    job_context = f"for the role of **{job_role}**" if job_role else "for general job applications"
    prompt = f"""You are an expert resume coach and HR professional.
Analyze the resume below {job_context}.
 
Return ONLY a valid JSON object - no markdown, no extra text - with exactly these keys:
{{
  "score": <integer 0-100>,
  "summary": "<2-3 sentence overall assessment>",
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "gaps": ["<gap 1>", "<gap 2>", "<gap 3>"],
  "tips": ["<actionable tip 1>", "<tip 2>", "<tip 3>", "<tip 4>"],
  "keywords": ["<keyword 1>", "<keyword 2>", "<keyword 3>", "<keyword 4>", "<keyword 5>"]
}}
 
RESUME:
{resume_text[:4000]}"""
    
    try:
        response = requests.post(
            GROQ_URL,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            json={
                'model': 'llama-3.1-8b-instant',  # or 'llama-3.3-70b-versatile', 'mixtral-8x7b-32768'
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 1000,
            },
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Groq API. Check your internet connection.")
    
    data = response.json()
    
    # ── Catch API-level errors (auth failure, rate limit, etc.) ──
    if response.status_code != 200:
        error_msg = data.get('error', {}).get('message', 'Unknown API error')
        raise RuntimeError(f"Groq API error ({response.status_code}): {error_msg}")
    
    # Extract content from Groq response format (same as OpenAI)
    choices = data.get('choices', [])
    if not choices:
        raise RuntimeError(f"Unexpected API response: {json.dumps(data)}")
    
    message = choices[0].get('message', {})
    if 'content' not in message or not message['content']:
        raise RuntimeError(f"Unexpected API response: {json.dumps(data)}")
    
    raw = message['content'].strip()
    
    # Strip accidental markdown fences
    if raw.startswith('```'):
        parts = raw.split('```')
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith('json'):
            raw = raw[4:]
    
    return json.loads(raw.strip())

# ─── Routes ─────────────────────────────────────────────────────
@app.route('/')
def index():
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM analyses ORDER BY id DESC LIMIT 5')
    recent = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', recent=recent)

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file     = request.files['resume']
    job_role = request.form.get('job_role', '').strip()

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file type. Use PDF, DOCX, or TXT'}), 400

    filename = secure_filename(file.filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        resume_text = extract_text(filepath)
        if not resume_text:
            return jsonify({'error': 'Could not extract text from the file'}), 400

        result = analyze_with_groq(resume_text, job_role)

        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO analyses
               (filename, job_role, score, summary, strengths, gaps, tips, keywords)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
            (
                filename,
                job_role or None,
                result['score'],
                result['summary'],
                json.dumps(result['strengths']),
                json.dumps(result['gaps']),
                json.dumps(result['tips']),
                json.dumps(result['keywords']),
            )
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'result': result, 'filename': filename})

    except json.JSONDecodeError:
        return jsonify({'error': 'AI returned unexpected format. Please try again.'}), 500
    except Error as db_err:
        return jsonify({'error': f'Database error: {db_err}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

@app.route('/history')
def history():
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM analyses ORDER BY id DESC')
    analyses = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('history.html', analyses=analyses)

@app.route('/delete/<int:analysis_id>', methods=['POST'])
def delete_analysis(analysis_id):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM analyses WHERE id = %s', (analysis_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('history'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)