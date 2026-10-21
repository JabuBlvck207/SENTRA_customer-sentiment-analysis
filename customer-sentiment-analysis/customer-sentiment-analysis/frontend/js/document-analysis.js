/* Document upload and analysis */

let selectedFile = null;

document.addEventListener('DOMContentLoaded', () => {
  const zone = document.getElementById('uploadZone');
  const input = document.getElementById('fileInput');
  if (!zone || !input) return;

  zone.addEventListener('click', (e) => {
    if (e.target.tagName !== 'LABEL' && e.target.tagName !== 'INPUT') {
      input.click();
    }
  });

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('dragover');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  });

  input.addEventListener('change', () => {
    if (input.files.length) handleFileSelect(input.files[0]);
  });

  document.getElementById('removeFileBtn')?.addEventListener('click', clearSelectedFile);
  document.getElementById('uploadAnalyseBtn')?.addEventListener('click', uploadAndAnalyse);
});

function handleFileSelect(file) {
  const allowed = ['application/pdf', 'text/plain'];
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'txt'].includes(ext) && !allowed.includes(file.type)) {
    showDocError('Unsupported file type. Only PDF and TXT are accepted.');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showDocError('File exceeds the 10 MB size limit.');
    return;
  }
  selectedFile = file;
  document.getElementById('fileName').textContent = file.name;
  document.getElementById('fileSize').textContent = formatBytes(file.size);
  document.getElementById('selectedFile').classList.remove('hidden');
  document.getElementById('uploadAnalyseBtn').disabled = false;
  hideDocError();
  if (window.lucide) lucide.createIcons();
}

function clearSelectedFile() {
  selectedFile = null;
  document.getElementById('fileInput').value = '';
  document.getElementById('selectedFile').classList.add('hidden');
  document.getElementById('uploadAnalyseBtn').disabled = true;
}

function showDocError(msg) {
  const el = document.getElementById('docError');
  el.textContent = msg;
  el.classList.remove('hidden');
}
function hideDocError() {
  document.getElementById('docError').classList.add('hidden');
}

async function uploadAndAnalyse() {
  if (!selectedFile) return;

  const loading = document.getElementById('docLoading');
  const loadingText = document.getElementById('docLoadingText');
  const btn = document.getElementById('uploadAnalyseBtn');
  const reportCard = document.getElementById('docReportCard');

  hideDocError();
  reportCard.style.display = 'none';
  loading.classList.remove('hidden');
  btn.disabled = true;
  loadingText.textContent = 'Uploading…';

  try {
    // 1. Upload
    const form = new FormData();
    form.append('file', selectedFile);
    const uploadRes = await api('/documents/upload', {
      method: 'POST',
      body: form,
      headers: {}, // let browser set multipart boundary
    });

    const docId = uploadRes.document.id;
    loadingText.textContent = 'Extracting text and analysing with AI… This may take a moment.';

    // 2. Analyse
    const analyseRes = await api(`/documents/${docId}/analyze`, { method: 'POST' });

    renderDocumentReport(analyseRes);
    reportCard.style.display = 'block';
    clearSelectedFile();
    loadDocumentsList();
  } catch (e) {
    showDocError(e.message || 'Upload or analysis failed.');
  } finally {
    loading.classList.add('hidden');
    btn.disabled = !selectedFile;
  }
}

