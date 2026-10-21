/* Feedback history and insights */

let historyPage = 1;

async function loadHistory(page = 1) {
  historyPage = page;
  const search = document.getElementById('historySearch')?.value || '';
  const sentiment = document.getElementById('historySentiment')?.value || '';
  const source = document.getElementById('historySource')?.value || '';

  const params = new URLSearchParams({ page, per_page: 15 });
  if (search) params.set('search', search);
  if (sentiment) params.set('sentiment', sentiment);
  if (source) params.set('source_type', source);

  const el = document.getElementById('historyList');
  const pagEl = document.getElementById('historyPagination');

  try {
    const data = await api('/feedback?' + params.toString());
    const items = data.items || [];

    if (!items.length) {
      el.innerHTML = '<p class="empty-state">No feedback records match your filters.</p>';
      pagEl.innerHTML = '';
      return;
    }

    el.innerHTML = items.map(f => {
      const cls = sentimentClass(f.sentiment);
      const excerpt = (f.feedback_text || '').slice(0, 160) + ((f.feedback_text || '').length > 160 ? '…' : '');
      return `
        <div class="hist-item" style="cursor:pointer" onclick="showHistoryDetail(${f.id})">
          <div class="hist-icon"><i data-lucide="message-circle"></i></div>
          <div class="hist-body">
            <div class="hist-text">${escapeHtml(excerpt)}</div>
            <div class="hist-meta">
              <span class="sentiment-badge ${cls}" style="font-size:0.75rem;padding:0.15rem 0.5rem">${escapeHtml(f.sentiment)}</span>
              <span>${f.source_type === 'document' ? 'Document' : 'Manual'}</span>
              ${f.document_name ? `<span>${escapeHtml(f.document_name)}</span>` : ''}
              <span>${formatDate(f.created_at)}</span>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Pagination
    const pages = data.pages || 1;
    if (pages <= 1) {
      pagEl.innerHTML = '';
    } else {
      let html = '';
      html += `<button ${page <= 1 ? 'disabled' : ''} onclick="loadHistory(${page - 1})">‹</button>`;
      for (let i = 1; i <= pages && i <= 10; i++) {
        html += `<button class="${i === page ? 'active' : ''}" onclick="loadHistory(${i})">${i}</button>`;
      }
      if (pages > 10) html += `<span style="padding:0 0.4rem;color:var(--text-muted)">…</span>`;
      html += `<button ${page >= pages ? 'disabled' : ''} onclick="loadHistory(${page + 1})">›</button>`;
      pagEl.innerHTML = html;
    }

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    el.innerHTML = `<p class="empty-state">Failed to load history: ${escapeHtml(e.message)}</p>`;
  }
}

async function showHistoryDetail(id) {
  try {
    const data = await api(`/feedback/${id}`);
    const f = data.feedback;
    const card = document.getElementById('historyDetailCard');
    const el = document.getElementById('historyDetail');
    const cls = sentimentClass(f.sentiment);

    let keywords = '';
    if (f.keywords?.length) {
      keywords = `<h4>Keywords</h4><div class="tag-list">${f.keywords.map(k => `<span class="tag">${escapeHtml(k)}</span>`).join('')}</div>`;
    }
    let cats = '';
    if (f.complaint_categories?.length) {
      cats = `<h4>Complaint Categories</h4><div class="tag-list">${f.complaint_categories.map(c => `<span class="tag complaint">${escapeHtml(c)}</span>`).join('')}</div>`;
    }
    let action = '';
    if (f.suggested_action) {
      action = `<h4>Suggested Action <small style="font-weight:400;text-transform:none;color:var(--text-muted)">(AI-generated)</small></h4><p>${escapeHtml(f.suggested_action)}</p>`;
    }

    el.innerHTML = `
      <div class="result-header" style="border:none;padding:0 0 0.75rem">
        <span class="sentiment-badge ${cls}">${escapeHtml(f.sentiment)}</span>
        <span style="font-size:0.82rem;color:var(--text-muted)">${formatDate(f.created_at)}</span>
      </div>
      <div class="result-body" style="padding:0">
        <h4>Feedback</h4>
        <div class="original-text">${escapeHtml(f.feedback_text)}</div>
        <h4>Explanation</h4>
        <p>${escapeHtml(f.explanation || '—')}</p>
        ${keywords}${cats}${action}
        <h4 style="margin-top:1rem">Source</h4>
        <p style="font-size:0.9rem">${f.source_type === 'document' ? 'Document' : 'Manual entry'}${f.document_name ? ' · ' + escapeHtml(f.document_name) : ''}${f.document_id ? ` · <a href="#" onclick="event.preventDefault();navigate('documents');viewDocument(${f.document_id})">View document report</a>` : ''}</p>
      </div>
    `;
    card.classList.remove('hidden');
    card.scrollIntoView({ behavior: 'smooth' });
  } catch (e) {
    alert(e.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('historyFilterBtn')?.addEventListener('click', () => loadHistory(1));
  document.getElementById('historySearch')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') loadHistory(1);
  });
  document.getElementById('closeDetailBtn')?.addEventListener('click', () => {
    document.getElementById('historyDetailCard').classList.add('hidden');
  });
});

/* ---------- Insights ---------- */
async function loadInsights() {
  const el = document.getElementById('insightsContent');
  try {
    const data = await api('/insights');
    const ins = data.insights || {};
    const stats = ins.stats || {};

    let complaintsHtml = '<p class="empty-state" style="padding:0.5rem 0">No complaint data yet.</p>';
    if (ins.top_complaints?.length) {
      complaintsHtml = '<ul class="insight-list">' +
        ins.top_complaints.map(c =>
          `<li><span>${escapeHtml(c.category)}</span><span class="insight-count">${c.count}</span></li>`
        ).join('') + '</ul>';
    }

    let posHtml = '<p class="empty-state" style="padding:0.5rem 0">No positive keyword data yet.</p>';
    if (ins.top_positive_keywords?.length) {
      posHtml = '<ul class="insight-list">' +
        ins.top_positive_keywords.map(k =>
          `<li><span>${escapeHtml(k.keyword)}</span><span class="insight-count">${k.count}</span></li>`
        ).join('') + '</ul>';
    }

    let negHtml = '<p class="empty-state" style="padding:0.5rem 0">No negative keyword data yet.</p>';
    if (ins.top_negative_keywords?.length) {
      negHtml = '<ul class="insight-list">' +
        ins.top_negative_keywords.map(k =>
          `<li><span>${escapeHtml(k.keyword)}</span><span class="insight-count">${k.count}</span></li>`
        ).join('') + '</ul>';
    }

    let improveHtml = '<p class="empty-state" style="padding:0.5rem 0">Not enough data for recommendations.</p>';
    if (ins.improvement_areas?.length) {
      improveHtml = '<ul style="padding-left:1.2rem;font-size:0.9rem">' +
        ins.improvement_areas.map(a => `<li style="margin-bottom:0.4rem">${escapeHtml(a)}</li>`).join('') +
        '</ul><p style="font-size:0.8rem;color:var(--text-muted);margin-top:0.75rem">Based on frequency of complaint categories in stored feedback. AI-generated interpretations appear in individual analysis results.</p>';
    }

    let trendNote = '';
    if (ins.trend_note) {
      trendNote = `<p style="font-size:0.85rem;color:var(--text-muted);margin-top:0.5rem">${escapeHtml(ins.trend_note)}</p>`;
    }

    el.innerHTML = `
      <div class="insight-card">
        <h3><i data-lucide="bar-chart-2"></i> Summary</h3>
        <div class="report-summary">
          <div class="report-stat"><span class="val">${stats.total_feedback || 0}</span><span class="lbl">Total feedback</span></div>
          <div class="report-stat"><span class="val" style="color:var(--green)">${stats.positive_pct || 0}%</span><span class="lbl">Positive</span></div>
          <div class="report-stat"><span class="val" style="color:var(--red)">${stats.negative_pct || 0}%</span><span class="lbl">Negative</span></div>
          <div class="report-stat"><span class="val" style="color:var(--amber)">${stats.neutral_pct || 0}%</span><span class="lbl">Neutral</span></div>
        </div>
        ${trendNote}
      </div>
      <div class="insight-card">
        <h3><i data-lucide="alert-triangle"></i> Top Complaints</h3>
        ${complaintsHtml}
      </div>
      <div class="insight-card">
        <h3><i data-lucide="thumbs-up"></i> Frequently Praised</h3>
        ${posHtml}
      </div>
      <div class="insight-card">
        <h3><i data-lucide="thumbs-down"></i> Common Negative Themes</h3>
        ${negHtml}
      </div>
      <div class="insight-card" style="grid-column:1/-1">
        <h3><i data-lucide="target"></i> Potential Improvement Areas</h3>
        ${improveHtml}
      </div>
    `;
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    el.innerHTML = `<p class="empty-state">Failed to load insights: ${escapeHtml(e.message)}</p>`;
  }
}
