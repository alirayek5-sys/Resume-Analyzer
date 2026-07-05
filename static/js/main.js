/* ─── ResumeAI – main.js ───────────────────────────────────────── */

const dropZone    = document.getElementById('dropZone');
const fileInput   = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const fileName    = document.getElementById('fileName');
const fileSize    = document.getElementById('fileSize');
const clearFile   = document.getElementById('clearFile');
const submitBtn   = document.getElementById('submitBtn');
const analyzeForm = document.getElementById('analyzeForm');

// ─── Drag & Drop ────────────────────────────────────────────────
if (dropZone) {
  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  ['dragleave', 'dragend'].forEach(evt =>
    dropZone.addEventListener(evt, () => dropZone.classList.remove('drag-over'))
  );

  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) setFile(file);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) setFile(fileInput.files[0]);
  });

  clearFile?.addEventListener('click', resetFile);
}

function setFile(file) {
  const allowed = ['application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain'];
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf','docx','txt'].includes(ext)) {
    alert('Please upload a PDF, DOCX, or TXT file.');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    alert('File exceeds 10 MB limit.');
    return;
  }

  // Attach to the hidden input via DataTransfer
  const dt = new DataTransfer();
  dt.items.add(file);
  fileInput.files = dt.files;

  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  dropZone.classList.add('hidden');
  filePreview.classList.remove('hidden');
  submitBtn.disabled = false;
}

function resetFile() {
  fileInput.value = '';
  dropZone.classList.remove('hidden');
  filePreview.classList.add('hidden');
  submitBtn.disabled = true;
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ─── Form Submit ─────────────────────────────────────────────────
analyzeForm?.addEventListener('submit', async e => {
  e.preventDefault();

  if (!fileInput.files[0]) {
    alert('Please select a resume file first.');
    return;
  }

  // Show spinner
  submitBtn.querySelector('.btn-text').classList.add('hidden');
  submitBtn.querySelector('.btn-spinner').classList.remove('hidden');
  submitBtn.disabled = true;

  const formData = new FormData(analyzeForm);

  try {
    const res  = await fetch('/analyze', { method: 'POST', body: formData });
    const data = await res.json();

    if (data.error) {
      alert('Error: ' + data.error);
      return;
    }

    renderResults(data.result, data.filename);
  } catch (err) {
    alert('Something went wrong. Please try again.');
    console.error(err);
  } finally {
    submitBtn.querySelector('.btn-text').classList.remove('hidden');
    submitBtn.querySelector('.btn-spinner').classList.add('hidden');
    submitBtn.disabled = false;
  }
});

// ─── Render Results ──────────────────────────────────────────────
function renderResults(result, filename) {
  document.getElementById('analyzedFile').textContent = `File: ${filename}`;
  document.getElementById('scoreNum').textContent     = result.score;
  document.getElementById('summaryText').textContent  = result.summary;

  // Animate ring
  setRing('ringFill', result.score);

  // Lists
  fillList('strengthsList', result.strengths);
  fillList('gapsList',      result.gaps);
  fillList('tipsList',      result.tips);

  // Keywords
  const cloud = document.getElementById('keywordsCloud');
  cloud.innerHTML = '';
  (result.keywords || []).forEach(kw => {
    const span = document.createElement('span');
    span.className   = 'keyword-tag';
    span.textContent = kw;
    cloud.appendChild(span);
  });

  // Show & scroll
  const section = document.getElementById('resultsSection');
  section.classList.remove('hidden');
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function fillList(id, items) {
  const ul = document.getElementById(id);
  ul.innerHTML = '';
  (items || []).forEach(text => {
    const li = document.createElement('li');
    li.textContent = text;
    ul.appendChild(li);
  });
}

// ─── Score Ring ──────────────────────────────────────────────────
function setRing(id, score) {
  const circumference = 2 * Math.PI * 50; // r=50
  const fill = document.getElementById(id);
  if (!fill) return;

  // Color by score
  if (score >= 75)      fill.style.stroke = '#22c55e';
  else if (score >= 50) fill.style.stroke = '#f59e0b';
  else                  fill.style.stroke = '#ef4444';

  // Animate after a tick so CSS transition fires
  requestAnimationFrame(() => {
    const offset = circumference - (score / 100) * circumference;
    fill.style.strokeDashoffset = offset;
  });
}

// ─── Reset ───────────────────────────────────────────────────────
function resetForm() {
  resetFile();
  document.getElementById('resultsSection').classList.add('hidden');
  document.getElementById('jobRole').value = '';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
