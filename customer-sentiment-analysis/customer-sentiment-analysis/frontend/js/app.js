/* Core application logic – navigation, health, shared utilities */

const API = '/api';

const SECTIONS = {
  overview:  { title: 'Overview',            desc: 'Dashboard overview of customer sentiment analytics' },
  analyse:   { title: 'Analyse Feedback',    desc: 'Classify individual customer comments with AI' },
  documents: { title: 'Document Analysis',   desc: 'Upload and analyse PDF or TXT feedback documents' },
  history:   { title: 'Feedback History',    desc: 'Search and review previously analysed feedback' },
  insights:  { title: 'Customer Insights',   desc: 'Recurring themes, complaints and improvement areas' },
  settings:  { title: 'Settings',            desc: 'Application configuration and service status' },
};

/* ---------- Navigation ---------- */
function navigate(section) {
  if (!SECTIONS[section]) section = 'overview';

  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  const el = document.getElementById(`section-${section}`);
  if (el) el.classList.add('active');

  document.querySelectorAll('.nav-item').forEach(n => {
    n.classList.toggle('active', n.dataset.section === section);
  });

  document.getElementById('pageTitle').textContent = SECTIONS[section].title;
  document.getElementById('pageDesc').textContent = SECTIONS[section].desc;

  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('open');

  // Load section data
  if (section === 'overview') loadDashboard();
  if (section === 'documents') loadDocumentsList();
  if (section === 'history') loadHistory();
  if (section === 'insights') loadInsights();
  if (section === 'settings') loadSettings();

  history.replaceState(null, '', `#${section}`);
}

/* ---------- API helpers ---------- */
async function api(path, options = {}) {
  const opts = {
    headers: { 'Accept': 'application/json', ...options.headers },
    ...options,
  };
  if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(`${API}${path}`, opts);
  let data;
  try {
    data = await res.json();
  } catch {
    data = { success: false, error: `Server returned ${res.status}` };
  }
  if (!res.ok) {
    const err = new Error(data.error || `Request failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function sentimentClass(s) {
  if (!s) return 'neutral';
  return s.toLowerCase();
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ---------- Health check ---------- */
async function checkHealth() {
  const el = document.getElementById('serviceStatus');
  try {
    const data = await api('/health');
    const available = data.ai_service && data.ai_service.available;
    el.className = 'service-status ' + (available ? 'online' : 'offline');
    el.querySelector('.status-text').textContent = available
      ? 'AI service online'
      : (data.ai_service?.message || 'AI service offline');
    return data;
  } catch {
    el.className = 'service-status offline';
    el.querySelector('.status-text').textContent = 'Server unreachable';
    return null;
  }
}

/* ---------- Settings ---------- */
async function loadSettings() {
  const data = await checkHealth();
  document.getElementById('settingsAiStatus').textContent =
    data?.ai_service?.available ? 'Available' : (data?.ai_service?.message || 'Unavailable');
  document.getElementById('settingsModel').textContent =
    data?.model || data?.ai_service?.model || 'Not configured';
}

/* ---------- Init ---------- */
document.addEventListener('DOMContentLoaded', () => {
  // Lucide icons
  if (window.lucide) lucide.createIcons();

  // Nav clicks
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      navigate(item.dataset.section);
    });
  });

  // Mobile menu
  document.getElementById('menuToggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.add('open');
    document.getElementById('sidebarOverlay').classList.add('open');
  });
  document.getElementById('sidebarClose').addEventListener('click', () => {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebarOverlay').classList.remove('open');
  });
  document.getElementById('sidebarOverlay').addEventListener('click', () => {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebarOverlay').classList.remove('open');
  });

  // Refresh
  document.getElementById('refreshBtn').addEventListener('click', () => {
    const active = document.querySelector('.nav-item.active');
    navigate(active ? active.dataset.section : 'overview');
    checkHealth();
  });

  // Character counter
  const input = document.getElementById('feedbackInput');
  if (input) {
    input.addEventListener('input', () => {
      document.getElementById('charCount').textContent = input.value.length;
    });
  }

  // Analyse feedback
  document.getElementById('analyseBtn')?.addEventListener('click', analyseIndividual);
  document.getElementById('clearFeedbackBtn')?.addEventListener('click', () => {
    document.getElementById('feedbackInput').value = '';
    document.getElementById('charCount').textContent = '0';
    document.getElementById('analyseResult').classList.add('hidden');
    document.getElementById('analyseError').classList.add('hidden');
  });

  // Hash routing
  const hash = location.hash.replace('#', '') || 'overview';
  navigate(hash);
  checkHealth();
});

/* ---------- Individual analysis ---------- */
async function analyseIndividual() {
  const text = document.getElementById('feedbackInput').value.trim();
  const errEl = document.getElementById('analyseError');
  const resultEl = document.getElementById('analyseResult');
  const loading = document.getElementById('analyseLoading');
  const btn = document.getElementById('analyseBtn');

  errEl.classList.add('hidden');
  resultEl.classList.add('hidden');

  if (!text) {
    errEl.textContent = 'Please enter some feedback text.';
    errEl.classList.remove('hidden');
    return;
  }

  loading.classList.remove('hidden');
  btn.disabled = true;

  try {
    const data = await api('/analyze', { method: 'POST', body: { text } });
    renderAnalysisResult(data.analysis, data.record);
    resultEl.classList.remove('hidden');
  } catch (e) {
    errEl.textContent = e.message || 'Analysis failed.';
    errEl.classList.remove('hidden');
  } finally {
    loading.classList.add('hidden');
    btn.disabled = false;
  }
}

function renderAnalysisResult(analysis, record) {
  const el = document.getElementById('analyseResult');
  const s = analysis.sentiment || 'Neutral';
  const cls = sentimentClass(s);

  let keywordsHtml = '';
  if (analysis.keywords && analysis.keywords.length) {
    keywordsHtml = `<h4>Keywords</h4><div class="tag-list">${
      analysis.keywords.map(k => `<span class="tag">${escapeHtml(k)}</span>`).join('')
    }</div>`;
  }

  let complaintsHtml = '';
  if (analysis.complaint_categories && analysis.complaint_categories.length) {
    complaintsHtml = `<h4>Complaint Categories</h4><div class="tag-list">${
      analysis.complaint_categories.map(c => `<span class="tag complaint">${escapeHtml(c)}</span>`).join('')
    }</div>`;
  }

  let actionHtml = '';
  if (analysis.suggested_action) {
    actionHtml = `<h4>Suggested Action <small style="font-weight:400;text-transform:none;letter-spacing:0;color:var(--text-muted)">(AI-generated)</small></h4>
      <p>${escapeHtml(analysis.suggested_action)}</p>`;
  }

  let confidenceHtml = '';
  if (analysis.confidence != null) {
    confidenceHtml = `<h4>Confidence</h4><p>${(analysis.confidence * 100).toFixed(0)}%</p>`;
  }

  el.innerHTML = `
    <div class="result-header">
      <span class="sentiment-badge ${cls}">${escapeHtml(s)}</span>
      <span style="font-size:0.82rem;color:var(--text-muted)">${record ? formatDate(record.created_at) : ''}</span>
    </div>
    <div class="result-body">
      <h4>Original Feedback</h4>
      <div class="original-text">${escapeHtml(analysis.original_text || '')}</div>
      <h4>Explanation</h4>
      <p>${escapeHtml(analysis.explanation || '—')}</p>
      ${confidenceHtml}
      ${keywordsHtml}
      ${complaintsHtml}
      ${actionHtml}
    </div>
  `;
  if (window.lucide) lucide.createIcons();
}