function renderDocumentReport(data) {
  const el = document.getElementById('docReportContent');
  const doc = data.document || {};
  const report = data.report || {};
  const counts = data.sentiment_counts || {
    Positive: doc.positive_count || 0,
    Negative: doc.negative_count || 0,
    Neutral: doc.neutral_count || 0,
  };
  const total = data.feedback_count || doc.total_feedback_items || 0;

  let complaintsHtml = '';
  if (report.common_complaints?.length) {
    complaintsHtml = `<h4 style="margin-top:1.25rem">Common Complaints</h4>
      <ul class="complaint-list">${
        report.common_complaints.map(c =>
          `<li><span>${escapeHtml(c.category)}</span><span class="complaint-count">${c.count}</span></li>`
        ).join('')
      }</ul>`;
  }

  let themesHtml = '';
  if (report.positive_themes?.length) {
    themesHtml = `<h4 style="margin-top:1.25rem">Positive Themes</h4>
      <ul class="complaint-list">${
        report.positive_themes.map(t =>
          `<li><span>${escapeHtml(t.theme)}</span><span class="complaint-count">${t.count}</span></li>`
        ).join('')
      }</ul>`;
  }

  let recsHtml = '';
  if (report.recommended_improvements?.length) {
    recsHtml = `<h4 style="margin-top:1.25rem">Recommended Improvements <small style="font-weight:400;text-transform:none;color:var(--text-muted)">(AI-generated)</small></h4>
      <ul style="padding-left:1.2rem;font-size:0.9rem">${
        report.recommended_improvements.map(r => `<li style="margin-bottom:0.35rem">${escapeHtml(r)}</li>`).join('')
      }</ul>`;
  }

  el.innerHTML = `
    <p style="font-size:0.92rem;margin-bottom:0.5rem">
      <strong>${escapeHtml(doc.original_filename || 'Document')}</strong>
      <span class="status-pill ${doc.processing_status || 'completed'}" style="margin-left:0.5rem">${escapeHtml(doc.processing_status || 'completed')}</span>
    </p>
    <p style="font-size:0.85rem;color:var(--text-secondary)">${escapeHtml(report.overall_sentiment_summary || '')}</p>
    <div class="report-summary">
      <div class="report-stat"><span class="val">${total}</span><span class="lbl">Segments analysed</span></div>
      <div class="report-stat"><span class="val" style="color:var(--green)">${counts.Positive || 0}</span><span class="lbl">Positive</span></div>
      <div class="report-stat"><span class="val" style="color:var(--red)">${counts.Negative || 0}</span><span class="lbl">Negative</span></div>
      <div class="report-stat"><span class="val" style="color:var(--amber)">${counts.Neutral || 0}</span><span class="lbl">Neutral</span></div>
    </div>
    ${complaintsHtml}
    ${themesHtml}
    ${recsHtml}
  `;
}

async function loadDocumentsList() {
  const el = document.getElementById('documentsList');
  if (!el) return;
  try {
    const data = await api('/documents?per_page=50');
    const items = data.items || [];
    if (!items.length) {
      el.innerHTML = '<p class="empty-state">No documents uploaded yet.</p>';
      return;
    }
    el.innerHTML = items.map(d => `
      <div class="doc-item">
        <div class="doc-icon"><i data-lucide="file-text"></i></div>
        <div class="doc-body">
          <div class="doc-name">${escapeHtml(d.original_filename)}</div>
          <div class="doc-meta">
            <span class="status-pill ${d.processing_status}">${escapeHtml(d.processing_status)}</span>
            <span>${formatBytes(d.file_size || 0)}</span>
            <span>${formatDate(d.upload_timestamp)}</span>
            ${d.total_feedback_items ? `<span>${d.total_feedback_items} items</span>` : ''}
          </div>
        </div>
        <div class="doc-actions">
          ${d.processing_status === 'completed' ? `<button class="btn btn-ghost" onclick="viewDocument(${d.id})" style="padding:0.35rem 0.7rem;font-size:0.82rem">View</button>` : ''}
          ${d.processing_status === 'pending' || d.processing_status === 'failed' ? `<button class="btn btn-primary" onclick="reanalyseDocument(${d.id})" style="padding:0.35rem 0.7rem;font-size:0.82rem">Analyse</button>` : ''}
          <button class="btn-icon" onclick="deleteDocument(${d.id})" title="Delete"><i data-lucide="trash-2"></i></button>
        </div>
      </div>
    `).join('');
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    el.innerHTML = `<p class="empty-state">Failed to load documents: ${escapeHtml(e.message)}</p>`;
  }
}

async function viewDocument(id) {
  try {
    const data = await api(`/documents/${id}`);
    const reportCard = document.getElementById('docReportCard');
    renderDocumentReport({
      document: data.document,
      report: data.report,
      feedback_count: data.document?.total_feedback_items,
      sentiment_counts: {
        Positive: data.document?.positive_count || 0,
        Negative: data.document?.negative_count || 0,
        Neutral: data.document?.neutral_count || 0,
      },
    });
    reportCard.style.display = 'block';
    reportCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    showDocError(e.message);
  }
}

async function reanalyseDocument(id) {
  const loading = document.getElementById('docLoading');
  const loadingText = document.getElementById('docLoadingText');
  hideDocError();
  loading.classList.remove('hidden');
  loadingText.textContent = 'Analysing document…';
  try {
    // Reset status by re-calling analyse (backend allows if not completed, or we force)
    // First set status – the endpoint handles pending/failed
    const res = await api(`/documents/${id}/analyze`, { method: 'POST' });
    renderDocumentReport(res);
    document.getElementById('docReportCard').style.display = 'block';
    loadDocumentsList();
  } catch (e) {
    showDocError(e.message);
  } finally {
    loading.classList.add('hidden');
  }
}

async function deleteDocument(id) {
  if (!confirm('Delete this document and all associated feedback records?')) return;
  try {
    await api(`/documents/${id}`, { method: 'DELETE' });
    loadDocumentsList();
    document.getElementById('docReportCard').style.display = 'none';
  } catch (e) {
    showDocError(e.message);
  }
}
